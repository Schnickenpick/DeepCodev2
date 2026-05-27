# -*- coding: utf-8 -*-
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.rule import Rule
from rich.padding import Padding
from rich import box
from .models import PROVIDERS, TIER_COLORS, get_model

console = Console(highlight=False)

_stream_at_line_start = True
_streamed_lines = 0
_notify = True


def set_notify(enabled: bool):
    global _notify
    _notify = enabled


def print_banner():
    banner = r"""
  ██████╗ ███████╗███████╗██████╗      ██████╗ ██████╗ ██████╗ ███████╗
  ██╔══██╗██╔════╝██╔════╝██╔══██╗    ██╔════╝██╔═══██╗██╔══██╗██╔════╝
  ██║  ██║█████╗  █████╗  ██████╔╝    ██║     ██║   ██║██║  ██║█████╗
  ██║  ██║██╔══╝  ██╔══╝  ██╔═══╝     ██║     ██║   ██║██║  ██║██╔══╝
  ██████╔╝███████╗███████╗██║         ╚██████╗╚██████╔╝██████╔╝███████╗
  ╚═════╝ ╚══════╝╚══════╝╚═╝          ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝"""
    console.print(banner, style="bold magenta")
    console.print()
    console.print("  Free AI. 34 models. No account. No limits.", style="dim")
    console.print()


def print_model_status(model_id: str, mode: str = "chat", agent: bool = False):
    m = get_model(model_id)
    provider = PROVIDERS.get(m["provider"], {})
    color = provider.get("color", "white")
    tier_color = TIER_COLORS.get(m["tier"], "white")

    if mode == "merge":
        line = "[yellow bold]⚡ Merge AI[/yellow bold]  [dim]GPT-5.5 + Claude Opus 4.7 + Gemini 2.5 Pro[/dim]"
    elif mode == "search":
        line = "[blue bold]🔍 Web Search[/blue bold]  [dim]Searches web, synthesizes with sources[/dim]"
    else:
        line = f"[{color} bold]{m['name']}[/{color} bold]  [dim]{provider.get('name','?')} · [{tier_color}]{m['tier']}[/{tier_color}][/dim]"

    agent_tag = "  [bold green]⚡ agent[/bold green]" if agent else ""
    console.print(f"  Model: {line}{agent_tag}")
    console.print("  Type [bold cyan]/help[/bold cyan] for commands", style="dim")
    console.print()


def print_help(agent: bool = False):
    rows = [
        ("/model [name]",        "Switch model — e.g. /model opus"),
        ("/models",              "List all 34 models"),
        ("/agent",               f"Toggle agent mode (tools) — currently {'[green]ON[/green]' if agent else '[dim]OFF[/dim]'}"),
        ("/reasoning [level]",   "Set reasoning — off/low/middle/high/ultra"),
        ("/merge",               "Toggle Merge AI mode"),
        ("/search",              "Toggle Web Search mode"),
        ("/new",                 "Start new conversation"),
        ("/history",             "Show past conversations"),
        ("/memory",              "Show remembered facts"),
        ("/init [hint]",         "Generate DEEPCODE.md for this project"),
        ("/notify",              "Toggle bell notification on/off"),
        ("/quizmaxoptions [n]",  "Set max quiz options (default 5)"),
        ("/clear",               "Clear screen"),
        ("/exit",                "Quit"),
    ]
    console.print()
    for cmd, desc in rows:
        console.print(f"  [bold cyan]{cmd:<22}[/bold cyan] {desc}")
    console.print()


def print_models_list(current_model_id: str):
    from .models import MODELS
    console.print()
    current_provider = None
    for m in MODELS:
        if m["provider"] != current_provider:
            current_provider = m["provider"]
            p = PROVIDERS.get(current_provider, {})
            console.print(f"  [{p.get('color','white')} bold]{p.get('name','?')}[/{p.get('color','white')} bold]")
        active = " ◀" if m["id"] == current_model_id else ""
        tier_color = TIER_COLORS.get(m["tier"], "white")
        console.print(f"    [dim]{m['name']:<26}[/dim][{tier_color}]{m['tier']:<12}[/{tier_color}][green]{active}[/green]")
    console.print()


def print_user_label(text: str):
    console.print()
    console.print(f"  [bold white]You[/bold white]")
    console.print(f"  [white]{text}[/white]")
    console.print()


def print_assistant_header(model_id: str, mode: str = "chat"):
    global _stream_at_line_start, _streamed_lines
    _stream_at_line_start = True
    _streamed_lines = 0
    m = get_model(model_id)
    provider = PROVIDERS.get(m["provider"], {})
    color = provider.get("color", "white")

    if mode == "merge":
        label = "⚡ Merge AI"
        color = "yellow"
    elif mode == "search":
        label = "🔍 Web Search"
        color = "blue"
    else:
        label = m["name"]

    console.print(f"  [{color} bold]{label}[/{color} bold]")


def stream_token(token: str):
    """No-op during streaming — we buffer and render after."""
    pass


def finish_stream(full_text: str):
    global _stream_at_line_start, _streamed_lines
    _stream_at_line_start = True
    _streamed_lines = 0

    text = full_text.strip()
    if not text:
        return

    for line in text.splitlines():
        console.print("  " + line, markup=False, highlight=False)
    console.print()
    if _notify:
        print("\a", end="", flush=True)


def print_reasoning(text: str):
    if not text:
        return
    console.print(Padding(
        Panel(
            Markdown(text),
            title="[dim]Reasoning[/dim]",
            border_style="dim magenta",
            padding=(0, 1),
        ),
        pad=(0, 0, 0, 2),
    ))


def print_search_sources(sources: list):
    if not sources:
        return
    console.print("  [blue bold]Sources[/blue bold]")
    for s in sources:
        console.print(f"  [dim]·[/dim] {s.get('title', s.get('url',''))}")
    console.print()


def print_status(msg: str):
    console.print(f"  [dim yellow]{msg}[/dim yellow]", end="\r")


def print_response_time(elapsed: float):
    console.print(f"  [dim]⏱ {elapsed:.1f}s[/dim]")


def print_keybinds():
    rows = [
        ("Enter",       "Send message"),
        ("Ctrl+J",      "New line (multiline input)"),
        ("Tab",         "Autocomplete command / cycle options"),
        ("↑ / ↓",       "Navigate autocomplete menu / history"),
        ("Ctrl+C",      "Cancel / exit"),
        ("Ctrl+R",      "Search input history"),
    ]
    console.print()
    console.print("  [bold]Keybinds[/bold]")
    for key, desc in rows:
        console.print(f"  [bold cyan]{key:<20}[/bold cyan] [dim]{desc}[/dim]")
    console.print()


def print_error(msg: str):
    console.print(f"\n  [bold red]✗[/bold red] {msg}\n")


def print_info(msg: str):
    console.print(f"  [dim]{msg}[/dim]")


def render_markdown(text: str):
    console.print(Padding(Markdown(text), pad=(0, 0, 0, 2)))


def print_memory(facts: list):
    if not facts:
        console.print("\n  [dim]No memories yet.[/dim]\n")
        return
    console.print()
    console.print("  [bold]Remembered Facts[/bold]")
    for f in facts:
        console.print(f"  [dim]·[/dim] {f}")
    console.print()


def print_quiz(options: list[str]) -> None:
    """Render numbered quiz options. Last option is always 'Type something different'."""
    for i, opt in enumerate(options, 1):
        if i == len(options):
            console.print(f"  [dim]{i}. {opt}[/dim]")
        else:
            console.print(f"  [bold cyan]{i}.[/bold cyan] {opt}")
    console.print()
