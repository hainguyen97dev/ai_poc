"""Loads .env if present. No-ops cleanly if python-dotenv isn't installed or
the file doesn't exist — --dry-run and other dependency-light paths must keep
working with zero third-party packages installed, same as the anthropic /
httpx import guards in llm_gateway.py / minimax_gateway.py.
"""

from __future__ import annotations

from pathlib import Path


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(path)
