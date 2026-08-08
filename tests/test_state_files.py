"""Testes do CRUD da tabela files (SPEC.md §2)."""

from __future__ import annotations

from core.state import STATUS_FAILED, STATUS_PENDING, STATUS_SYNCED, State


def test_record_pending_then_synced() -> None:
    with State() as state:
        state.record_pending("A", "a.jpg", "/x/a.jpg", "m1", 10, "t")
        row = state.get_file("A")
        assert row is not None and row.status == STATUS_PENDING

        state.record_synced("A", "a.jpg", "/x/a.jpg", "m1", 10, "t")
        row = state.get_file("A")
        assert row is not None and row.status == STATUS_SYNCED
        assert row.fail_count == 0 and row.last_error is None


def test_record_failed_increments() -> None:
    with State() as state:
        state.record_pending("A", "a.jpg", "/x/a.jpg", "m1", 10, "t")
        state.record_failed("A", "erro 1")
        state.record_failed("A", "erro 2")
        row = state.get_file("A")
        assert row is not None
        assert row.status == STATUS_FAILED
        assert row.fail_count == 2
        assert row.last_error == "erro 2"


def test_synced_after_failures_resets_fail_count() -> None:
    with State() as state:
        state.record_pending("A", "a.jpg", "/x/a.jpg", "m1", 10, "t")
        state.record_failed("A", "erro")
        state.record_synced("A", "a.jpg", "/x/a.jpg", "m1", 10, "t")
        row = state.get_file("A")
        assert row is not None and row.fail_count == 0


def test_files_by_status_and_counts() -> None:
    with State() as state:
        state.record_synced("A", "a", "/a", "m", 1, "t")
        state.record_pending("B", "b", "/b", "m", 1, "t")
        assert {r.file_id for r in state.files_by_status(STATUS_SYNCED)} == {"A"}
        assert state.count_by_status() == {STATUS_SYNCED: 1, STATUS_PENDING: 1}
