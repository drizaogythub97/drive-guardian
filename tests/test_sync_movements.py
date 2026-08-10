"""Registro de movimentações no ciclo completo (pedido do dono, 10/08/2026):
tudo que acontece no Drive precisa ficar gravado para aparecer na UI —
inclusive o que **sumiu**, que a reconciliação por ``files.list`` não enxerga.

Regra inviolável 1: nada disso pode tocar no arquivo local.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest

from core.auth import Auth
from core.config import (
    AuthConfig,
    Config,
    HeartbeatConfig,
    LoggingConfig,
    NotificationsConfig,
    NtfyConfig,
    SyncConfig,
    SyncPair,
)
from core.drive import DriveFile
from core.logger import SqliteEventHandler
from core.notifier.base import NullNotifier
from core.planner import Plan
from core.state import STATUS_REMOTE_DELETED, STATUS_SYNCED, State
from core.sync import CycleReport, SyncEngine

LOG = logging.getLogger("test")


class FakeAuth(Auth):
    def credentials(self) -> object:
        return object()

    def account_label(self) -> str:
        return "fake@example.com"


def _config(dest: Path) -> Config:
    return Config(
        auth=AuthConfig(strategy="service_account", service_account_key=Path("k.json")),
        sync=SyncConfig(
            pairs=[SyncPair(drive_folder_id="ROOT", local_path=dest)],
            interval_minutes=30,
            bandwidth_limit_mbps=0,
            export_google_docs=False,
            export_formats={},
        ),
        notifications=NotificationsConfig(
            ntfy=NtfyConfig(enabled=False, server="https://ntfy.sh", topic=""),
            weekly_summary=False, summary_day="sunday", summary_hour=20,
        ),
        heartbeat=HeartbeatConfig(enabled=False, url=""),
        logging=LoggingConfig(),
    )


def _drive_file(file_id: str, name: str) -> DriveFile:
    return DriveFile(
        id=file_id, name=name, mime_type="image/jpeg", md5="m",
        size=10, modified_time="t", drive_path=name,
    )


def _logger_writing_to(state: State) -> logging.Logger:
    """Logger com o mesmo handler do app, para os eventos caírem no SQLite."""
    logger = logging.getLogger(f"test.movements.{id(state)}")
    logger.handlers.clear()
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(SqliteEventHandler(state))
    return logger


@pytest.fixture
def engine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Engine com o serviço do Drive trocado por um objeto inerte."""
    monkeypatch.setattr("core.sync.build_service", lambda _auth: object())

    def _make(state: State) -> SyncEngine:
        return SyncEngine(
            _config(tmp_path / "dst"), state, FakeAuth(), _logger_writing_to(state),
            notifier=NullNotifier(), sleep=lambda _s: None,
        )

    return _make


def test_remote_deletion_is_recorded_and_local_untouched(
    engine: Any, tmp_path: Path
) -> None:
    dest = tmp_path / "dst"
    dest.mkdir()
    local = dest / "sumido.jpg"
    local.write_bytes(b"conteudo original")

    with State() as state:
        state.record_synced("GONE", "sumido.jpg", str(local), "m", 17, "t")
        state.record_synced("KEEP", "fica.jpg", str(dest / "fica.jpg"), "m", 10, "t")

        plan = Plan(synced=[_drive_file("KEEP", "fica.jpg")])
        report = CycleReport()
        engine(state)._track_remote_changes(
            _config(dest).sync.pairs[0], plan, report
        )

        assert report.remote_deleted == 1
        assert state.get_file("GONE").status == STATUS_REMOTE_DELETED  # type: ignore[union-attr]
        assert state.get_file("KEEP").status == STATUS_SYNCED  # type: ignore[union-attr]

        # O evento fica no banco — é o que a UI vai listar.
        messages = [r["message"] for r in state.recent_events(limit=10)]
        assert any("Sumiu do Drive" in m and "sumido.jpg" in m for m in messages)

    # Regra inviolável 1: o arquivo local continua lá, intacto.
    assert local.exists()
    assert local.read_bytes() == b"conteudo original"


def test_file_returning_to_drive_is_restored(engine: Any, tmp_path: Path) -> None:
    dest = tmp_path / "dst"
    dest.mkdir()
    with State() as state:
        state.record_synced("BACK", "voltou.jpg", str(dest / "voltou.jpg"), "m", 10, "t")
        state.record_remote_deleted("BACK")

        plan = Plan(synced=[_drive_file("BACK", "voltou.jpg")])
        engine(state)._track_remote_changes(
            _config(dest).sync.pairs[0], plan, CycleReport()
        )

        assert state.get_file("BACK").status == STATUS_SYNCED  # type: ignore[union-attr]
        messages = [r["message"] for r in state.recent_events(limit=10)]
        assert any("Voltou a aparecer no Drive" in m for m in messages)


def test_deletion_is_not_recorded_twice(engine: Any, tmp_path: Path) -> None:
    dest = tmp_path / "dst"
    dest.mkdir()
    with State() as state:
        state.record_synced("GONE", "sumido.jpg", str(dest / "sumido.jpg"), "m", 10, "t")
        pair = _config(dest).sync.pairs[0]

        first = CycleReport()
        engine(state)._track_remote_changes(pair, Plan(), first)
        second = CycleReport()
        engine(state)._track_remote_changes(pair, Plan(), second)

        assert (first.remote_deleted, second.remote_deleted) == (1, 0)


def test_other_destinations_are_left_alone(engine: Any, tmp_path: Path) -> None:
    """Arquivo de outro par não pode ser marcado como sumido por este par."""
    dest = tmp_path / "dst"
    dest.mkdir()
    with State() as state:
        state.record_synced("OTHER", "x.jpg", str(tmp_path / "outro" / "x.jpg"), "m", 10, "t")

        report = CycleReport()
        engine(state)._track_remote_changes(_config(dest).sync.pairs[0], Plan(), report)

        assert report.remote_deleted == 0
        assert state.get_file("OTHER").status == STATUS_SYNCED  # type: ignore[union-attr]


def test_native_google_docs_do_not_count_as_deleted(engine: Any, tmp_path: Path) -> None:
    """Docs nativos são ignorados no download, mas existem no Drive."""
    dest = tmp_path / "dst"
    dest.mkdir()
    native = DriveFile(
        id="DOC", name="nota", mime_type="application/vnd.google-apps.document",
        md5=None, size=None, modified_time="t", drive_path="nota",
    )
    with State() as state:
        state.record_synced("DOC", "nota", str(dest / "nota"), None, None, "t")

        report = CycleReport()
        engine(state)._track_remote_changes(
            _config(dest).sync.pairs[0], Plan(skipped_native=[native]), report
        )
        assert report.remote_deleted == 0
