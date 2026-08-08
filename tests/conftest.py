"""Fixtures compartilhadas: isola dados do app num diretório temporário."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """Redireciona ``%LOCALAPPDATA%/DriveGuardian`` para um tmp por teste."""
    monkeypatch.setenv("DRIVE_GUARDIAN_DATA_DIR", str(tmp_path))
    yield tmp_path
