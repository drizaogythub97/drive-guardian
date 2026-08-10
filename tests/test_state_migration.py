"""Migração do schema: um banco criado na Fase 1 (já com 118 arquivos reais no
disco do dono) precisa ganhar as colunas/tabelas da Fase 2 sem perder nada.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from core.state import STATUS_SYNCED, State

# Schema exatamente como era antes da Fase 2.
_OLD_SCHEMA = """
CREATE TABLE files (
  file_id TEXT PRIMARY KEY, drive_path TEXT NOT NULL, local_path TEXT NOT NULL,
  md5 TEXT, size INTEGER, modified_time TEXT, status TEXT NOT NULL,
  fail_count INTEGER DEFAULT 0, last_error TEXT, updated_at TEXT NOT NULL
);
CREATE TABLE sync_state (
  id INTEGER PRIMARY KEY CHECK (id=1), page_token TEXT,
  last_full_scan TEXT, last_cycle_ok TEXT
);
CREATE TABLE events (
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL, level TEXT NOT NULL,
  category TEXT NOT NULL, message TEXT NOT NULL, file_id TEXT
);
"""


def _legacy_db(path: Path) -> None:
    conn = sqlite3.connect(str(path))
    with conn:
        conn.executescript(_OLD_SCHEMA)
        conn.execute(
            "INSERT INTO sync_state (id, page_token, last_full_scan, last_cycle_ok) "
            "VALUES (1, '131', '2026-08-10T13:00:00+00:00', '2026-08-10T13:00:00+00:00')"
        )
        conn.execute(
            "INSERT INTO files (file_id, drive_path, local_path, md5, size, modified_time, "
            "status, fail_count, last_error, updated_at) "
            "VALUES ('F1', 'foto.jpg', 'D:/dst/foto.jpg', 'abc', 10, 't', ?, 0, NULL, 'u')",
            (STATUS_SYNCED,),
        )
    conn.close()


def test_migration_adds_columns_and_keeps_data(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _legacy_db(db)

    with State(db) as state:
        row = state.get_file("F1")
        assert row is not None
        assert row.md5 == "abc"          # dado antigo preservado
        assert row.first_failed_at is None  # coluna nova, vazia
        assert state.get_page_token() == "131"
        assert state.get_last_summary() is None

        # A tabela nova existe e é usável.
        state.record_cycle(started_at="2026-08-10T14:00:00+00:00", kind="completo", downloaded=1)
        assert len(state.recent_cycles()) == 1


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "state.db"
    _legacy_db(db)
    with State(db):
        pass
    with State(db) as state:  # abrir de novo não pode tentar re-adicionar colunas
        assert state.get_file("F1") is not None


def test_fresh_database_has_all_columns(tmp_path: Path) -> None:
    with State(tmp_path / "novo.db") as state:
        cols = {r["name"] for r in state.connection.execute("PRAGMA table_info(files)")}
        assert "first_failed_at" in cols
        tables = {
            r["name"]
            for r in state.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"files", "sync_state", "events", "cycles"} <= tables
