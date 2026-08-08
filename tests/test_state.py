"""Testes do banco de estado SQLite (SPEC.md §2)."""

from __future__ import annotations

from core.state import State


def test_schema_and_singleton_created() -> None:
    with State() as state:
        tables = {
            row["name"]
            for row in state.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {"files", "sync_state", "events"} <= tables

        row = state.connection.execute("SELECT COUNT(*) AS n FROM sync_state").fetchone()
        assert row["n"] == 1


def test_wal_mode_enabled() -> None:
    with State() as state:
        mode = state.connection.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode.lower() == "wal"


def test_record_event_persists() -> None:
    with State() as state:
        state.record_event("INFO", "cycle", "ciclo ok", file_id=None)
        state.record_event("ERROR", "disk", "disco cheio", file_id="abc")
        rows = state.connection.execute(
            "SELECT level, category, message FROM events ORDER BY id"
        ).fetchall()
        assert [r["level"] for r in rows] == ["INFO", "ERROR"]
        assert rows[1]["category"] == "disk"


def test_page_token_roundtrip() -> None:
    with State() as state:
        assert state.get_page_token() is None
        state.set_page_token("token-123")
        assert state.get_page_token() == "token-123"


def test_singleton_reopen_keeps_one_row(tmp_path_factory: object) -> None:
    # Reabrir o mesmo db não deve duplicar o singleton.
    with State() as state:
        db = state.db_path
    with State(db) as state2:
        row = state2.connection.execute("SELECT COUNT(*) AS n FROM sync_state").fetchone()
        assert row["n"] == 1
