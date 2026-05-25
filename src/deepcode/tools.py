from __future__ import annotations
import os
import subprocess
import fnmatch
from pathlib import Path


class ToolError(Exception):
    pass


def read_file(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise ToolError(f"File not found: {path}")
    if not p.is_file():
        raise ToolError(f"Not a file: {path}")
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        # Return with line numbers for context
        numbered = "\n".join(f"{i+1:4} | {line}" for i, line in enumerate(lines))
        return f"File: {path} ({len(lines)} lines)\n\n{numbered}"
    except Exception as e:
        raise ToolError(str(e))


def write_file(path: str, content: str) -> str:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    lines = content.count("\n") + 1
    return f"Written {lines} lines to {path}"


def edit_file(path: str, old_text: str, new_text: str) -> str:
    p = Path(path)
    if not p.exists():
        raise ToolError(f"File not found: {path}")
    content = p.read_text(encoding="utf-8", errors="replace")
    if old_text not in content:
        raise ToolError(f"old_text not found in {path}. Read the file first to get exact content.")
    count = content.count(old_text)
    if count > 1:
        raise ToolError(f"old_text matches {count} places in {path}. Make it more specific.")
    new_content = content.replace(old_text, new_text, 1)
    p.write_text(new_content, encoding="utf-8")
    return f"Edited {path} — replaced 1 occurrence"


def run_command(cmd: str, cwd: str = None) -> str:
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=cwd or os.getcwd(),
        )
        out = result.stdout.strip()
        err = result.stderr.strip()
        parts = []
        if out:
            parts.append(out)
        if err:
            parts.append(f"[stderr]\n{err}")
        if result.returncode != 0:
            parts.append(f"[exit code: {result.returncode}]")
        return "\n".join(parts) if parts else "(no output)"
    except subprocess.TimeoutExpired:
        raise ToolError("Command timed out after 120s")
    except Exception as e:
        raise ToolError(str(e))


def list_dir(path: str = ".") -> str:
    p = Path(path)
    if not p.exists():
        raise ToolError(f"Path not found: {path}")
    if not p.is_dir():
        raise ToolError(f"Not a directory: {path}")
    entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower()))
    lines = []
    for e in entries:
        if e.is_dir():
            lines.append(f"  📁 {e.name}/")
        else:
            size = e.stat().st_size
            size_str = f"{size:,}" if size < 1024 else f"{size//1024:,}KB"
            lines.append(f"  📄 {e.name}  [{size_str}]")
    return f"{path}/\n" + "\n".join(lines) if lines else f"{path}/ (empty)"


def search_files(pattern: str, path: str = ".", glob: str = "*") -> str:
    base = Path(path)
    if not base.exists():
        raise ToolError(f"Path not found: {path}")
    results = []
    for p in base.rglob(glob):
        if not p.is_file():
            continue
        # Skip common noise dirs
        parts = p.parts
        if any(part in {".git", "__pycache__", "node_modules", ".venv", "venv", "dist", "build"} for part in parts):
            continue
        try:
            content = p.read_text(encoding="utf-8", errors="replace")
            for i, line in enumerate(content.splitlines(), 1):
                if pattern.lower() in line.lower():
                    results.append(f"{p}:{i}: {line.strip()}")
        except Exception:
            continue
    if not results:
        return f"No matches for '{pattern}' in {path}/**/{glob}"
    return "\n".join(results[:100])  # cap at 100 matches


TOOL_REGISTRY = {
    "read_file":    lambda args: read_file(args["path"]),
    "write_file":   lambda args: write_file(args["path"], args["content"]),
    "edit_file":    lambda args: edit_file(args["path"], args["old_text"], args["new_text"]),
    "run_command":  lambda args: run_command(args["cmd"], args.get("cwd")),
    "list_dir":     lambda args: list_dir(args.get("path", ".")),
    "search_files": lambda args: search_files(args["pattern"], args.get("path", "."), args.get("glob", "*")),
}

TOOL_DESCRIPTIONS = {
    "read_file":    "Read file contents",
    "write_file":   "Write content to file",
    "edit_file":    "Replace text in file",
    "run_command":  "Execute shell command",
    "list_dir":     "List directory contents",
    "search_files": "Search for pattern in files",
}
