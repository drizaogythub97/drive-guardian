"""Hierarquia de erros por nível de severidade (SPEC.md §4).

- Nível 1 (transitório): timeout, 5xx, 429 -> backoff, só log. (Fase 1+)
- Nível 2 (degradado): arquivo falhou 3x, md5 divergente -> pula. (Fase 1+)
- Nível 3 (crítico): credencial inválida, disco ausente/cheio, config inválida
  -> pausa sync, status vermelho, notificação ntfy imediata.

Na Fase 0 usamos apenas os erros de Nível 3 (config e auth).
"""

from __future__ import annotations


class DriveGuardianError(Exception):
    """Base para todos os erros do app."""


class CriticalError(DriveGuardianError):
    """Nível 3: crítico. Deve pausar o sync e notificar imediatamente."""


class ConfigError(CriticalError):
    """Config inválida ou ausente (Nível 3)."""


class AuthError(CriticalError):
    """Falha de autenticação/credencial (Nível 3)."""


class DiskError(CriticalError):
    """Disco de destino ausente, inacessível ou cheio (Nível 3)."""
