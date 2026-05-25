from __future__ import annotations
import json
import os
from pathlib import Path
from datetime import datetime

DATA_DIR = Path.home() / ".deepcode"
HISTORY_FILE = DATA_DIR / "history.json"
MEMORY_FILE = DATA_DIR / "memory.json"
CONFIG_FILE = DATA_DIR / "config.json"


def ensure_dir():
    DATA_DIR.mkdir(exist_ok=True)


def load_history() -> list[dict]:
    ensure_dir()
    if not HISTORY_FILE.exists():
        return []
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_history(sessions: list[dict]):
    ensure_dir()
    HISTORY_FILE.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")


def load_memory() -> list[str]:
    ensure_dir()
    if not MEMORY_FILE.exists():
        return []
    try:
        return json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_memory(facts: list[str]):
    ensure_dir()
    MEMORY_FILE.write_text(json.dumps(facts, ensure_ascii=False, indent=2), encoding="utf-8")


def load_config() -> dict:
    ensure_dir()
    if not CONFIG_FILE.exists():
        return {}
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_config(cfg: dict):
    ensure_dir()
    CONFIG_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


def new_session(model_id: str) -> dict:
    return {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S"),
        "model": model_id,
        "created": datetime.now().isoformat(),
        "messages": [],
    }
