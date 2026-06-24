"""
OpsBrain — Memory Service

Extracted from agent_chat.py. Handles Agent memory persistence
(JSON file-based, similar to OpenClaw memory/*.md pattern).
"""

from __future__ import annotations

import json
import os
from typing import Optional

from logging_setup import get_logger

log = get_logger(__name__)

# ═══ Configuration ════════════════════════════════════════════════

def _get_memory_dir() -> str:
    from platform_info import get_data_dir
    return str(get_data_dir() / "memory")


MEMORY_DIR = _get_memory_dir()
MAX_CONTEXT = 20  # Max messages to retain


# ═══ Memory Operations ════════════════════════════════════════════

def memory_path(name: str) -> str:
    """Memory file path, like OpenClaw's memory/agent-name.json"""
    os.makedirs(MEMORY_DIR, exist_ok=True)
    return os.path.join(MEMORY_DIR, f"{name}.json")


def load_memory(name: str) -> list[dict]:
    """Load Agent memory (last N messages)."""
    path = memory_path(name)
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data[-MAX_CONTEXT:] if len(data) > MAX_CONTEXT else data
    except Exception:
        return []


def save_memory(name: str, messages: list[dict]) -> int:
    """Save Agent memory, retaining only recent context."""
    path = memory_path(name)
    existing = []
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            pass
    new_msgs = [m for m in messages if m.get("role") in ("user", "assistant")]
    combined = existing + new_msgs
    if len(combined) > MAX_CONTEXT:
        combined = combined[-MAX_CONTEXT:]
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(combined, f, ensure_ascii=False, indent=2)
        return len(combined)
    except Exception:
        return 0


def delete_memory(name: str) -> bool:
    """Delete Agent memory file."""
    path = memory_path(name)
    if os.path.exists(path):
        try:
            os.remove(path)
            return True
        except Exception:
            pass
    return False
