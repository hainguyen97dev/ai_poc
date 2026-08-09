"""Tests for SqliteSessionRepository — real SQLite against a temp file, no mocking."""

from __future__ import annotations

from pathlib import Path

from infra.session_store import SqliteSessionRepository


def _store(tmp_path: Path) -> SqliteSessionRepository:
    return SqliteSessionRepository(tmp_path / "sessions.db")


def test_create_session_and_first_draft_version_round_trip(tmp_path: Path):
    store = _store(tmp_path)

    store.create_session(
        "ADA-001",
        task_type="analyze_requirement",
        requirement_id="REQ-001",
        subject_ref="Integrate payment gateway",
        request_json='{"requirement_id": "REQ-001"}',
    )
    store.add_draft_version(
        "ADA-001",
        analysis_id="ADA-001",
        status="COMPLETED",
        content="## Draft v1",
        assumptions_count=1,
        questions_count=2,
        risks_count=0,
    )

    session = store.get_session("ADA-001")

    assert session is not None
    assert session.task_type == "analyze_requirement"
    assert session.requirement_id == "REQ-001"
    assert session.status == "ACTIVE"
    assert len(session.versions) == 1
    assert session.latest_version.version_no == 1
    assert session.latest_version.content == "## Draft v1"
    assert session.messages == []


def test_add_draft_version_increments_version_number(tmp_path: Path):
    store = _store(tmp_path)
    store.create_session(
        "ADA-002", task_type="draft_adr", requirement_id=None, subject_ref="ADR", request_json="{}"
    )
    store.add_draft_version(
        "ADA-002", analysis_id="ADA-002", status="COMPLETED", content="v1",
        assumptions_count=0, questions_count=0, risks_count=0,
    )
    store.add_draft_version(
        "ADA-002", analysis_id="ADA-002-R2", status="COMPLETED", content="v2",
        assumptions_count=0, questions_count=0, risks_count=0,
    )

    session = store.get_session("ADA-002")

    assert [v.version_no for v in session.versions] == [1, 2]
    assert session.latest_version.content == "v2"


def test_usage_stats_counts_draft_versions_by_task_type_and_chat_replies(tmp_path: Path):
    store = _store(tmp_path)

    # Session 1: draft_adr, v1 + one refine (2 draft_versions) + 1 chat exchange.
    store.create_session("S1", task_type="draft_adr", requirement_id=None, subject_ref="x", request_json="{}")
    store.add_draft_version(
        "S1", analysis_id="S1", status="COMPLETED", content="v1",
        assumptions_count=0, questions_count=0, risks_count=0,
    )
    store.add_message("S1", "user", "why?")
    store.add_message("S1", "assistant", "because")
    store.add_draft_version(
        "S1", analysis_id="S1-R2", status="COMPLETED", content="v2",
        assumptions_count=0, questions_count=0, risks_count=0,
    )

    # Session 2: analyze_requirement, v1 only, no chat.
    store.create_session("S2", task_type="analyze_requirement", requirement_id=None, subject_ref="y", request_json="{}")
    store.add_draft_version(
        "S2", analysis_id="S2", status="COMPLETED", content="v1",
        assumptions_count=0, questions_count=0, risks_count=0,
    )

    stats = store.get_usage_stats()

    assert stats.by_task_type == {"draft_adr": 2, "analyze_requirement": 1}
    assert stats.chat_replies == 1  # only the "assistant" message counts, not the "user" one
    assert stats.total == 4  # 2 + 1 draft_versions + 1 chat reply


def test_usage_stats_on_empty_store_is_all_zero(tmp_path: Path):
    store = _store(tmp_path)

    stats = store.get_usage_stats()

    assert stats.by_task_type == {}
    assert stats.chat_replies == 0
    assert stats.total == 0


def test_reasoning_is_persisted_and_defaults_to_none(tmp_path: Path):
    store = _store(tmp_path)
    store.create_session(
        "ADA-005", task_type="draft_adr", requirement_id=None, subject_ref="ADR", request_json="{}"
    )

    store.add_draft_version(
        "ADA-005", analysis_id="ADA-005", status="COMPLETED", content="v1",
        assumptions_count=0, questions_count=0, risks_count=0,
        reasoning="Considered on-premise constraint first.",
    )
    store.add_message("ADA-005", "user", "why?")  # no reasoning kwarg — should default to None
    store.add_message("ADA-005", "assistant", "because...", reasoning="Ruled out cloud options.")

    session = store.get_session("ADA-005")

    assert session.versions[0].reasoning == "Considered on-premise constraint first."
    assert session.messages[0].reasoning is None
    assert session.messages[1].reasoning == "Ruled out cloud options."


def test_opening_a_pre_reasoning_db_backfills_the_column(tmp_path: Path):
    """A dev data/sessions.db created before this feature existed lacks the
    reasoning columns — CREATE TABLE IF NOT EXISTS is a no-op there, so the
    ALTER TABLE migrations in SqliteSessionRepository.__init__ must backfill
    it rather than crash on the next INSERT."""
    import sqlite3

    db_path = tmp_path / "legacy.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sessions (
            id TEXT PRIMARY KEY, task_type TEXT, requirement_id TEXT, subject_ref TEXT,
            status TEXT, request_json TEXT, created_at TEXT, updated_at TEXT
        );
        CREATE TABLE draft_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, version_no INTEGER,
            analysis_id TEXT, status TEXT, content TEXT, assumptions_count INTEGER,
            questions_count INTEGER, risks_count INTEGER, created_at TEXT
        );
        CREATE TABLE messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT, role TEXT,
            content TEXT, created_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()

    store = SqliteSessionRepository(db_path)  # must not raise
    store.create_session(
        "ADA-006", task_type="draft_adr", requirement_id=None, subject_ref="ADR", request_json="{}"
    )
    store.add_draft_version(
        "ADA-006", analysis_id="ADA-006", status="COMPLETED", content="v1",
        assumptions_count=0, questions_count=0, risks_count=0, reasoning="post-migration reasoning",
    )

    session = store.get_session("ADA-006")
    assert session.versions[0].reasoning == "post-migration reasoning"


def test_add_message_appends_in_order(tmp_path: Path):
    store = _store(tmp_path)
    store.create_session(
        "ADA-003", task_type="gap_impact_analysis", requirement_id=None, subject_ref="CR", request_json="{}"
    )

    store.add_message("ADA-003", "user", "What about the legacy DB?")
    store.add_message("ADA-003", "assistant", "It stays read-only during migration.")

    session = store.get_session("ADA-003")

    assert [(m.role, m.content) for m in session.messages] == [
        ("user", "What about the legacy DB?"),
        ("assistant", "It stays read-only during migration."),
    ]


def test_get_session_returns_none_for_unknown_id(tmp_path: Path):
    store = _store(tmp_path)

    assert store.get_session("does-not-exist") is None


def test_list_sessions_orders_most_recently_updated_first(tmp_path: Path):
    store = _store(tmp_path)
    store.create_session("ADA-OLD", task_type="draft_adr", requirement_id=None, subject_ref="old", request_json="{}")
    store.create_session("ADA-NEW", task_type="draft_adr", requirement_id=None, subject_ref="new", request_json="{}")
    # Touch ADA-OLD again so it becomes the most recently updated.
    store.add_message("ADA-OLD", "user", "follow-up")

    ids = [s.id for s in store.list_sessions()]

    assert ids[0] == "ADA-OLD"
    assert "ADA-NEW" in ids


def test_reopening_same_db_path_persists_across_instances(tmp_path: Path):
    db_path = tmp_path / "sessions.db"
    SqliteSessionRepository(db_path).create_session(
        "ADA-004", task_type="draft_adr", requirement_id=None, subject_ref="persisted", request_json="{}"
    )

    reopened = SqliteSessionRepository(db_path).get_session("ADA-004")

    assert reopened is not None
    assert reopened.subject_ref == "persisted"
