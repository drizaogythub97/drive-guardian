"""Política de alertas (SPEC.md §4): crítico imediato, degradado só após 24h,
anti-spam persistido entre execuções."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from core.alerts import AlertManager
from core.errors import AuthError, CriticalError, DiskError
from core.notifier.base import PRIORITY_DEFAULT, PRIORITY_HIGH, Notifier
from core.state import State

LOG = logging.getLogger("test")


class SpyNotifier(Notifier):
    """Notificador de teste: registra tudo que sairia para o celular."""

    def __init__(self, enabled: bool = True, ok: bool = True) -> None:
        self.sent: list[tuple[str, str, str, str]] = []
        self._enabled = enabled
        self._ok = ok

    def notify(
        self, title: str, message: str, *, priority: str = PRIORITY_DEFAULT, tags: str = ""
    ) -> bool:
        self.sent.append((title, message, priority, tags))
        return self._ok

    @property
    def enabled(self) -> bool:
        return self._enabled


def test_critical_notifies_immediately_with_high_priority() -> None:
    spy = SpyNotifier()
    with State() as state:
        assert AlertManager(spy, state, LOG).critical(DiskError("O disco D: não foi encontrado."))

    _title, message, priority, _tags = spy.sent[0]
    assert priority == PRIORITY_HIGH
    assert "Conecte o disco" in message  # mensagem acionável, não só o erro


def test_message_leads_with_plain_language_not_jargon() -> None:
    """Quem lê no celular vê primeiro o que houve e o que fazer; jargão por último."""
    spy = SpyNotifier()
    with State() as state:
        AlertManager(spy, state, LOG).critical(
            AuthError("Service account info was not in the expected format")
        )

    message = spy.sent[0][1]
    first_line = message.splitlines()[0]
    assert first_line == "O backup parou: o app perdeu o acesso à pasta do Drive."
    assert message.index("O que fazer:") < message.index("Detalhe técnico:")
    # O detalhe técnico continua na mensagem, mas depois da orientação.
    assert message.index("Service account info") > message.index("O que fazer:")


def test_auth_error_message_is_actionable() -> None:
    spy = SpyNotifier()
    with State() as state:
        AlertManager(spy, state, LOG).critical(AuthError("Credencial inválida."))
    assert "compartilhada com a conta" in spy.sent[0][1]


def test_unknown_critical_still_gets_plain_headline() -> None:
    spy = SpyNotifier()
    with State() as state:
        AlertManager(spy, state, LOG).critical(CriticalError("boom"))
    assert spy.sent[0][1].startswith("O backup parou por um erro inesperado.")


def test_same_alert_is_not_repeated_inside_window() -> None:
    spy = SpyNotifier()
    with State() as state:
        alerts = AlertManager(spy, state, LOG)
        assert alerts.critical(DiskError("sumiu")) is True
        assert alerts.critical(DiskError("sumiu")) is False  # dedup
    assert len(spy.sent) == 1


def test_dedup_survives_new_process() -> None:
    """Um `sync` agendado não pode virar uma notificação por execução."""
    spy = SpyNotifier()
    with State() as state:
        assert AlertManager(spy, state, LOG).critical(DiskError("sumiu")) is True
        # Novo AlertManager = novo processo; a janela vem do banco, não da memória.
        assert AlertManager(spy, state, LOG).critical(DiskError("sumiu")) is False
    assert len(spy.sent) == 1


def test_alert_repeats_after_window() -> None:
    spy = SpyNotifier()
    with State() as state:
        AlertManager(spy, state, LOG, repeat_after_hours=6).critical(DiskError("sumiu"))
        # Envelhece o marcador para além da janela.
        old = (datetime.now(UTC) - timedelta(hours=7)).isoformat()
        state.connection.execute("UPDATE events SET ts=? WHERE category LIKE 'alerta:%'", (old,))
        state.connection.commit()
        assert AlertManager(spy, state, LOG, repeat_after_hours=6).critical(DiskError("sumiu"))
    assert len(spy.sent) == 2


def test_logged_message_has_no_internal_marker() -> None:
    """O log da UI mostra o texto que foi para o celular, sem prefixo técnico."""
    spy = SpyNotifier()
    with State() as state:
        AlertManager(spy, state, LOG).critical(DiskError("O disco D: sumiu."))
        rows = state.recent_events(limit=10)

    marker = next(r for r in rows if r["category"].startswith("alerta:"))
    assert marker["category"] == "alerta:disco"
    assert not marker["message"].startswith("[")
    assert marker["message"] == spy.sent[0][1]


def test_disabled_notifier_sends_nothing() -> None:
    spy = SpyNotifier(enabled=False)
    with State() as state:
        assert AlertManager(spy, state, LOG).critical(DiskError("sumiu")) is False
    assert spy.sent == []


def _fail_file(state: State, file_id: str, hours_ago: float) -> None:
    state.record_pending(file_id, f"{file_id}.jpg", f"/dst/{file_id}.jpg", "m", 1, "t")
    state.record_failed(file_id, "erro de rede")
    stamp = (datetime.now(UTC) - timedelta(hours=hours_ago)).isoformat()
    state.connection.execute(
        "UPDATE files SET first_failed_at=? WHERE file_id=?", (stamp, file_id)
    )
    state.connection.commit()


def test_degraded_ignores_recent_failures() -> None:
    spy = SpyNotifier()
    with State() as state:
        _fail_file(state, "A", hours_ago=2)
        assert AlertManager(spy, state, LOG).check_degraded() == 0
    assert spy.sent == []


def test_degraded_notifies_after_24h() -> None:
    spy = SpyNotifier()
    with State() as state:
        _fail_file(state, "A", hours_ago=30)
        _fail_file(state, "B", hours_ago=1)  # recente: não conta
        assert AlertManager(spy, state, LOG).check_degraded() == 1

    message = spy.sent[0][1]
    assert "A.jpg" in message
    assert "B.jpg" not in message


def test_success_clears_the_failure_clock() -> None:
    spy = SpyNotifier()
    with State() as state:
        _fail_file(state, "A", hours_ago=30)
        state.record_synced("A", "A.jpg", "/dst/A.jpg", "m", 1, "t")
        assert state.get_file("A").first_failed_at is None  # type: ignore[union-attr]
        assert AlertManager(spy, state, LOG).check_degraded() == 0
