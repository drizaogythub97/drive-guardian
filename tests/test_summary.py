"""Resumo semanal: números vindos da tabela ``cycles`` e agendamento preguiçoso."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from core.config import NotificationsConfig, NtfyConfig
from core.state import State
from core.summary import build_summary, due, weekday_index


def _notif(weekly: bool = True, day: str = "sunday", hour: int = 20) -> NotificationsConfig:
    return NotificationsConfig(
        ntfy=NtfyConfig(enabled=True, server="https://ntfy.sh", topic="t"),
        weekly_summary=weekly,
        summary_day=day,
        summary_hour=hour,
    )


def _cycle(state: State, **kwargs: int) -> None:
    state.record_cycle(started_at=datetime.now(UTC).isoformat(), kind="completo", **kwargs)


def test_summary_aggregates_last_week() -> None:
    with State() as state:
        _cycle(state, downloaded=3, versioned=1, bytes_downloaded=1000, remote_deleted=2)
        _cycle(state, downloaded=2, failed=1, bytes_downloaded=500)
        report = build_summary(state)

    assert report.downloaded == 5
    assert report.versioned == 1
    assert report.failed == 1
    assert report.remote_deleted == 2
    assert report.bytes_downloaded == 1500
    assert report.cycles == 2


def test_summary_ignores_cycles_older_than_the_window() -> None:
    with State() as state:
        _cycle(state, downloaded=9)
        old = (datetime.now(UTC) - timedelta(days=10)).isoformat()
        state.connection.execute("UPDATE cycles SET finished_at=?", (old,))
        state.connection.commit()
        assert build_summary(state).downloaded == 0


def test_summary_message_mentions_pending_errors_and_kept_files() -> None:
    with State() as state:
        state.record_pending("A", "a.jpg", "/d/a.jpg", "m", 1, "t")
        state.record_failed("A", "erro")
        state.record_synced("B", "b.jpg", "/d/b.jpg", "m", 1, "t")
        state.record_remote_deleted("B")
        message = build_summary(state).as_message()

    assert "1 arquivo(s) com erro pendente" in message
    assert "1 arquivo(s)" in message.split("Total preservado")[1]


def test_weekday_index_accepts_pt_and_en() -> None:
    assert weekday_index("sunday") == weekday_index("domingo") == 6
    assert weekday_index("wednesday") == weekday_index("quarta") == 2
    assert weekday_index("zzz") == 6  # padrão: domingo


def test_due_is_false_before_scheduled_time() -> None:
    # Domingo 19h; agendado para domingo 20h.
    moment = datetime(2026, 8, 9, 19, tzinfo=UTC)
    assert moment.weekday() == 6
    with State() as state:
        assert due(_notif(), state, now=moment) is False


def test_due_is_true_after_scheduled_time_and_never_sent() -> None:
    moment = datetime(2026, 8, 9, 21, tzinfo=UTC)
    with State() as state:
        assert due(_notif(), state, now=moment) is True


def test_due_is_false_once_sent_this_week() -> None:
    moment = datetime(2026, 8, 9, 21, tzinfo=UTC)
    with State() as state:
        state.set_last_summary(datetime(2026, 8, 9, 20, 5, tzinfo=UTC).isoformat())
        assert due(_notif(), state, now=moment) is False


def test_due_is_true_again_next_week() -> None:
    with State() as state:
        state.set_last_summary(datetime(2026, 8, 9, 20, 5, tzinfo=UTC).isoformat())
        next_week = datetime(2026, 8, 16, 20, 30, tzinfo=UTC)
        assert due(_notif(), state, now=next_week) is True


def test_late_send_when_machine_was_off_on_schedule() -> None:
    """PC desligado no domingo 20h: o resumo sai no primeiro ciclo depois."""
    monday = datetime(2026, 8, 10, 9, tzinfo=UTC)
    with State() as state:
        assert due(_notif(), state, now=monday) is True


def test_due_respects_disabled_summary() -> None:
    with State() as state:
        assert due(_notif(weekly=False), state, now=datetime(2026, 8, 9, 21, tzinfo=UTC)) is False
