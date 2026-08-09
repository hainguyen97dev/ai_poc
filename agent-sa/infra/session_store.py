"""SQLite implementation of domain.ports.SessionRepository.

Stdlib-only (sqlite3) — no new dependency. A fresh connection is opened per
call rather than held open, since FastAPI's sync route handlers each run in
their own thread-pool thread and sqlite3 connections aren't safe to share
across threads.

Path resolution mirrors infra/architecture_context.py: an env var override,
a Docker-friendly cwd() candidate, and a local-source-tree fallback — except
here we *create* the directory (this store writes; architecture_context.py
only reads).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional, Sequence

from domain.session import ChatMessage, DraftVersionRecord, Session, UsageStats

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    requirement_id TEXT,
    subject_ref TEXT NOT NULL,
    status TEXT NOT NULL,
    request_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS draft_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    version_no INTEGER NOT NULL,
    analysis_id TEXT NOT NULL,
    status TEXT NOT NULL,
    content TEXT NOT NULL,
    assumptions_count INTEGER NOT NULL,
    questions_count INTEGER NOT NULL,
    risks_count INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    reasoning TEXT
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    reasoning TEXT
);
"""

# CREATE TABLE IF NOT EXISTS is a no-op against a table that already exists
# (e.g. a dev data/sessions.db from before this column was added) — these
# ALTERs backfill it on such databases. Harmless / already-satisfied on a
# fresh DB, since the CREATE above already includes the column there.
_MIGRATIONS = (
    "ALTER TABLE draft_versions ADD COLUMN reasoning TEXT",
    "ALTER TABLE messages ADD COLUMN reasoning TEXT",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_candidates() -> Iterator[Path]:
    configured = os.getenv("ADA_DATA_DIR")
    if configured:
        yield Path(configured).expanduser()

    # Docker runs with WORKDIR=/app; docker-compose mounts ../data there.
    yield Path.cwd() / "data"

    # Local source tree: repo/agent-sa/infra/session_store.py -> repo/data.
    yield Path(__file__).resolve().parents[2] / "data"


def resolve_data_dir(directory: Optional[Path] = None) -> Path:
    """Pick (and create) the shared data directory.

    Mirrors resolve_current_architecture_dir's preference order: an already-
    existing candidate wins first, so a directory created on a prior run is
    found again regardless of the process's current cwd (which local dev
    commands vary — `python main.py` from ada-service/ vs pytest's rootdir at
    agent-sa/ vs Docker's /app — unlike the Docker cwd()/"data" candidate,
    which is reliably /app). Only on a genuinely first run, with no candidate
    yet on disk, do we create one — the last candidate, since it's anchored
    to this file's location rather than to cwd, so it's the same directory
    every time regardless of where the process was launched from.
    """
    if directory is not None:
        resolved = directory.resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        return resolved

    candidates = list(_default_candidates())
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_dir():
            return resolved

    fallback = candidates[-1].resolve()
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


class SqliteSessionRepository:
    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = db_path or (resolve_data_dir() / "sessions.db")
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)
            for migration in _MIGRATIONS:
                try:
                    conn.execute(migration)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e):
                        raise

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def create_session(
        self,
        session_id: str,
        *,
        task_type: str,
        requirement_id: Optional[str],
        subject_ref: str,
        request_json: str,
    ) -> Session:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions "
                "(id, task_type, requirement_id, subject_ref, status, request_json, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, 'ACTIVE', ?, ?, ?)",
                (session_id, task_type, requirement_id, subject_ref, request_json, now, now),
            )
        session = self.get_session(session_id)
        assert session is not None  # just inserted it
        return session

    def add_draft_version(
        self,
        session_id: str,
        *,
        analysis_id: str,
        status: str,
        content: str,
        assumptions_count: int,
        questions_count: int,
        risks_count: int,
        reasoning: Optional[str] = None,
    ) -> DraftVersionRecord:
        now = _now()
        with self._connect() as conn:
            (next_version,) = conn.execute(
                "SELECT COALESCE(MAX(version_no), 0) + 1 FROM draft_versions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
            conn.execute(
                "INSERT INTO draft_versions "
                "(session_id, version_no, analysis_id, status, content, "
                " assumptions_count, questions_count, risks_count, created_at, reasoning) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_id,
                    next_version,
                    analysis_id,
                    status,
                    content,
                    assumptions_count,
                    questions_count,
                    risks_count,
                    now,
                    reasoning,
                ),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        return DraftVersionRecord(
            version_no=next_version,
            analysis_id=analysis_id,
            status=status,
            content=content,
            assumptions_count=assumptions_count,
            questions_count=questions_count,
            risks_count=risks_count,
            created_at=now,
            reasoning=reasoning,
        )

    def add_message(
        self, session_id: str, role: str, content: str, *, reasoning: Optional[str] = None
    ) -> ChatMessage:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages (session_id, role, content, created_at, reasoning) VALUES (?, ?, ?, ?, ?)",
                (session_id, role, content, now, reasoning),
            )
            conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id))
        return ChatMessage(role=role, content=content, created_at=now, reasoning=reasoning)

    def get_session(self, session_id: str) -> Optional[Session]:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                return None
            versions = [
                DraftVersionRecord(
                    version_no=r["version_no"],
                    analysis_id=r["analysis_id"],
                    status=r["status"],
                    content=r["content"],
                    assumptions_count=r["assumptions_count"],
                    questions_count=r["questions_count"],
                    risks_count=r["risks_count"],
                    created_at=r["created_at"],
                    reasoning=r["reasoning"],
                )
                for r in conn.execute(
                    "SELECT * FROM draft_versions WHERE session_id = ? ORDER BY version_no",
                    (session_id,),
                ).fetchall()
            ]
            messages = [
                ChatMessage(
                    role=r["role"], content=r["content"], created_at=r["created_at"], reasoning=r["reasoning"]
                )
                for r in conn.execute(
                    "SELECT * FROM messages WHERE session_id = ? ORDER BY id",
                    (session_id,),
                ).fetchall()
            ]
        return Session(
            id=row["id"],
            task_type=row["task_type"],
            requirement_id=row["requirement_id"],
            subject_ref=row["subject_ref"],
            status=row["status"],
            request_json=row["request_json"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            versions=versions,
            messages=messages,
        )

    def list_sessions(self) -> Sequence[Session]:
        with self._connect() as conn:
            ids = [
                r["id"]
                for r in conn.execute("SELECT id FROM sessions ORDER BY updated_at DESC").fetchall()
            ]
        sessions = [self.get_session(session_id) for session_id in ids]
        return [s for s in sessions if s is not None]

    def get_usage_stats(self) -> UsageStats:
        with self._connect() as conn:
            by_task_type = {
                row["task_type"]: row["cnt"]
                for row in conn.execute(
                    "SELECT s.task_type AS task_type, COUNT(dv.id) AS cnt "
                    "FROM draft_versions dv JOIN sessions s ON dv.session_id = s.id "
                    "GROUP BY s.task_type"
                ).fetchall()
            }
            (chat_replies,) = conn.execute(
                "SELECT COUNT(*) FROM messages WHERE role = 'assistant'"
            ).fetchone()
        return UsageStats(by_task_type=by_task_type, chat_replies=chat_replies)
