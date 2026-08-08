"""Banco de estado SQLite — fonte da verdade da idempotência (SPEC.md §2).

Tabelas: ``files``, ``sync_state`` (singleton id=1) e ``events``. Modo WAL.
O schema é criado sob demanda (idempotente) na primeira conexão.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from core.paths import state_db_path

# Estados possíveis de um arquivo (coluna files.status).
STATUS_SYNCED = "synced"
STATUS_PENDING = "pending"
STATUS_DOWNLOADING = "downloading"
STATUS_FAILED = "failed"
STATUS_VERSIONED = "versioned"
QUEUEABLE = (STATUS_PENDING, STATUS_DOWNLOADING, STATUS_FAILED)


@dataclass(frozen=True)
class FileRow:
    """Linha da tabela ``files`` já tipada."""

    file_id: str
    drive_path: str
    local_path: str
    md5: str | None
    size: int | None
    modified_time: str | None
    status: str
    fail_count: int
    last_error: str | None
    updated_at: str

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
  file_id       TEXT PRIMARY KEY,   -- ID do Drive (estável em renomes/moves)
  drive_path    TEXT NOT NULL,      -- caminho lógico atual no Drive
  local_path    TEXT NOT NULL,      -- caminho absoluto no disco
  md5           TEXT,               -- md5Checksum do Drive na última sync
  size          INTEGER,
  modified_time TEXT,               -- modifiedTime do Drive (RFC3339)
  status        TEXT NOT NULL,      -- synced | pending | downloading | failed | versioned
  fail_count    INTEGER DEFAULT 0,
  last_error    TEXT,
  updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sync_state (   -- singleton (id=1)
  id             INTEGER PRIMARY KEY CHECK (id=1),
  page_token     TEXT,             -- changes.list startPageToken corrente
  last_full_scan TEXT,             -- última reconciliação completa
  last_cycle_ok  TEXT
);

CREATE TABLE IF NOT EXISTS events (       -- alimenta a aba de logs da UI e o resumo semanal
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       TEXT NOT NULL,
  level    TEXT NOT NULL,          -- INFO | WARN | ERROR | CRITICAL
  category TEXT NOT NULL,          -- download | auth | disk | config | notify | cycle
  message  TEXT NOT NULL,
  file_id  TEXT
);

CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


def _utcnow() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_file(row: sqlite3.Row) -> FileRow:
    return FileRow(
        file_id=row["file_id"],
        drive_path=row["drive_path"],
        local_path=row["local_path"],
        md5=row["md5"],
        size=row["size"],
        modified_time=row["modified_time"],
        status=row["status"],
        fail_count=row["fail_count"],
        last_error=row["last_error"],
        updated_at=row["updated_at"],
    )


class State:
    """Wrapper fino sobre a conexão SQLite com o schema garantido."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else state_db_path()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(SCHEMA)
            self._conn.execute(
                "INSERT OR IGNORE INTO sync_state (id, page_token, last_full_scan, last_cycle_ok) "
                "VALUES (1, NULL, NULL, NULL)"
            )

    @property
    def connection(self) -> sqlite3.Connection:
        return self._conn

    def record_event(
        self, level: str, category: str, message: str, file_id: str | None = None
    ) -> None:
        """Persiste um evento (consumido pela UI e pelo resumo semanal)."""
        with self._conn:
            self._conn.execute(
                "INSERT INTO events (ts, level, category, message, file_id) VALUES (?, ?, ?, ?, ?)",
                (_utcnow(), level.upper(), category, message, file_id),
            )

    def get_page_token(self) -> str | None:
        row = self._conn.execute("SELECT page_token FROM sync_state WHERE id=1").fetchone()
        return row["page_token"] if row else None

    def set_page_token(self, token: str) -> None:
        with self._conn:
            self._conn.execute("UPDATE sync_state SET page_token=? WHERE id=1", (token,))

    def mark_full_scan(self) -> None:
        with self._conn:
            self._conn.execute("UPDATE sync_state SET last_full_scan=? WHERE id=1", (_utcnow(),))

    def mark_cycle_ok(self) -> None:
        with self._conn:
            self._conn.execute("UPDATE sync_state SET last_cycle_ok=? WHERE id=1", (_utcnow(),))

    # --- Tabela files -----------------------------------------------------

    def get_file(self, file_id: str) -> FileRow | None:
        row = self._conn.execute("SELECT * FROM files WHERE file_id=?", (file_id,)).fetchone()
        return _row_to_file(row) if row is not None else None

    def files_by_status(self, *statuses: str) -> list[FileRow]:
        if not statuses:
            rows = self._conn.execute("SELECT * FROM files").fetchall()
        else:
            placeholders = ",".join("?" * len(statuses))
            rows = self._conn.execute(
                f"SELECT * FROM files WHERE status IN ({placeholders})", statuses
            ).fetchall()
        return [_row_to_file(r) for r in rows]

    def count_by_status(self) -> dict[str, int]:
        rows = self._conn.execute(
            "SELECT status, COUNT(*) AS n FROM files GROUP BY status"
        ).fetchall()
        return {r["status"]: r["n"] for r in rows}

    def record_pending(
        self,
        file_id: str,
        drive_path: str,
        local_path: str,
        md5: str | None,
        size: int | None,
        modified_time: str | None,
    ) -> None:
        """Marca um arquivo como na fila, preservando ``fail_count`` existente."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO files (file_id, drive_path, local_path, md5, size, modified_time,
                                   status, fail_count, last_error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    drive_path=excluded.drive_path,
                    local_path=excluded.local_path,
                    md5=excluded.md5,
                    size=excluded.size,
                    modified_time=excluded.modified_time,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (file_id, drive_path, local_path, md5, size, modified_time,
                 STATUS_PENDING, _utcnow()),
            )

    def record_synced(
        self,
        file_id: str,
        drive_path: str,
        local_path: str,
        md5: str | None,
        size: int | None,
        modified_time: str | None,
    ) -> None:
        """Marca um arquivo como sincronizado (zera falhas)."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO files (file_id, drive_path, local_path, md5, size, modified_time,
                                   status, fail_count, last_error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?)
                ON CONFLICT(file_id) DO UPDATE SET
                    drive_path=excluded.drive_path,
                    local_path=excluded.local_path,
                    md5=excluded.md5,
                    size=excluded.size,
                    modified_time=excluded.modified_time,
                    status=excluded.status,
                    fail_count=0,
                    last_error=NULL,
                    updated_at=excluded.updated_at
                """,
                (file_id, drive_path, local_path, md5, size, modified_time,
                 STATUS_SYNCED, _utcnow()),
            )

    def record_failed(self, file_id: str, error: str) -> None:
        """Incrementa ``fail_count`` e guarda o último erro (status=failed)."""
        with self._conn:
            self._conn.execute(
                "UPDATE files SET status=?, fail_count=fail_count+1, last_error=?, updated_at=? "
                "WHERE file_id=?",
                (STATUS_FAILED, error, _utcnow(), file_id),
            )

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> State:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
