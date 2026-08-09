"""Load the repository's verified current-architecture baseline.

The loader is intentionally filesystem-only and dependency-free. ADA invokes
it per request so architects can update the baseline documents without
restarting the API service.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple

SUPPORTED_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml"}
DEFAULT_MAX_CHARS = 100_000


@dataclass(frozen=True)
class ArchitectureContext:
    root: Optional[Path]
    files: Tuple[str, ...] = ()
    content: str = ""
    truncated: bool = False

    @property
    def is_loaded(self) -> bool:
        return bool(self.content)


def _default_candidates() -> Iterable[Path]:
    configured = os.getenv("CURRENT_ARCHITECTURE_DIR")
    if configured:
        yield Path(configured).expanduser()

    # Docker runs with WORKDIR=/app and mounts the baseline at this path.
    yield Path.cwd() / "current-architecture"

    # Local source tree: repo/agent-sa/infra/architecture_context.py.
    yield Path(__file__).resolve().parents[2] / "current-architecture"


def resolve_current_architecture_dir(directory: Optional[Path] = None) -> Optional[Path]:
    candidates = (directory,) if directory is not None else _default_candidates()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_dir():
            return resolved
    return None


def load_current_architecture(
    directory: Optional[Path] = None, *, max_chars: int = DEFAULT_MAX_CHARS
) -> ArchitectureContext:
    root = resolve_current_architecture_dir(directory)
    if root is None:
        return ArchitectureContext(root=None)

    paths = sorted(
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_SUFFIXES
        and path.name.lower() != "readme.md"
    )

    sections = []
    loaded_files = []
    used = 0
    truncated = False

    for path in paths:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            continue
        relative = path.relative_to(root).as_posix()
        section = f"## Source: {relative}\n\n{text}"
        remaining = max_chars - used
        if remaining <= 0:
            truncated = True
            break
        if len(section) > remaining:
            section = section[:remaining].rstrip() + "\n\n[CURRENT ARCHITECTURE TRUNCATED]"
            truncated = True
        sections.append(section)
        loaded_files.append(relative)
        used += len(section)
        if truncated:
            break

    return ArchitectureContext(
        root=root,
        files=tuple(loaded_files),
        content="\n\n---\n\n".join(sections),
        truncated=truncated,
    )

