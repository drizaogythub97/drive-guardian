"""Localização dos dados do app em ``%LOCALAPPDATA%/DriveGuardian``.

Em plataformas não-Windows (CI, testes) cai para ``~/.local/share/DriveGuardian``,
ou para ``$DRIVE_GUARDIAN_DATA_DIR`` se definido (usado nos testes).
"""

from __future__ import annotations

import os
from pathlib import Path

APP_NAME = "DriveGuardian"


def data_dir() -> Path:
    """Diretório-raiz de dados do app (criado se ausente)."""
    override = os.environ.get("DRIVE_GUARDIAN_DATA_DIR")
    if override:
        base = Path(override)
    elif os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP_NAME
    base.mkdir(parents=True, exist_ok=True)
    return base


def logs_dir() -> Path:
    """Diretório de logs rotativos (criado se ausente)."""
    path = data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def state_db_path() -> Path:
    """Caminho do banco de estado SQLite."""
    return data_dir() / "state.db"
