"""Strings de UI em PT-BR isoladas para futura tradução (CLAUDE.md §Stack).

Também abriga textos de notificação acionáveis (SPEC.md §4), reutilizáveis
pelo core via injeção — sem que o core importe ``ui`` (CLAUDE.md §6).
"""

from __future__ import annotations

APP_NAME = "Drive Guardian"

# Bandeja / menu (Fase 3)
TRAY_OPEN = "Abrir"
TRAY_CHECK_NOW = "Verificar agora"
TRAY_PAUSE = "Pausar"
TRAY_QUIT = "Sair"

# Status
STATUS_OK = "Tudo sincronizado"
STATUS_SYNCING = "Sincronizando…"
STATUS_ACTION_NEEDED = "Ação necessária"
