"""Testes do download atômico: sucesso, retomada via Range, md5 divergente e
versionamento (SPEC.md §3; critérios F1 c/e). Sem rede — sessão HTTP falsa."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

from core.downloader import Downloader
from core.drive import DriveFile


def _md5(data: bytes) -> str:
    return hashlib.md5(data, usedforsecurity=False).hexdigest()


class FakeResponse:
    def __init__(self, data: bytes, status: int) -> None:
        self._data = data
        self.status_code = status

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False

    def iter_content(self, chunk_size: int) -> Iterator[bytes]:
        for i in range(0, len(self._data), chunk_size):
            yield self._data[i : i + chunk_size]

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    """Serve bytes de um blob por file_id, honrando o cabeçalho Range (206)."""

    def __init__(self, blob: dict[str, bytes]) -> None:
        self.blob = blob
        self.range_requests = 0

    def get(
        self, url: str, headers: dict[str, str] | None = None, stream: bool = False,
        timeout: int | None = None,
    ) -> FakeResponse:
        file_id = url.split("/files/")[1].split("?")[0]
        data = self.blob[file_id]
        rng = (headers or {}).get("Range")
        if rng:
            self.range_requests += 1
            offset = int(rng.split("=")[1].split("-")[0])
            if offset >= len(data):
                return FakeResponse(b"", 416)  # Range além do fim
            return FakeResponse(data[offset:], 206)
        return FakeResponse(data, 200)


def _file(content: bytes, name: str = "a.bin", path: str | None = None) -> DriveFile:
    return DriveFile(
        id="F1", name=name, mime_type="application/octet-stream",
        md5=_md5(content), size=len(content), modified_time="2026-01-01T00:00:00Z",
        drive_path=path or name,
    )


def _downloader(blob: dict[str, bytes]) -> Downloader:
    return Downloader(session=FakeSession(blob), chunk_size=4)


def test_full_download_atomic(tmp_path: Path) -> None:
    content = b"hello world, this is a test payload"
    dl = _downloader({"F1": content})
    dest = tmp_path / "a.bin"

    result = dl.download(_file(content), dest, tmp_path)

    assert result.ok and not result.versioned
    assert dest.read_bytes() == content
    assert not dest.with_name("a.bin.part").exists()  # nada parcial deixado


def test_resume_via_range(tmp_path: Path) -> None:
    content = b"0123456789abcdefghij"  # 20 bytes
    session = FakeSession({"F1": content})
    dl = Downloader(session=session, chunk_size=4)
    dest = tmp_path / "a.bin"
    # Simula queda: .part já tem os primeiros 8 bytes.
    dest.with_name("a.bin.part").write_bytes(content[:8])

    result = dl.download(_file(content), dest, tmp_path)

    assert result.ok
    assert session.range_requests == 1  # retomou, não recomeçou
    assert dest.read_bytes() == content


def test_complete_part_not_renamed_is_finalized(tmp_path: Path) -> None:
    """Crash entre md5 e rename: .part já completo -> 416 -> finaliza sem rebaixar."""
    content = b"already fully downloaded"
    session = FakeSession({"F1": content})
    dl = Downloader(session=session, chunk_size=4)
    dest = tmp_path / "a.bin"
    dest.with_name("a.bin.part").write_bytes(content)  # .part já completo

    result = dl.download(_file(content), dest, tmp_path)

    assert result.ok
    assert dest.read_bytes() == content


def test_md5_mismatch_discards_part(tmp_path: Path) -> None:
    content = b"real content"
    dl = _downloader({"F1": b"corrupted bytes!"})  # servidor devolve outra coisa
    dest = tmp_path / "a.bin"

    result = dl.download(_file(content), dest, tmp_path)

    assert not result.ok and result.error and "md5" in result.error
    assert not dest.exists()
    assert not dest.with_name("a.bin.part").exists()


def test_modified_file_is_versioned(tmp_path: Path) -> None:
    old = b"old version content"
    new = b"new version content!!"
    dest = tmp_path / "sub" / "a.bin"
    dest.parent.mkdir(parents=True)
    dest.write_bytes(old)

    dl = _downloader({"F1": new})
    result = dl.download(_file(new, path="sub/a.bin"), dest, tmp_path)

    assert result.ok and result.versioned
    assert dest.read_bytes() == new
    versions = list((tmp_path / "_versões" / "sub").glob("a.*.bin"))
    assert len(versions) == 1
    assert versions[0].read_bytes() == old  # versão antiga preservada intacta
