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
# Sumiu do Drive (lixeira/exclusão). A cópia local é mantida (regra inviolável 1);
# o status existe só para registro e exibição na UI.
STATUS_REMOTE_DELETED = "removido_no_drive"
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
    first_failed_at: str | None = None


@dataclass(frozen=True)
class CycleRow:
    """Linha da tabela ``cycles`` — um ciclo de sincronização já encerrado."""

    id: int
    started_at: str
    finished_at: str
    kind: str
    downloaded: int
    versioned: int
    failed: int
    remote_deleted: int
    bytes_downloaded: int
    ok: int
    error: str | None

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
  file_id       TEXT PRIMARY KEY,   -- ID do Drive (estável em renomes/moves)
  drive_path    TEXT NOT NULL,      -- caminho lógico atual no Drive
  local_path    TEXT NOT NULL,      -- caminho absoluto no disco
  md5           TEXT,               -- md5Checksum do Drive na última sync
  size          INTEGER,
  modified_time TEXT,               -- modifiedTime do Drive (RFC3339)
  status        TEXT NOT NULL,      -- synced | pending | downloading | failed | versioned
                                    -- | removido_no_drive
  fail_count    INTEGER DEFAULT 0,
  last_error    TEXT,
  updated_at    TEXT NOT NULL,
  first_failed_at TEXT              -- início da falha atual (Nível 2: >24h notifica)
);

CREATE TABLE IF NOT EXISTS sync_state (   -- singleton (id=1)
  id             INTEGER PRIMARY KEY CHECK (id=1),
  page_token     TEXT,             -- changes.list startPageToken corrente
  last_full_scan TEXT,             -- última reconciliação completa
  last_cycle_ok  TEXT,
  last_summary   TEXT              -- envio do último resumo semanal
);

CREATE TABLE IF NOT EXISTS events (       -- alimenta a aba de logs da UI e o resumo semanal
  id       INTEGER PRIMARY KEY AUTOINCREMENT,
  ts       TEXT NOT NULL,
  level    TEXT NOT NULL,          -- INFO | WARN | ERROR | CRITICAL
  category TEXT NOT NULL,          -- download | auth | disk | config | notify | cycle
  message  TEXT NOT NULL,
  file_id  TEXT
);

CREATE TABLE IF NOT EXISTS cycles (       -- um registro por ciclo (painel da UI + resumo)
  id             INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at     TEXT NOT NULL,
  finished_at    TEXT NOT NULL,
  kind           TEXT NOT NULL,    -- completo | incremental
  downloaded     INTEGER NOT NULL DEFAULT 0,
  versioned      INTEGER NOT NULL DEFAULT 0,
  failed         INTEGER NOT NULL DEFAULT 0,
  remote_deleted INTEGER NOT NULL DEFAULT 0,
  bytes_downloaded INTEGER NOT NULL DEFAULT 0,
  ok             INTEGER NOT NULL DEFAULT 1,
  error          TEXT
);

CREATE INDEX IF NOT EXISTS idx_files_status ON files(status);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_cycles_finished ON cycles(finished_at);
"""

# Colunas acrescentadas depois do schema original (Fase 2): aplicadas com ALTER TABLE
# em bancos que já existem, já que ``CREATE TABLE IF NOT EXISTS`` não as adicionaria.
_MIGRATIONS: tuple[tuple[str, str, str], ...] = (
    ("files", "first_failed_at", "ALTER TABLE files ADD COLUMN first_failed_at TEXT"),
    ("sync_state", "last_summary", "ALTER TABLE sync_state ADD COLUMN last_summary TEXT"),
)


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
        first_failed_at=row["first_failed_at"],
    )


def _row_to_cycle(row: sqlite3.Row) -> CycleRow:
    return CycleRow(
        id=row["id"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        kind=row["kind"],
        downloaded=row["downloaded"],
        versioned=row["versioned"],
        failed=row["failed"],
        remote_deleted=row["remote_deleted"],
        bytes_downloaded=row["bytes_downloaded"],
        ok=row["ok"],
        error=row["error"],
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
            self._migrate()

    def _migrate(self) -> None:
        """Aplica colunas novas em bancos criados por versões anteriores."""
        for table, column, ddl in _MIGRATIONS:
            existing = {r["name"] for r in self._conn.execute(f"PRAGMA table_info({table})")}
            if column not in existing:
                self._conn.execute(ddl)

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

    def get_last_cycle_ok(self) -> str | None:
        row = self._conn.execute("SELECT last_cycle_ok FROM sync_state WHERE id=1").fetchone()
        return row["last_cycle_ok"] if row else None

    def get_last_summary(self) -> str | None:
        row = self._conn.execute("SELECT last_summary FROM sync_state WHERE id=1").fetchone()
        return row["last_summary"] if row else None

    def set_last_summary(self, when: str | None = None) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE sync_state SET last_summary=? WHERE id=1", (when or _utcnow(),)
            )

    # --- Tabela cycles ----------------------------------------------------

    def record_cycle(
        self,
        *,
        started_at: str,
        kind: str,
        downloaded: int = 0,
        versioned: int = 0,
        failed: int = 0,
        remote_deleted: int = 0,
        bytes_downloaded: int = 0,
        ok: bool = True,
        error: str | None = None,
    ) -> None:
        """Registra um ciclo encerrado (alimenta o painel da UI e o resumo semanal)."""
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO cycles (started_at, finished_at, kind, downloaded, versioned,
                                    failed, remote_deleted, bytes_downloaded, ok, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (started_at, _utcnow(), kind, downloaded, versioned, failed,
                 remote_deleted, bytes_downloaded, int(ok), error),
            )

    def cycles_since(self, since: str) -> list[CycleRow]:
        rows = self._conn.execute(
            "SELECT * FROM cycles WHERE finished_at >= ? ORDER BY id", (since,)
        ).fetchall()
        return [_row_to_cycle(r) for r in rows]

    def recent_cycles(self, limit: int = 10) -> list[CycleRow]:
        rows = self._conn.execute(
            "SELECT * FROM cycles ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_cycle(r) for r in rows]

    # --- Consulta de eventos (aba Atividade da UI) ------------------------

    def recent_events(
        self, limit: int = 50, *, levels: tuple[str, ...] = (), category: str | None = None
    ) -> list[sqlite3.Row]:
        """Últimos eventos, opcionalmente filtrados por nível e categoria."""
        clauses: list[str] = []
        params: list[object] = []
        if levels:
            clauses.append(f"level IN ({','.join('?' * len(levels))})")
            params.extend(lv.upper() for lv in levels)
        if category:
            clauses.append("category = ?")
            params.append(category)
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        return list(
            self._conn.execute(f"SELECT * FROM events{where} ORDER BY id DESC LIMIT ?", params)
        )

    def count_events_since(self, since: str, *, levels: tuple[str, ...] = ()) -> int:
        clause = f" AND level IN ({','.join('?' * len(levels))})" if levels else ""
        params: list[object] = [since, *(lv.upper() for lv in levels)]
        row = self._conn.execute(
            f"SELECT COUNT(*) AS n FROM events WHERE ts >= ?{clause}", params
        ).fetchone()
        return int(row["n"])

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
                    first_failed_at=NULL,
                    updated_at=excluded.updated_at
                """,
                (file_id, drive_path, local_path, md5, size, modified_time,
                 STATUS_SYNCED, _utcnow()),
            )

    def record_failed(self, file_id: str, error: str) -> None:
        """Incrementa ``fail_count`` e guarda o último erro (status=failed).

        Carimba ``first_failed_at`` na primeira falha da sequência atual — é o que
        permite ao Nível 2 saber que um arquivo já falha há mais de 24h.
        """
        now = _utcnow()
        with self._conn:
            self._conn.execute(
                "UPDATE files SET status=?, fail_count=fail_count+1, last_error=?, updated_at=?, "
                "first_failed_at=COALESCE(first_failed_at, ?) WHERE file_id=?",
                (STATUS_FAILED, error, now, now, file_id),
            )

    def record_remote_deleted(self, file_id: str) -> None:
        """Marca que o arquivo sumiu do Drive. **Não** toca na cópia local."""
        with self._conn:
            self._conn.execute(
                "UPDATE files SET status=?, updated_at=? WHERE file_id=?",
                (STATUS_REMOTE_DELETED, _utcnow(), file_id),
            )

    def restore_remote_deleted(self, file_id: str) -> None:
        """Arquivo voltou a aparecer no Drive: volta a contar como sincronizado."""
        with self._conn:
            self._conn.execute(
                "UPDATE files SET status=?, updated_at=? WHERE file_id=? AND status=?",
                (STATUS_SYNCED, _utcnow(), file_id, STATUS_REMOTE_DELETED),
            )

    def failing_since(self, cutoff: str) -> list[FileRow]:
        """Arquivos em falha cuja primeira falha é anterior a ``cutoff`` (Nível 2)."""
        rows = self._conn.execute(
            "SELECT * FROM files WHERE status=? AND first_failed_at IS NOT NULL "
            "AND first_failed_at <= ? ORDER BY first_failed_at",
            (STATUS_FAILED, cutoff),
        ).fetchall()
        return [_row_to_file(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> State:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
