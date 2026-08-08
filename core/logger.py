"""Logging: arquivo rotativo em ``%LOCALAPPDATA%/DriveGuardian/logs`` + espelho
opcional dos eventos no SQLite para exibição na UI (SPEC.md; CLAUDE.md §Stack).

Uso::

    log = setup_logging(cfg.logging)
    log.info("mensagem", extra={"category": "cycle"})

O ``category`` (extra) alimenta a coluna ``events.category``; sem ele, cai em "app".
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from core.config import LoggingConfig
from core.paths import logs_dir
from core.state import State

LOGGER_NAME = "drive_guardian"
_LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(name)s] %(message)s"


class SqliteEventHandler(logging.Handler):
    """Espelha registros de log na tabela ``events`` do SQLite."""

    def __init__(self, state: State, level: int = logging.INFO) -> None:
        super().__init__(level)
        self._state = state

    def emit(self, record: logging.LogRecord) -> None:
        try:
            category = str(getattr(record, "category", "app"))
            self._state.record_event(
                level=record.levelname,
                category=category,
                message=record.getMessage(),
                file_id=getattr(record, "file_id", None),
            )
        except Exception:
            self.handleError(record)


def setup_logging(config: LoggingConfig, state: State | None = None) -> logging.Logger:
    """Configura o logger raiz do app (idempotente). Retorna o :class:`Logger`."""
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(getattr(logging, config.level, logging.INFO))
    logger.propagate = False

    # Evita handlers duplicados se chamado mais de uma vez no mesmo processo.
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    formatter = logging.Formatter(_LOG_FORMAT)

    file_handler = RotatingFileHandler(
        logs_dir() / "drive-guardian.log",
        maxBytes=config.max_file_mb * 1024 * 1024,
        backupCount=config.backups,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    if state is not None:
        logger.addHandler(SqliteEventHandler(state))

    return logger


def get_logger() -> logging.Logger:
    """Retorna o logger do app (sem reconfigurar)."""
    return logging.getLogger(LOGGER_NAME)


def null_logger() -> logging.Logger:
    """Logger silencioso (NullHandler) — usado no ``--dry-run`` para não gravar nada."""
    logger = logging.getLogger(f"{LOGGER_NAME}.dryrun")
    logger.handlers.clear()
    logger.addHandler(logging.NullHandler())
    logger.propagate = False
    return logger
