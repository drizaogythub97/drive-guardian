"""Verificação de integridade: md5 local x ``md5Checksum`` do Drive (SPEC.md §3)."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1024 * 1024  # 1 MiB


def md5_file(path: str | Path) -> str:
    """Calcula o md5 (hex) de um arquivo em streaming, sem carregá-lo na memória."""
    # md5 é imposto pela Drive API (md5Checksum); não é uso criptográfico.
    digest = hashlib.md5(usedforsecurity=False)
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def matches(path: str | Path, expected_md5: str) -> bool:
    """Verifica se o md5 do arquivo local bate com o esperado (do Drive)."""
    return md5_file(path) == expected_md5
