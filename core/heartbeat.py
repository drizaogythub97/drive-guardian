"""Heartbeat para healthchecks.io ao fim de cada ciclo bem-sucedido (SPEC.md §4).

O serviço alerta sozinho quando o ping **para** de chegar — é assim que se descobre
que o app morreu ou que a máquina desligou (critério de aceite da Fase 2). Por isso
o ping só sai depois de um ciclo realmente bem-sucedido; ciclo com erro manda
``/fail``, que dispara o alerta na hora.

Como o notificador, nunca levanta exceção: heartbeat é observabilidade, não backup.
"""

from __future__ import annotations

import logging

import requests

from core.config import HeartbeatConfig

_TIMEOUT_SECONDS = 10


class Heartbeat:
    """Cliente do healthchecks.io (ou compatível) com endpoints ``/`` e ``/fail``."""

    def __init__(
        self,
        config: HeartbeatConfig,
        logger: logging.Logger,
        *,
        session: requests.Session | None = None,
        timeout: int = _TIMEOUT_SECONDS,
    ) -> None:
        self._url = config.url.rstrip("/")
        self._enabled = config.enabled and bool(self._url)
        self._log = logger
        self._session = session or requests.Session()
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return self._enabled

    def ping(self) -> bool:
        """Sinaliza ciclo bem-sucedido."""
        return self._send(self._url, "ok")

    def ping_fail(self, message: str = "") -> bool:
        """Sinaliza falha — o healthchecks alerta imediatamente."""
        return self._send(f"{self._url}/fail", "falha", body=message)

    def _send(self, url: str, kind: str, body: str = "") -> bool:
        if not self._enabled:
            return False
        try:
            response = self._session.post(
                url, data=body.encode("utf-8"), timeout=self._timeout
            )
            response.raise_for_status()
        except Exception as exc:
            self._log.warning(
                "Falha ao enviar heartbeat (%s): %s", kind, exc, extra={"category": "notify"}
            )
            return False
        self._log.debug("Heartbeat (%s) enviado.", kind, extra={"category": "notify"})
        return True
