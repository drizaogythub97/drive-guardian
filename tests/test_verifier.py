"""Testes do verificador de md5 (SPEC.md §3)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from core import verifier


def test_md5_matches_hashlib(tmp_path: Path) -> None:
    data = b"conteudo qualquer para hashing" * 100
    path = tmp_path / "f.bin"
    path.write_bytes(data)
    expected = hashlib.md5(data, usedforsecurity=False).hexdigest()
    assert verifier.md5_file(path) == expected
    assert verifier.matches(path, expected)
    assert not verifier.matches(path, "0" * 32)
