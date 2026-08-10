"""Interface comum de notificação (SPEC.md §4).

Regra de ouro: **notificar nunca pode derrubar o backup**. As implementações
engolem os próprios erros de rede e apenas registram no log — um ntfy fora do ar
não pode impedir um download de acontecer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

# Prioridades aceitas pelo ntfy (usadas também pelo NullNotifier/testes).
PRIORITY_DEFAULT = "default"
PRIORITY_HIGH = "high"
PRIORITY_LOW = "low"


class Notifier(ABC):
    """Envia alertas acionáveis ao usuário (celular)."""

    @abstractmethod
    def notify(
        self, title: str, message: str, *, priority: str = PRIORITY_DEFAULT, tags: str = ""
    ) -> bool:
        """Envia uma notificação. ``priority`` alto para erros Nível 3.

        Retorna ``True`` se o envio foi bem-sucedido. Não levanta exceção.
        """

    @property
    @abstractmethod
    def enabled(self) -> bool:
        """``False`` quando o canal está desligado na config."""


class NullNotifier(Notifier):
    """Não envia nada — usado quando as notificações estão desabilitadas."""

    def notify(
        self, title: str, message: str, *, priority: str = PRIORITY_DEFAULT, tags: str = ""
    ) -> bool:
        return False

    @property
    def enabled(self) -> bool:
        return False
