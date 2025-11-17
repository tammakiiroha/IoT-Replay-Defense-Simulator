"""Definitions for the toy command set used in the simulation."""
from __future__ import annotations

from pathlib import Path
from typing import List

DEFAULT_COMMANDS: List[str] = [
    "FWD",
    "BACK",
    "LEFT",
    "RIGHT",
    "STOP",
]


def load_command_sequence(path: str | Path) -> List[str]:
    """Load a command trace from a text file.

    Each non-empty line is treated as one command token. Blank lines and lines
    starting with '#' are ignored to allow inline comments in the trace file.
    """

    trace_path = Path(path)
    if not trace_path.exists():
        raise FileNotFoundError(f"Command trace not found: {trace_path}")

    commands: List[str] = []
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        commands.append(stripped)

    if not commands:
        raise ValueError(f"Command trace {trace_path} is empty")

    return commands
