"""Notificador ntfy e heartbeat: envio correto e falha que nunca propaga."""

from __future__ import annotations

import logging
from typing import Any

from core.config import HeartbeatConfig, NotificationsConfig, NtfyConfig
from core.heartbeat import Heartbeat
from core.notifier import build_notifier
from core.notifier.base import PRIORITY_HIGH, NullNotifier
from core.notifier.ntfy import NtfyNotifier

LOG = logging.getLogger("test")


class _Response:
    def __init__(self, status: int = 200) -> None:
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Sessão ``requests`` falsa: grava as chamadas e devolve o status pedido."""

    def __init__(self, status: int = 200, boom: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self._status = status
        self._boom = boom

    def post(self, url: str, **kwargs: Any) -> _Response:
        self.calls.append({"url": url, **kwargs})
        if self._boom:
            raise ConnectionError("rede fora")
        return _Response(self._status)


def _ntfy(session: FakeSession, enabled: bool = True) -> NtfyNotifier:
    return NtfyNotifier("https://ntfy.sh/", "topico-secreto", LOG, enabled=enabled,
                        session=session)


def test_ntfy_posts_to_topic_with_headers() -> None:
    session = FakeSession()
    assert _ntfy(session).notify("Título", "mensagem", priority=PRIORITY_HIGH, tags="warning")

    call = session.calls[0]
    assert call["url"] == "https://ntfy.sh/topico-secreto"
    assert call["data"] == b"mensagem"
    assert call["headers"]["Title"] == "Título"
    assert call["headers"]["Priority"] == PRIORITY_HIGH
    assert call["headers"]["Tags"] == "warning"


def test_ntfy_network_failure_never_raises() -> None:
    session = FakeSession(boom=True)
    assert _ntfy(session).notify("t", "m") is False


def test_ntfy_http_error_never_raises() -> None:
    session = FakeSession(status=500)
    assert _ntfy(session).notify("t", "m") is False


def test_ntfy_disabled_sends_nothing() -> None:
    session = FakeSession()
    notifier = _ntfy(session, enabled=False)
    assert notifier.enabled is False
    assert notifier.notify("t", "m") is False
    assert session.calls == []


def test_build_notifier_respects_config() -> None:
    off = NotificationsConfig(
        ntfy=NtfyConfig(enabled=False, server="https://ntfy.sh", topic="x"),
        weekly_summary=False, summary_day="sunday", summary_hour=20,
    )
    assert isinstance(build_notifier(off, LOG), NullNotifier)

    on = NotificationsConfig(
        ntfy=NtfyConfig(enabled=True, server="https://ntfy.sh", topic="x"),
        weekly_summary=False, summary_day="sunday", summary_hour=20,
    )
    assert isinstance(build_notifier(on, LOG), NtfyNotifier)


def test_heartbeat_pings_success_and_failure() -> None:
    session = FakeSession()
    hb = Heartbeat(
        HeartbeatConfig(enabled=True, url="https://hc-ping.com/uuid/"), LOG, session=session
    )
    assert hb.ping()
    assert hb.ping_fail("disco ausente")
    assert session.calls[0]["url"] == "https://hc-ping.com/uuid"
    assert session.calls[1]["url"] == "https://hc-ping.com/uuid/fail"
    assert session.calls[1]["data"] == b"disco ausente"


def test_heartbeat_disabled_and_failure_are_silent() -> None:
    off = Heartbeat(HeartbeatConfig(enabled=False, url=""), LOG, session=FakeSession())
    assert off.enabled is False
    assert off.ping() is False

    broken = Heartbeat(
        HeartbeatConfig(enabled=True, url="https://hc-ping.com/uuid"),
        LOG,
        session=FakeSession(boom=True),
    )
    assert broken.ping() is False
