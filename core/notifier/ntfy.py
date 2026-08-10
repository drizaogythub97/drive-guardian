"""Notificador ntfy.sh (SPEC.md §4) — alertas no celular, custo zero.

Publica em ``<server>/<topic>`` via POST. O tópico funciona como senha (por isso o
sufixo aleatório na config), então nada de valores previsíveis.

Falha de envio **não** propaga: só vira log de aviso (ver ``notifier.base``).
"""

from __future__ import annotations

import logging

import requests

from core.notifier.base import PRIORITY_DEFAULT, Notifier

# Timeout curto: notificar é secundário, não pode travar o ciclo de backup.
_TIMEOUT_SECONDS = 10


class NtfyNotifier(Notifier):
    """Envia notificações para um tópico ntfy."""

    def __init__(
        self,
        server: str,
        topic: str,
        logger: logging.Logger,
        *,
        enabled: bool = True,
        session: requests.Session | None = None,
        timeout: int = _TIMEOUT_SECONDS,
    ) -> None:
        self._server = server.rstrip("/")
        self._topic = topic
        self._log = logger
        self._enabled = enabled and bool(topic)
        self._session = session or requests.Session()
        self._timeout = timeout

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def url(self) -> str:
        return f"{self._server}/{self._topic}"

    def notify(
        self, title: str, message: str, *, priority: str = PRIORITY_DEFAULT, tags: str = ""
    ) -> bool:
        if not self._enabled:
            return False

        headers = {"Title": title, "Priority": priority}
        if tags:
            headers["Tags"] = tags
        try:
            response = self._session.post(
                self.url,
                data=message.encode("utf-8"),
                headers=headers,
                timeout=self._timeout,
            )
            response.raise_for_status()
        except Exception as exc:  # rede fora, ntfy fora: só registra
            self._log.warning(
                "Falha ao enviar notificação ntfy: %s", exc, extra={"category": "notify"}
            )
            return False

        self._log.info("Notificação enviada: %s", title, extra={"category": "notify"})
        return True
