from __future__ import annotations
import asyncio
import sys
import time
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.styles import Style
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.keys import Keys
from prompt_toolkit.filters import is_done
from prompt_toolkit.key_binding import KeyBindings

from . import api, renderer, storage
from .models import DEFAULT_MODEL, find_model, MODELS
from .agent import run_agent
from .system_prompt import SYSTEM_PROMPT
from .reasoning import run_reasoning, LEVELS as REASONING_LEVELS


COMMANDS = [
    ("/notify",    "Toggle bell notification on/off"),
    ("/reasoning", "Set reasoning level — off/low/middle/high/ultra"),
    ("/agent",     "Toggle agent mode (file/shell tools)"),
    ("/model",    "Switch model — e.g. /model opus"),
    ("/models",   "List all 34 models"),
    ("/merge",    "Toggle Merge AI mode"),
    ("/search",   "Toggle Web Search mode"),
    ("/session",  "Browse & resume past conversations"),
    ("/new",      "Start new conversation"),
    ("/compact",  "Summarize conversation to save context"),
    ("/history",  "Show past conversations (quick list)"),
    ("/memory",   "Show remembered facts"),
    ("/init",     "Generate DEEPCODE.md for this project"),
    ("/keybinds", "Show all keyboard shortcuts"),
    ("/clear",    "Clear screen"),
    ("/help",     "Show all commands"),
    ("/exit",     "Quit"),
]


class DeepCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        stripped = text.lstrip()

        if not stripped.startswith("/"):
            return

        parts = stripped.split(None, 1)
        cmd = parts[0]
        has_arg = len(parts) > 1

        if not has_arg:
            for name, desc in COMMANDS:
                if name.startswith(cmd):
                    yield Completion(
                        name[len(cmd):],
                        start_position=0,
                        display=HTML(f"<cyan>{name}</cyan>"),
                        display_meta=desc,
                    )
        elif cmd == "/model":
            partial = parts[1].lower()
            for m in MODELS:
                if partial in m["name"].lower() or partial in m["provider"].lower():
                    yield Completion(
                        m["name"],
                        start_position=-len(parts[1]),
                        display=HTML(f"<b>{m['name']}</b>"),
                        display_meta=m["provider"],
                    )


PROMPT_STYLE = Style.from_dict({
    "prompt": "bold cyan",
    "completion-menu.completion":              "bg:#111118 #555566",
    "completion-menu.completion.current":      "bg:#1e1e2e bold #c084fc",
    "completion-menu.meta.completion":         "bg:#111118 #333344",
    "completion-menu.meta.completion.current": "bg:#1e1e2e #888899",
    "scrollbar.background": "bg:#111118",
    "scrollbar.button":     "bg:#c084fc",
})


def _make_bindings() -> KeyBindings:
    kb = KeyBindings()

    @kb.add("c-j")
    def _newline_cj(event):
        event.current_buffer.insert_text("\n")

    @kb.add("escape", "enter")
    def _newline_alt(event):
        event.current_buffer.insert_text("\n")

    return kb


async def _gen_title(first_message: str, model_id: str) -> str:
    """Ask AI for a short 4-word title for this conversation."""
    prompt = f"Give a 4-word title for a conversation starting with: \"{first_message[:100]}\". Reply with ONLY the title, no quotes, no punctuation."
    title = ""
    try:
        async for chunk in api.stream_chat(prompt, model_id):
            if chunk.get("delta"):
                title += chunk["delta"]
            if chunk.get("done"):
                break
        return title.strip()[:50] or first_message[:40]
    except Exception:
        return first_message[:40]


async def _init_deepcode_md(instructions: str, model_id: str) -> str:
    """Scan cwd and generate a DEEPCODE.md file."""
    from pathlib import Path
    import os

    cwd = Path.cwd()

    # Collect file tree (max depth 3, skip common noise)
    skip = {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build", ".egg-info"}
    tree_lines = []
    for root, dirs, files in os.walk(cwd):
        dirs[:] = [d for d in dirs if d not in skip]
        depth = len(Path(root).relative_to(cwd).parts)
        if depth > 3:
            dirs.clear()
            continue
        indent = "  " * depth
        rel = Path(root).relative_to(cwd)
        if depth > 0:
            tree_lines.append(f"{indent}{rel.name}/")
        for f in files:
            tree_lines.append(f"{'  ' * (depth+1)}{f}")

    tree = "\n".join(tree_lines[:150])

    # Read key files if they exist
    key_files = ["README.md", "pyproject.toml", "package.json", "Cargo.toml", "go.mod", "requirements.txt"]
    snippets = []
    for kf in key_files:
        p = cwd / kf
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8")[:800]
                snippets.append(f"--- {kf} ---\n{content}")
            except Exception:
                pass

    extra = f"\nExtra instructions: {instructions}" if instructions else ""
    prompt = f"""You are generating a DEEPCODE.md file for a software project. This file is like a CLAUDE.md — it gives an AI assistant persistent context about the project so it can help more effectively.

Project file tree:
{tree}

{"Key files:" if snippets else ""}
{chr(10).join(snippets)}
{extra}

Write a DEEPCODE.md that includes:
- What this project is and does
- Tech stack and key dependencies
- Project structure overview
- How to run / build it
- Any important conventions or notes an AI should know

Be concise. Use markdown headers. No fluff."""

    result = ""
    renderer.print_info("Generating DEEPCODE.md...")
    try:
        async for chunk in api.stream_chat(prompt, model_id):
            if chunk.get("delta"):
                result += chunk["delta"]
            if chunk.get("done"):
                break
    except Exception as e:
        renderer.print_error(str(e))
        return ""
    return result.strip()


async def _compact_conversation(conversation: list[dict], model_id: str) -> str:
    """Summarize the conversation so far into a compact context block."""
    history = "\n".join(
        f"{m['role'].upper()}: {m['content'][:500]}"
        for m in conversation[-20:]
    )
    prompt = f"Summarize this conversation concisely so it can be used as context. Keep all important decisions, code, and facts. Be brief.\n\n{history}\n\nSummary:"
    summary = ""
    renderer.print_info("Compacting conversation...")
    try:
        async for chunk in api.stream_chat(prompt, model_id):
            if chunk.get("delta"):
                summary += chunk["delta"]
            if chunk.get("done"):
                break
        return summary.strip()
    except Exception as e:
        renderer.print_error(str(e))
        return ""


def _session_browser(sessions: list[dict]) -> dict | None:
    """Interactive arrow-key session browser. Returns chosen session or None."""
    if not sessions:
        renderer.print_info("No past sessions found.")
        return None

    import msvcrt

    items = list(reversed(sessions[-30:]))  # most recent first
    selected = 0

    def _label(s: dict) -> str:
        title = s.get("title", "Untitled")
        count = len(s.get("messages", []))
        sid = s.get("id", "")[:10]
        return f"{title[:45]:<46} [dim]{count} msgs · {sid}[/dim]"

    def _render(sel: int):
        renderer.console.print("\n  [bold cyan]Sessions[/bold cyan]  [dim]↑↓ navigate · Enter select · Esc cancel[/dim]\n")
        for i, s in enumerate(items):
            if i == sel:
                renderer.console.print(f"  [bold cyan]❯ {_label(s)}[/bold cyan]")
            else:
                renderer.console.print(f"    [dim]{_label(s)}[/dim]")
        renderer.console.print()

    _render(selected)
    total = len(items)

    while True:
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch()
            if ch2 == "H":   # up
                selected = (selected - 1) % total
            elif ch2 == "P": # down
                selected = (selected + 1) % total
            else:
                continue
        elif ch == "\r":
            # clear menu
            lines = total + 4
            for _ in range(lines):
                sys.stdout.write("\033[1A\033[2K")
            sys.stdout.flush()
            return items[selected]
        elif ch == "\x1b":
            lines = total + 4
            for _ in range(lines):
                sys.stdout.write("\033[1A\033[2K")
            sys.stdout.flush()
            return None
        else:
            continue

        # redraw
        lines = total + 4
        for _ in range(lines):
            sys.stdout.write("\033[1A\033[2K")
        sys.stdout.flush()
        _render(selected)


async def run_chat_stream(message: str, model_id: str, mode: str, memory: list[str], deepcode_md: str = ""):
    full_content = ""
    reasoning = ""
    t0 = time.time()

    try:
        if mode == "merge":
            async for chunk in api.stream_merge(message):
                if chunk.get("status"):
                    renderer.print_status(chunk["status"])
                if chunk.get("delta"):
                    full_content += chunk["delta"]
                    renderer.stream_token(chunk["delta"])
                if chunk.get("reasoning"):
                    reasoning = chunk["reasoning"]
                if chunk.get("answer"):
                    full_content = chunk["answer"]
                if chunk.get("done"):
                    break

        elif mode == "search":
            async for chunk in api.stream_search(message):
                if chunk.get("status"):
                    renderer.print_status(chunk["status"])
                if chunk.get("delta"):
                    full_content += chunk["delta"]
                    renderer.stream_token(chunk["delta"])
                if chunk.get("sources"):
                    renderer.print_search_sources(chunk["sources"])
                if chunk.get("done"):
                    break

        else:
            extra = ""
            if deepcode_md:
                extra += f"\n\n[Project context from DEEPCODE.md:\n{deepcode_md}\n]"
            if memory:
                facts = "\n".join(f"- {f}" for f in memory[-15:])
                extra += f"\n\n[User context:\n{facts}\n]"
            prompt = f"{SYSTEM_PROMPT}{extra}\n\nUser: {message}\nAssistant:"

            async for chunk in api.stream_chat(prompt, model_id):
                if chunk.get("delta"):
                    full_content += chunk["delta"]
                    renderer.stream_token(chunk["delta"])
                if chunk.get("reasoning"):
                    reasoning = chunk["reasoning"]
                if chunk.get("answer"):
                    full_content = chunk["answer"]
                if chunk.get("error"):
                    renderer.print_error(chunk["error"])
                if chunk.get("done"):
                    break

    except asyncio.CancelledError:
        if full_content.strip():
            renderer.print_assistant_header(model_id, mode)
            renderer.finish_stream(full_content)
        renderer.print_info("Stopped.")
        return full_content, reasoning
    except Exception as e:
        renderer.print_error(str(e))
        return "", ""

    elapsed = time.time() - t0

    if full_content.strip():
        renderer.print_assistant_header(model_id, mode)
        renderer.finish_stream(full_content)
        if reasoning:
            renderer.print_reasoning(reasoning)
        renderer.print_response_time(elapsed)

    return full_content, reasoning


async def main_loop():
    cfg = storage.load_config()
    model_id = cfg.get("model", DEFAULT_MODEL)
    mode = cfg.get("mode", "chat")
    agent_mode = cfg.get("agent", False)
    reasoning_level = cfg.get("reasoning", None)  # None = off
    renderer.set_notify(cfg.get("notify", True))

    storage.ensure_dir()
    history_path = storage.DATA_DIR / "prompt_history"

    kb = _make_bindings()

    session = PromptSession(
        history=FileHistory(str(history_path)),
        style=PROMPT_STYLE,
        completer=DeepCompleter(),
        complete_while_typing=True,
        reserve_space_for_menu=6,
        key_bindings=kb,
        multiline=False,
    )

    renderer.print_banner()
    renderer.print_model_status(model_id, mode, agent_mode)

    sessions = storage.load_history()
    memory = storage.load_memory()
    deepcode_md = storage.load_deepcode_md()
    if deepcode_md:
        renderer.print_info("DEEPCODE.md loaded.")
    current_session = storage.new_session(model_id)
    agent_conversation: list[dict] = []
    stream_task = None

    while True:
        try:
            indicators = []
            if agent_mode:          indicators.append("agent")
            if mode == "merge":     indicators.append("merge")
            elif mode == "search":  indicators.append("search")
            if reasoning_level:     indicators.append(f"reasoning:{reasoning_level}")
            prefix = f"[{', '.join(indicators)}] " if indicators else ""

            raw = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: session.prompt(f"\n  {prefix}❯ ", style=PROMPT_STYLE)
            )
        except KeyboardInterrupt:
            renderer.print_info("\nBye!")
            break
        except EOFError:
            renderer.print_info("\nBye!")
            break

        text = raw.strip()
        if not text:
            continue

        if text.startswith("/"):
            parts = text.split(None, 1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""

            if cmd == "/exit":
                renderer.print_info("Bye!")
                break

            elif cmd == "/clear":
                renderer.console.clear()
                renderer.print_banner()
                renderer.print_model_status(model_id, mode, agent_mode)

            elif cmd == "/new":
                if current_session["messages"]:
                    sessions.append(current_session)
                    storage.save_history(sessions)
                current_session = storage.new_session(model_id)
                agent_conversation = []
                renderer.print_info("New conversation started.")

            elif cmd == "/session":
                chosen = _session_browser(sessions)
                if chosen:
                    current_session = chosen
                    agent_conversation = [
                        {"role": m["role"], "content": m["content"]}
                        for m in chosen.get("messages", [])
                        if m["role"] in ("user", "assistant")
                    ]
                    title = chosen.get("title", "Untitled")
                    renderer.print_info(f"Resumed: {title}")

            elif cmd == "/compact":
                if not current_session["messages"]:
                    renderer.print_info("No conversation to compact.")
                else:
                    summary = await _compact_conversation(current_session["messages"], model_id)
                    if summary:
                        current_session["messages"] = [{
                            "role": "user",
                            "content": f"[Conversation summary]\n{summary}"
                        }]
                        agent_conversation = [{"role": "user", "content": f"[Conversation summary]\n{summary}"}]
                        renderer.print_info("Conversation compacted.")

            elif cmd == "/model":
                if arg:
                    found = find_model(arg)
                    if found:
                        model_id = found["id"]
                        mode = "chat"
                        cfg["model"] = model_id
                        cfg["mode"] = mode
                        storage.save_config(cfg)
                        renderer.print_model_status(model_id, mode, agent_mode)
                    else:
                        renderer.print_error(f"No model matching '{arg}'. Try /models.")
                else:
                    renderer.print_models_list(model_id)
                    renderer.print_info("Usage: /model <name>  e.g. /model opus")

            elif cmd == "/models":
                renderer.print_models_list(model_id)

            elif cmd == "/merge":
                mode = "chat" if mode == "merge" else "merge"
                cfg["mode"] = mode
                storage.save_config(cfg)
                renderer.print_model_status(model_id, mode, agent_mode)

            elif cmd == "/search":
                mode = "chat" if mode == "search" else "search"
                cfg["mode"] = mode
                storage.save_config(cfg)
                renderer.print_model_status(model_id, mode, agent_mode)

            elif cmd == "/agent":
                agent_mode = not agent_mode
                cfg["agent"] = agent_mode
                storage.save_config(cfg)
                agent_conversation = []
                renderer.print_model_status(model_id, mode, agent_mode)

            elif cmd == "/init":
                content = await _init_deepcode_md(arg, model_id)
                if content:
                    from pathlib import Path
                    out = Path.cwd() / "DEEPCODE.md"
                    out.write_text(content, encoding="utf-8")
                    deepcode_md = content
                    renderer.print_info(f"DEEPCODE.md written to {out}")

            elif cmd == "/memory":
                renderer.print_memory(memory)

            elif cmd == "/history":
                all_s = sessions + ([current_session] if current_session["messages"] else [])
                if not all_s:
                    renderer.print_info("No history yet.")
                else:
                    renderer.console.print()
                    for s in all_s[-10:]:
                        title = s.get("title", "Untitled")
                        count = len(s.get("messages", []))
                        renderer.console.print(f"  [cyan]{title[:50]}[/cyan]  [dim]{count} messages · {s['id']}[/dim]")
                    renderer.console.print()

            elif cmd == "/reasoning":
                lvl = arg.lower().strip()
                if lvl == "off" or (not lvl and reasoning_level):
                    reasoning_level = None
                    cfg["reasoning"] = None
                    renderer.print_info("Reasoning OFF.")
                elif lvl in REASONING_LEVELS:
                    reasoning_level = lvl
                    cfg["reasoning"] = lvl
                    renderer.print_info(f"Reasoning: {lvl}")
                else:
                    renderer.print_error(f"Unknown level '{lvl}'. Use: off, low, middle, high, ultra")
                storage.save_config(cfg)

            elif cmd == "/notify":
                new_state = not renderer._notify
                renderer.set_notify(new_state)
                cfg["notify"] = new_state
                storage.save_config(cfg)
                renderer.print_info(f"Bell notifications {'ON' if new_state else 'OFF'}.")

            elif cmd == "/keybinds":
                renderer.print_keybinds()

            elif cmd in ("/help", "/?"):
                renderer.print_help(agent_mode)

            else:
                renderer.print_error(f"Unknown command '{cmd}'. Type /help.")

            continue

        # send message
        current_session["messages"].append({"role": "user", "content": text, "model": model_id})

        # auto-generate title from first user message
        if len(current_session["messages"]) == 1 and not current_session.get("title"):
            asyncio.get_event_loop().create_task(
                _set_title(current_session, text, model_id)
            )

        if agent_mode and mode == "chat":
            content, agent_conversation = await run_agent(text, agent_conversation, memory, model_id, deepcode_md)
        elif reasoning_level and mode == "chat":
            memory_block = ""
            if deepcode_md:
                memory_block += f"[Project context from DEEPCODE.md:\n{deepcode_md}\n]"
            if memory:
                facts = "\n".join(f"- {f}" for f in memory[-15:])
                memory_block += f"\n\n[User context:\n{facts}\n]"
            renderer.print_assistant_header(model_id)
            content = await run_reasoning(text, model_id, reasoning_level, SYSTEM_PROMPT, memory_block.strip())
            renderer.finish_stream(content)
            reasoning = None
        else:
            content, reasoning = await run_chat_stream(text, model_id, mode, memory, deepcode_md)
            content = content  # already handled

        if content:
            current_session["messages"].append({
                "role": "assistant",
                "content": content,
                "model": model_id if mode == "chat" else f"__{mode}__",
            })
            storage.save_history((sessions + [current_session])[-100:])

            if len(current_session["messages"]) >= 2:
                new_facts = await api.extract_memory(current_session["messages"][-2:], memory)
                if new_facts:
                    memory = list(dict.fromkeys(memory + new_facts))[-50:]
                    storage.save_memory(memory)


async def _set_title(session_obj: dict, first_msg: str, model_id: str):
    """Background task — generate and save title."""
    title = await _gen_title(first_msg, model_id)
    session_obj["title"] = title


def run():
    asyncio.run(main_loop())
