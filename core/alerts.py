"""Política de alertas do SPEC.md §4 — o que notifica, quando e com que texto.

Concentra num só lugar as três decisões que o resto do código não deve tomar:

- **Nível 3 (crítico):** notifica na hora, ``priority=high``.
- **Nível 2 (degradado):** só notifica se o arquivo já falha há mais de 24 h.
- **Anti-spam:** o mesmo alerta não se repete antes de ``repeat_after_hours``.

A deduplicação é persistida na tabela ``events`` (marcador ``[alerta:<chave>]``), e não
em memória, para sobreviver a reinícios do processo — um `sync` agendado de hora em hora
não pode virar uma notificação de hora em hora.

Mensagens em PT-BR e **acionáveis**: dizem o que fazer, não só o que quebrou.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from core.errors import (
    LEVEL_CRITICAL,
    AuthError,
    ConfigError,
    DiskError,
    classify,
)
from core.notifier.base import PRIORITY_DEFAULT, PRIORITY_HIGH, Notifier
from core.state import State

# Um arquivo precisa estar falhando por mais que isso para virar notificação (Nível 2).
DEGRADED_AFTER_HOURS = 24
# Janela de silêncio para o mesmo alerta.
REPEAT_AFTER_HOURS = 6

# Categoria do evento que marca "este alerta já saiu" (base da janela de silêncio).
# Fica na coluna ``category`` e não no texto: assim a mensagem gravada é exatamente
# a que foi para o celular, sem prefixo técnico aparecendo no log da UI.
_MARKER_CATEGORY = "alerta"
_TITLE = "Drive Guardian"


def _marker_category(key: str) -> str:
    return f"{_MARKER_CATEGORY}:{key}"


def _now() -> datetime:
    return datetime.now(UTC)


# Para cada erro crítico: (chave de dedup, o que aconteceu, o que fazer). O jargão
# técnico da exceção entra só no fim — quem recebe no celular precisa primeiro saber
# que o backup parou e o que fazer a respeito (SPEC §4).
_CRITICAL_TEXTS: tuple[tuple[type[BaseException], str, str, str], ...] = (
    (
        DiskError,
        "disco",
        "O backup parou: o disco de destino não está acessível.",
        "Conecte o disco de backup e use 'Verificar agora' para retomar.",
    ),
    (
        AuthError,
        "auth",
        "O backup parou: o app perdeu o acesso à pasta do Drive.",
        "Confira se a pasta continua compartilhada com a conta de serviço e se a "
        "chave não foi revogada.",
    ),
    (
        ConfigError,
        "config",
        "O backup parou: a configuração está inválida.",
        "Corrija as configurações e inicie o app novamente.",
    ),
)


def _message_for(exc: BaseException) -> tuple[str, str]:
    """(chave de deduplicação, mensagem acionável) para um erro crítico."""
    detail = str(exc)
    for kind, key, what, action in _CRITICAL_TEXTS:
        if isinstance(exc, kind):
            return key, f"{what}\n\nO que fazer: {action}\n\nDetalhe técnico: {detail}"
    return "critico", f"O backup parou por um erro inesperado.\n\nDetalhe técnico: {detail}"


class AlertManager:
    """Aplica a política de notificação sobre um :class:`Notifier` qualquer."""

    def __init__(
        self,
        notifier: Notifier,
        state: State,
        logger: logging.Logger,
        *,
        repeat_after_hours: int = REPEAT_AFTER_HOURS,
        degraded_after_hours: int = DEGRADED_AFTER_HOURS,
    ) -> None:
        self._notifier = notifier
        self._state = state
        self._log = logger
        self._repeat_after = timedelta(hours=repeat_after_hours)
        self._degraded_after_hours = degraded_after_hours
        self._degraded_after = timedelta(hours=degraded_after_hours)

    # --- API principal ----------------------------------------------------

    def critical(self, exc: BaseException) -> bool:
        """Notifica um erro de Nível 3. Retorna ``True`` se a notificação saiu."""
        key, message = _message_for(exc)
        self._log.error(
            "Nível 3 (%s): %s", key, exc, extra={"category": self._category_for(key)}
        )
        return self.send(key, message, priority=PRIORITY_HIGH, tags="rotating_light")

    def check_degraded(self) -> int:
        """Notifica arquivos que já falham há mais de 24 h. Retorna quantos entraram."""
        cutoff = (_now() - self._degraded_after).isoformat()
        stale = self._state.failing_since(cutoff)
        if not stale:
            return 0

        names = [row.drive_path for row in stale[:5]]
        extra = f" e mais {len(stale) - 5}" if len(stale) > 5 else ""
        message = (
            f"{len(stale)} arquivo(s) falham há mais de {self._degraded_after_hours}h: "
            + ", ".join(names)
            + extra
            + ". O backup dos demais continua normalmente; verifique a aba Atividade."
        )
        self._log.warning(
            "Nível 2: %d arquivo(s) em falha persistente.", len(stale),
            extra={"category": "download"},
        )
        self.send("degradado", message, priority=PRIORITY_DEFAULT, tags="warning")
        return len(stale)

    def info(self, key: str, message: str, *, tags: str = "") -> bool:
        """Notificação informativa (resumo semanal, teste), sujeita ao anti-spam."""
        return self.send(key, message, priority=PRIORITY_DEFAULT, tags=tags)

    def send(
        self,
        key: str,
        message: str,
        *,
        priority: str = PRIORITY_DEFAULT,
        tags: str = "",
        force: bool = False,
    ) -> bool:
        """Envia respeitando a janela de silêncio da chave (a menos que ``force``)."""
        if not self._notifier.enabled:
            return False
        if not force and self._recently_sent(key):
            self._log.debug(
                "Alerta '%s' suprimido (repetido dentro da janela).", key,
                extra={"category": "notify"},
            )
            return False

        sent = self._notifier.notify(_TITLE, message, priority=priority, tags=tags)
        if sent:
            self._state.record_event("INFO", _marker_category(key), message)
        return sent

    # --- Interno ----------------------------------------------------------

    @staticmethod
    def _category_for(key: str) -> str:
        return {"disco": "disk", "auth": "auth", "config": "config"}.get(key, "cycle")

    def _recently_sent(self, key: str) -> bool:
        row = self._state.connection.execute(
            "SELECT ts FROM events WHERE category=? ORDER BY id DESC LIMIT 1",
            (_marker_category(key),),
        ).fetchone()
        if row is None:
            return False
        try:
            last = datetime.fromisoformat(row["ts"])
        except ValueError:
            return False
        return _now() - last < self._repeat_after


def is_critical(exc: BaseException) -> bool:
    """Atalho: a exceção é de Nível 3?"""
    return classify(exc) == LEVEL_CRITICAL
