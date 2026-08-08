"""Interface comum de notificação (SPEC.md §4). Implementação na Fase 2."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Notifier(ABC):
    """Envia alertas acionáveis ao usuário (celular)."""

    @abstractmethod
    def notify(self, title: str, message: str, *, priority: str = "default") -> None:
        """Envia uma notificação. ``priority`` alto para erros Nível 3."""
