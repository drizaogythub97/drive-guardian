"""Notificadores (ntfy e futuros). Interface comum em ``base``."""

from __future__ import annotations

import logging

from core.config import NotificationsConfig
from core.notifier.base import PRIORITY_DEFAULT, PRIORITY_HIGH, PRIORITY_LOW, Notifier, NullNotifier
from core.notifier.ntfy import NtfyNotifier

__all__ = [
    "PRIORITY_DEFAULT",
    "PRIORITY_HIGH",
    "PRIORITY_LOW",
    "Notifier",
    "NtfyNotifier",
    "NullNotifier",
    "build_notifier",
]


def build_notifier(config: NotificationsConfig, logger: logging.Logger) -> Notifier:
    """Escolhe o notificador conforme a config (ntfy ligado ou nenhum)."""
    if not config.ntfy.enabled:
        return NullNotifier()
    return NtfyNotifier(config.ntfy.server, config.ntfy.topic, logger)
