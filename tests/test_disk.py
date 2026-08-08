"""Testes das checagens de disco/destino (SPEC.md §1 e §3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from core import disk
from core.errors import DiskError


def test_ensure_destination_creates_folder(tmp_path: Path) -> None:
    dest = tmp_path / "BackupDrive" / "Memorias"
    result = disk.ensure_destination(dest)
    assert result.exists() and result.is_dir()


@pytest.mark.skipif(sys.platform != "win32", reason="letras de unidade só no Windows")
def test_ensure_destination_missing_drive_is_critical() -> None:
    # Uma unidade inexistente no Windows dispara Nível 3.
    with pytest.raises(DiskError):
        disk.ensure_destination("Z:/DriveGuardian/qualquer")


def test_check_free_space_raises_when_insufficient(tmp_path: Path) -> None:
    huge = 10**18  # ~1 EB: maior que qualquer disco real
    with pytest.raises(DiskError):
        disk.check_free_space(tmp_path, huge)


def test_check_free_space_ok_for_small(tmp_path: Path) -> None:
    disk.check_free_space(tmp_path, 1)  # não deve levantar
