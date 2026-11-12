"""Backward compatibility with the project's former name, incopilot.

The old names keep working for one release: INCOPILOT_* environment variables,
./incopilot.toml and ~/.incopilot/history.jsonl. The new names win when both exist.
"""

from __future__ import annotations

import os
from pathlib import Path

OLD_NAME = "incopilot"


def getenv(name: str, default: str | None = None) -> str | None:
    """Read FIRSTSIGNAL_<name>, falling back to INCOPILOT_<name>."""
    value = os.environ.get(f"FIRSTSIGNAL_{name}")
    if value:
        return value
    return os.environ.get(f"INCOPILOT_{name}", default)


def prefer_existing(new: Path, old: Path) -> Path:
    """Use `new` unless only the old-name file exists."""
    if not new.exists() and old.exists():
        return old
    return new
