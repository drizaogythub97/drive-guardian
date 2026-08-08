"""Validação do destino em disco (SPEC.md §1 e §3).

Regra: o app cria pastas, nunca "inventa" uma unidade. Unidade ausente ->
Nível 3 (:class:`DiskError`); pasta final ausente -> criar automaticamente.
Antes de baixar: exigir espaço livre >= tamanho do arquivo + folga (500 MB).
"""

from __future__ import annotations

import shutil
from pathlib import Path

from core.errors import DiskError

FREE_SPACE_MARGIN = 500 * 1024 * 1024  # 500 MiB de folga


def _anchor(path: Path) -> Path:
    """Raiz/unidade do caminho (ex.: ``D:\\`` no Windows, ``/`` no POSIX)."""
    resolved = path if path.is_absolute() else path.resolve()
    return Path(resolved.anchor) if resolved.anchor else resolved


def drive_available(path: str | Path) -> bool:
    """True se a unidade/raiz do caminho existe e está acessível."""
    anchor = _anchor(Path(path))
    return anchor.exists()


def ensure_destination(local_root: str | Path, *, create: bool = True) -> Path:
    """Valida a unidade e garante a pasta de destino.

    Unidade ausente -> :class:`DiskError` (Nível 3). Se ``create`` e a pasta não
    existe, cria (com os pais). Retorna o caminho absoluto do destino.
    """
    root = Path(local_root)
    anchor = _anchor(root)
    if not anchor.exists():
        raise DiskError(
            f"disk: a unidade {anchor} não foi encontrada. "
            "Conecte o disco de destino e tente novamente."
        )
    if create and not root.exists():
        root.mkdir(parents=True, exist_ok=True)
    return root


def free_space_bytes(path: str | Path) -> int:
    """Espaço livre (bytes) na unidade que contém ``path``."""
    target = Path(path)
    probe = target if target.exists() else _anchor(target)
    return shutil.disk_usage(str(probe)).free


def check_free_space(
    path: str | Path, needed_bytes: int, *, margin: int = FREE_SPACE_MARGIN
) -> None:
    """Levanta :class:`DiskError` se não houver espaço para ``needed_bytes`` + folga."""
    free = free_space_bytes(path)
    required = needed_bytes + margin
    if free < required:
        raise DiskError(
            f"disk: espaço insuficiente em {_anchor(Path(path))} "
            f"(livre {free} B, necessário {required} B). Libere espaço no disco."
        )
