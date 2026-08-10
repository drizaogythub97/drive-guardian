"""Hierarquia de erros por nível de severidade (SPEC.md §4).

- Nível 1 (transitório): timeout, 5xx, 429 -> backoff, só log.
- Nível 2 (degradado): arquivo falhou 3x, md5 divergente -> pula, notifica se >24h.
- Nível 3 (crítico): credencial inválida, disco ausente/cheio, config inválida
  -> pausa sync, status vermelho, notificação ntfy imediata.

Além das classes, este módulo sabe **classificar exceções de terceiros** (Google API,
``requests``, socket) no nível certo — é o que decide entre retentar, pular ou alertar.
"""

from __future__ import annotations

from typing import Final

LEVEL_TRANSIENT: Final = 1
LEVEL_DEGRADED: Final = 2
LEVEL_CRITICAL: Final = 3

# Status HTTP tratados como transitórios (Nível 1).
_TRANSIENT_STATUS: Final = frozenset({408, 429, 500, 502, 503, 504})
# Status HTTP de credencial inválida/sem acesso (Nível 3).
_AUTH_STATUS: Final = frozenset({401, 403})


class DriveGuardianError(Exception):
    """Base para todos os erros do app."""


class TransientError(DriveGuardianError):
    """Nível 1: falha passageira (rede, 5xx, 429). Retentar com backoff."""


class DegradedError(DriveGuardianError):
    """Nível 2: o ciclo segue, este item é pulado e retentado depois."""


class ChecksumError(DegradedError):
    """md5 do arquivo baixado diverge do metadado do Drive (Nível 2)."""


class CriticalError(DriveGuardianError):
    """Nível 3: crítico. Deve pausar o sync e notificar imediatamente."""


class ConfigError(CriticalError):
    """Config inválida ou ausente (Nível 3)."""


class AuthError(CriticalError):
    """Falha de autenticação/credencial (Nível 3)."""


class DiskError(CriticalError):
    """Disco de destino ausente, inacessível ou cheio (Nível 3)."""


def http_status_of(exc: BaseException) -> int | None:
    """Extrai o status HTTP de exceções do Google API client ou do ``requests``."""
    resp = getattr(exc, "resp", None)  # googleapiclient.errors.HttpError
    status = getattr(resp, "status", None)
    if status is None:
        response = getattr(exc, "response", None)  # requests.HTTPError
        status = getattr(response, "status_code", None)
    if status is None:
        status = getattr(exc, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None


def classify(exc: BaseException) -> int:
    """Nível de severidade (1/2/3) de uma exceção qualquer.

    Erros já tipados pelo app mandam. Para exceções de terceiros, decide pelo
    status HTTP e pelo tipo (timeout/conexão -> transitório). O padrão é Nível 1:
    é o mais seguro, porque só implica retentar.
    """
    if isinstance(exc, CriticalError):
        return LEVEL_CRITICAL
    if isinstance(exc, DegradedError):
        return LEVEL_DEGRADED
    if isinstance(exc, TransientError):
        return LEVEL_TRANSIENT

    status = http_status_of(exc)
    if status is not None:
        if status in _AUTH_STATUS:
            return LEVEL_CRITICAL
        if status in _TRANSIENT_STATUS:
            return LEVEL_TRANSIENT
        if 500 <= status < 600:
            return LEVEL_TRANSIENT
        return LEVEL_DEGRADED  # 4xx restantes: pular e retentar no próximo ciclo

    # Sem status HTTP: timeout/conexão (todos ``OSError``) e o resto caem em
    # transitório — retentar é a reação mais segura para o desconhecido.
    return LEVEL_TRANSIENT


def is_transient(exc: BaseException) -> bool:
    return classify(exc) == LEVEL_TRANSIENT
