from __future__ import annotations
import sys

# Tools allowed for entire session without asking
_session_allowed: set[str] = set()

OPTION_ALLOW     = "allow"
OPTION_ALLOW_ALL = "allow_all"
OPTION_DENY      = "deny"

_OPTIONS = [
    (OPTION_ALLOW,     "Yes",                  "allow once"),
    (OPTION_ALLOW_ALL, "Yes, don't ask again", "always allow this tool"),
    (OPTION_DENY,      "No",                   "deny"),
]


def _getch():
    if sys.platform == "win32":
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch()
            # H = up, P = down
            return "UP" if ch2 == "H" else "DOWN" if ch2 == "P" else "OTHER"
        if ch == "\r":
            return "ENTER"
        if ch == "\x1b":
            return "ESC"
        return ch
    else:
        import tty, termios
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                rest = sys.stdin.read(2)
                if rest == "[A": return "UP"
                if rest == "[B": return "DOWN"
                return "ESC"
            if ch == "\r" or ch == "\n": return "ENTER"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _write(s: str):
    sys.stdout.write(s)
    sys.stdout.flush()


def _move_up(n: int):
    if n > 0:
        _write(f"\033[{n}A")


def _clear_line():
    _write("\033[2K\r")


def ask_permission(tool_name: str, args: dict) -> str:
    if tool_name in _session_allowed:
        return OPTION_ALLOW

    from .tools import TOOL_DESCRIPTIONS
    from rich.console import Console
    console = Console(highlight=False)

    desc = TOOL_DESCRIPTIONS.get(tool_name, tool_name)
    arg_preview = _format_args(tool_name, args)

    console.print()
    console.print(f"  [bold yellow]⚡ Tool Request[/bold yellow]  [dim]{desc}[/dim]")
    console.print(f"  [bold]{tool_name}[/bold]  [dim]{arg_preview}[/dim]")
    console.print()

    selected = 0
    NUM_OPTS = len(_OPTIONS)

    # Print options once
    for i, (_, label, hint) in enumerate(_OPTIONS):
        if i == selected:
            console.print(f"  [bold cyan]❯ {label:<26}[/bold cyan][dim]{hint}[/dim]")
        else:
            console.print(f"    [dim]{label:<26}{hint}[/dim]")

    # Hide cursor
    _write("\033[?25l")

    try:
        while True:
            key = _getch()

            if key == "UP":
                selected = (selected - 1) % NUM_OPTS
            elif key == "DOWN":
                selected = (selected + 1) % NUM_OPTS
            elif key == "ENTER":
                break
            elif key == "ESC":
                selected = 2  # deny
                break

            # Move cursor back up to first option line and redraw
            _move_up(NUM_OPTS)
            for i, (_, label, hint) in enumerate(_OPTIONS):
                _clear_line()
                if i == selected:
                    console.print(f"  [bold cyan]❯ {label:<26}[/bold cyan][dim]{hint}[/dim]")
                else:
                    console.print(f"    [dim]{label:<26}{hint}[/dim]")

    finally:
        _write("\033[?25h")

    choice = _OPTIONS[selected][0]
    label  = _OPTIONS[selected][1]

    if choice == OPTION_ALLOW_ALL:
        _session_allowed.add(tool_name)

    # Clear option block, print final choice
    _move_up(NUM_OPTS)
    for _ in range(NUM_OPTS):
        _clear_line()
        _write("\n")
    _move_up(NUM_OPTS)
    console.print(f"  [dim]❯ {label}[/dim]")
    console.print()

    return choice


def _format_args(tool_name: str, args: dict) -> str:
    if tool_name == "run_command":
        return args.get("cmd", "")[:120]
    if tool_name in ("read_file", "write_file", "edit_file"):
        return args.get("path", "")
    if tool_name == "list_dir":
        return args.get("path", ".")
    if tool_name == "search_files":
        return f"'{args.get('pattern','')}' in {args.get('path','.')}"
    return str(args)[:120]


def reset_session_permissions():
    _session_allowed.clear()
