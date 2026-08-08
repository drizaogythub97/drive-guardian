"""Testes da reconciliação/plano (SPEC.md §3; critérios F1 a/b/e)."""

from __future__ import annotations

from pathlib import Path

from core.config import SyncPair
from core.drive import DriveFile
from core.planner import (
    REASON_MISSING_LOCAL,
    REASON_MODIFIED,
    REASON_NEW,
    build_plan,
)
from core.state import State


def _pair(root: Path) -> SyncPair:
    return SyncPair(drive_folder_id="ROOT", local_path=root)


def _file(fid: str, name: str, md5: str, size: int = 10) -> DriveFile:
    return DriveFile(
        id=fid, name=name, mime_type="image/jpeg", md5=md5, size=size,
        modified_time="2026-01-01T00:00:00Z", drive_path=name,
    )


def test_first_scan_queues_everything(tmp_path: Path) -> None:
    """(a) 1º sync clona a árvore inteira: sem registros, tudo é 'novo'."""
    with State() as state:
        remote = [_file("A", "a.jpg", "m1"), _file("B", "b.jpg", "m2")]
        plan = build_plan(state, remote, _pair(tmp_path))
        assert len(plan.to_download) == 2
        assert {i.reason for i in plan.to_download} == {REASON_NEW}
        assert plan.bytes_to_download == 20


def test_second_scan_downloads_nothing(tmp_path: Path) -> None:
    """(b) 2º sync não baixa nada: registro synced + arquivo local presente."""
    root = tmp_path
    (root / "a.jpg").write_bytes(b"x")
    with State() as state:
        state.record_synced("A", "a.jpg", str(root / "a.jpg"), "m1", 10, "t")
        plan = build_plan(state, [_file("A", "a.jpg", "m1")], _pair(root))
        assert plan.to_download == []
        assert len(plan.synced) == 1


def test_changed_md5_is_queued_as_modified(tmp_path: Path) -> None:
    """(e) md5 diferente no Drive -> reenfileira como 'modificado'."""
    root = tmp_path
    (root / "a.jpg").write_bytes(b"x")
    with State() as state:
        state.record_synced("A", "a.jpg", str(root / "a.jpg"), "m1", 10, "t")
        plan = build_plan(state, [_file("A", "a.jpg", "m2")], _pair(root))
        assert len(plan.to_download) == 1
        assert plan.to_download[0].reason == REASON_MODIFIED


def test_missing_local_is_requeued(tmp_path: Path) -> None:
    """Registro synced mas arquivo sumiu do disco -> 'ausente-local'."""
    root = tmp_path
    with State() as state:
        state.record_synced("A", "a.jpg", str(root / "a.jpg"), "m1", 10, "t")
        plan = build_plan(state, [_file("A", "a.jpg", "m1")], _pair(root))
        assert len(plan.to_download) == 1
        assert plan.to_download[0].reason == REASON_MISSING_LOCAL


def test_google_native_is_skipped(tmp_path: Path) -> None:
    native = DriveFile(
        id="G", name="doc", mime_type="application/vnd.google-apps.document",
        md5=None, size=None, modified_time="t", drive_path="doc",
    )
    with State() as state:
        plan = build_plan(state, [native], _pair(tmp_path))
        assert plan.to_download == []
        assert len(plan.skipped_native) == 1


def test_build_plan_does_not_write(tmp_path: Path) -> None:
    """Plano é só leitura (base do --dry-run): não cria registros."""
    with State() as state:
        build_plan(state, [_file("A", "a.jpg", "m1")], _pair(tmp_path))
        assert state.count_by_status() == {}  # nenhuma linha criada
