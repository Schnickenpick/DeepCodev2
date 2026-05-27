from __future__ import annotations
import json
import re
import sys
from . import api, renderer
from .tools import TOOL_REGISTRY, ToolError, TOOL_DESCRIPTIONS
from .permissions import ask_permission, OPTION_DENY
from .system_prompt import SYSTEM_PROMPT

TOOL_TAG_RE = re.compile(r'<tool>\s*(\{.*?\})\s*</tool>', re.DOTALL)
QUIZ_RE = re.compile(r'<quiz>([\s\S]*?)</quiz>')

MAX_ITERATIONS = 20


def _build_prompt(conversation: list[dict], memory: list[str], deepcode_md: str = "") -> str:
    parts = [SYSTEM_PROMPT, "\n\n"]
    if deepcode_md:
        parts.append(f"[Project context from DEEPCODE.md:\n{deepcode_md}\n]\n\n")
    if memory:
        facts = "\n".join(f"- {f}" for f in memory[-10:])
        parts.append(f"User facts: {facts}\n\n")
    for msg in conversation:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            parts.append(f"User: {content}\n\n")
        elif role == "assistant":
            parts.append(f"Assistant: {content}\n\n")
        elif role == "tool_result":
            parts.append(f"Tool result: {content}\n\n")
    parts.append("Assistant:")
    return "".join(parts)


def _extract_json_objects(text: str) -> list[tuple[str, dict]]:
    """Find all top-level JSON objects in text using brace counting. Returns (match_str, parsed) pairs."""
    results = []
    i = 0
    while i < len(text):
        if text[i] != '{':
            i += 1
            continue
        depth = 0
        in_string = False
        escape = False
        start = i
        for j in range(i, len(text)):
            ch = text[j]
            if escape:
                escape = False
                continue
            if ch == '\\' and in_string:
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    candidate = text[start:j+1]
                    try:
                        obj = json.loads(candidate)
                        if isinstance(obj, dict) and "name" in obj and "args" in obj:
                            results.append((candidate, obj))
                    except Exception:
                        pass
                    i = j + 1
                    break
        else:
            break
    return results


def _parse_tool_calls(text: str) -> list[dict]:
    calls = []
    # Try tagged format first
    for m in TOOL_TAG_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
            if "name" in obj and "args" in obj:
                calls.append({"match": m.group(0), "name": obj["name"], "args": obj["args"]})
        except Exception:
            pass
    if calls:
        return calls
    # Fallback: brace-counting extractor handles arbitrarily nested/long JSON
    for match_str, obj in _extract_json_objects(text):
        calls.append({"match": match_str, "name": obj["name"], "args": obj["args"]})
    return calls


def _strip_tool_calls(text: str, calls: list[dict]) -> str:
    for c in calls:
        text = text.replace(c["match"], "")
    return text.strip()


def _show_tool_result(tool_name: str, result: str, success: bool):
    from rich.console import Console
    c = Console(highlight=False)
    lines = result.splitlines()
    icon = "[green]✓[/green]" if success else "[red]✗[/red]"
    desc = TOOL_DESCRIPTIONS.get(tool_name, "")
    c.print(f"  {icon} [bold]{tool_name}[/bold]  [dim]{desc}[/dim]")
    for line in lines[:3]:
        c.print(f"    [dim]{line[:120]}[/dim]")
    if len(lines) > 3:
        c.print(f"    [dim]... {len(lines)-3} more lines[/dim]")
    c.print()


async def run_agent(user_message: str, conversation: list[dict], memory: list[str], model_id: str, deepcode_md: str = ""):
    conversation.append({"role": "user", "content": user_message})

    for iteration in range(MAX_ITERATIONS):
        prompt = _build_prompt(conversation, memory, deepcode_md)
        full_response = ""
        _show_thinking_dot = True

        async def _stream_with_indicator():
            nonlocal full_response, _show_thinking_dot
            import asyncio
            dot_task = asyncio.get_event_loop().create_task(_thinking_dots())
            try:
                async for chunk in api.stream_chat(prompt, model_id):
                    if chunk.get("error"):
                        renderer.print_error(chunk["error"])
                        break
                    if chunk.get("done"):
                        break
                    delta = chunk.get("delta", "")
                    if delta:
                        full_response += delta
            finally:
                _show_thinking_dot = False
                dot_task.cancel()
                try:
                    await asyncio.shield(dot_task)
                except Exception:
                    pass
                sys.stdout.write("\033[2K\r")
                sys.stdout.flush()

        async def _thinking_dots():
            import asyncio
            frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            i = 0
            try:
                while _show_thinking_dot:
                    sys.stdout.write(f"\r  \033[2m{frames[i % len(frames)]} thinking...\033[0m")
                    sys.stdout.flush()
                    i += 1
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                pass

        try:
            await _stream_with_indicator()
        except Exception as e:
            renderer.print_error(str(e))
            break

        tool_calls = _parse_tool_calls(full_response)
        visible = _strip_tool_calls(full_response, tool_calls).strip()

        # Strip quiz block before printing — caller handles quiz display
        visible_clean = QUIZ_RE.sub("", visible).strip()

        if visible_clean:
            renderer.print_assistant_header(model_id)
            renderer.finish_stream(visible_clean)

        if not tool_calls:
            conversation.append({"role": "assistant", "content": visible or full_response})
            return visible, conversation

        conversation.append({"role": "assistant", "content": full_response})

        all_denied = True
        for call in tool_calls:
            name = call["name"]
            args = call["args"]

            if name not in TOOL_REGISTRY:
                err = f"Unknown tool: {name}"
                renderer.print_error(err)
                conversation.append({"role": "tool_result", "content": err})
                continue

            decision = ask_permission(name, args)
            if decision == OPTION_DENY:
                conversation.append({"role": "tool_result", "content": "User denied."})
                continue

            all_denied = False
            try:
                result = TOOL_REGISTRY[name](args)
                _show_tool_result(name, result, True)
            except Exception as e:
                result = f"Error: {e}"
                _show_tool_result(name, result, False)

            conversation.append({"role": "tool_result", "content": f"[{name}]\n{result}"})

        if all_denied:
            renderer.print_info("All tools denied.")
            break

    return "", conversation
