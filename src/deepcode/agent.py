from __future__ import annotations
import json
import re
import sys
from . import api, renderer
from .tools import TOOL_REGISTRY, ToolError, TOOL_DESCRIPTIONS
from .permissions import ask_permission, OPTION_DENY
from .system_prompt import SYSTEM_PROMPT

# Match <tool>{...}</tool> OR bare {...} JSON tool calls
TOOL_TAG_RE = re.compile(r'<tool>\s*(\{.*?\})\s*</tool>', re.DOTALL)
BARE_JSON_RE = re.compile(r'(\{"name"\s*:\s*"[a-z_]+"\s*,\s*"args"\s*:\s*\{[^{}]*(?:\{[^{}]*\}[^{}]*)?\}(?:\s*\})?)', re.DOTALL)

MAX_ITERATIONS = 20


def _build_prompt(conversation: list[dict], memory: list[str]) -> str:
    parts = [SYSTEM_PROMPT, "\n\n"]
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
    # Fallback: bare JSON
    for m in BARE_JSON_RE.finditer(text):
        try:
            obj = json.loads(m.group(1))
            if "name" in obj and "args" in obj:
                calls.append({"match": m.group(0), "name": obj["name"], "args": obj["args"]})
        except Exception:
            pass
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


async def run_agent(user_message: str, conversation: list[dict], memory: list[str], model_id: str):
    conversation.append({"role": "user", "content": user_message})

    for iteration in range(MAX_ITERATIONS):
        prompt = _build_prompt(conversation, memory)
        full_response = ""

        try:
            async for chunk in api.stream_chat(prompt, model_id):
                if chunk.get("delta"):
                    full_response += chunk["delta"]
                if chunk.get("error"):
                    renderer.print_error(chunk["error"])
                    break
                if chunk.get("done"):
                    break
        except Exception as e:
            renderer.print_error(str(e))
            break

        tool_calls = _parse_tool_calls(full_response)
        visible = _strip_tool_calls(full_response, tool_calls).strip()

        # Only print model name + text if there's actual text
        if visible:
            renderer.print_assistant_header(model_id)
            renderer.finish_stream(visible)

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
