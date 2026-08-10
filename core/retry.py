"""Retry com backoff para erros de Nível 1 (SPEC.md §4).

Política do SPEC: backoff 1 → 5 → 30 min, no máximo 3 tentativas dentro do ciclo.
Só erros transitórios são retentados; Nível 2 e 3 sobem na hora (pular ou pausar).

O ``sleep`` é injetável para os testes não esperarem meia hora de verdade.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from core.errors import LEVEL_TRANSIENT, classify

# Espera antes de cada nova tentativa, em segundos (SPEC §4).
BACKOFF_SECONDS: tuple[int, ...] = (60, 300, 1800)
MAX_ATTEMPTS = 3


def retry_transient[T](
    operation: Callable[[], T],
    *,
    description: str,
    logger: logging.Logger,
    attempts: int = MAX_ATTEMPTS,
    backoff: tuple[int, ...] = BACKOFF_SECONDS,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Executa ``operation`` retentando apenas falhas transitórias.

    Levanta a última exceção quando as tentativas acabam, ou imediatamente se o
    erro não for de Nível 1.
    """
    last_exc: BaseException | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except Exception as exc:
            if classify(exc) != LEVEL_TRANSIENT:
                raise
            last_exc = exc
            if attempt == attempts:
                break
            wait = backoff[min(attempt - 1, len(backoff) - 1)]
            logger.warning(
                "Falha transitória em %s (tentativa %d/%d): %s. Nova tentativa em %d s.",
                description, attempt, attempts, exc, wait,
                extra={"category": "cycle"},
            )
            sleep(wait)

    assert last_exc is not None  # só chegamos aqui por esgotar as tentativas
    raise last_exc
