"""Download atômico com retomada e versionamento (CLAUDE.md §Regras; SPEC.md §3).

Fluxo por arquivo:
1. Garante o diretório de destino e checa espaço livre (tamanho + folga).
2. Baixa em ``<nome>.part`` — chunked, retomável via cabeçalho ``Range`` a partir
   do tamanho já gravado (retomada pós-queda de rede).
3. Valida o md5 do ``.part`` contra o ``md5Checksum`` do Drive. Se bater: se já
   existe uma versão local, move-a para ``_versões/`` e então renomeia o ``.part``
   atomicamente para o nome final. Se não bater: apaga o ``.part`` (retry no próximo ciclo).

Nunca exclui nem sobrescreve destrutivamente: a versão local anterior é preservada
em ``_versões/<caminho>/<nome>.<timestamp>.<ext>``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from google.auth.transport.requests import AuthorizedSession

from core import disk, verifier
from core.auth import Auth
from core.drive import DriveFile

_DOWNLOAD_URL = "https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&supportsAllDrives=true"
_CHUNK = 8 * 1024 * 1024  # 8 MiB
_VERSIONS_DIR = "_versões"


@dataclass(frozen=True)
class DownloadResult:
    ok: bool
    versioned: bool
    bytes_written: int
    error: str | None = None


class Downloader:
    """Baixa arquivos do Drive de forma atômica e retomável.

    ``session`` pode ser injetado nos testes (qualquer objeto com ``.get`` no
    estilo ``requests``); em produção usa-se uma ``AuthorizedSession``.
    """

    def __init__(
        self, auth: Auth | None = None, *, chunk_size: int = _CHUNK, session: Any | None = None
    ) -> None:
        if session is None:
            if auth is None:
                raise ValueError("Downloader requer 'auth' ou 'session'")
            session = AuthorizedSession(auth.credentials())  # type: ignore[no-untyped-call]
        self._session = session
        self._chunk = chunk_size

    def download(self, file: DriveFile, local_path: Path, local_root: Path) -> DownloadResult:
        """Baixa ``file`` para ``local_path`` (dentro de ``local_root``)."""
        if file.md5 is None:
            return DownloadResult(False, False, 0, "sem md5Checksum (Google Docs nativo?)")

        local_path.parent.mkdir(parents=True, exist_ok=True)
        disk.check_free_space(local_path.parent, file.size or 0)

        part_path = local_path.with_name(local_path.name + ".part")
        bytes_written = self._fetch_to_part(file.id, part_path)

        actual_md5 = verifier.md5_file(part_path)
        if actual_md5 != file.md5:
            part_path.unlink(missing_ok=True)
            return DownloadResult(
                False, False, bytes_written,
                f"md5 divergente (esperado {file.md5}, obtido {actual_md5})",
            )

        versioned = False
        if local_path.exists():
            self._version_existing(local_path, local_root)
            versioned = True

        os.replace(part_path, local_path)  # rename atômico
        return DownloadResult(True, versioned, bytes_written)

    def _fetch_to_part(self, file_id: str, part_path: Path) -> int:
        """Baixa (ou retoma) o conteúdo para ``part_path``; retorna bytes gravados agora."""
        offset = part_path.stat().st_size if part_path.exists() else 0
        headers = {"Range": f"bytes={offset}-"} if offset else {}
        url = _DOWNLOAD_URL.format(file_id=file_id)

        written = 0
        with self._session.get(url, headers=headers, stream=True, timeout=300) as resp:
            if resp.status_code == 416:
                # Range além do fim: o .part já está completo. Deixa a verificação
                # de md5 decidir (se bater, renomeia; se não, apaga e refaz do zero).
                return 0
            if resp.status_code == 206:
                mode = "ab"  # retomada aceita
            elif resp.status_code == 200:
                mode = "wb"  # servidor ignorou Range -> recomeça do zero
            else:
                resp.raise_for_status()
                mode = "wb"
            with open(part_path, mode) as handle:
                for chunk in resp.iter_content(self._chunk):
                    if chunk:
                        handle.write(chunk)
                        written += len(chunk)
        return written

    @staticmethod
    def _version_existing(local_path: Path, local_root: Path) -> None:
        """Move a versão local atual para ``_versões/<caminho>/<nome>.<timestamp>.<ext>``."""
        rel = local_path.relative_to(local_root)
        version_dir = local_root / _VERSIONS_DIR / rel.parent
        version_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        target = version_dir / f"{local_path.stem}.{ts}{local_path.suffix}"
        counter = 1
        while target.exists():  # colisão no mesmo segundo
            target = version_dir / f"{local_path.stem}.{ts}-{counter}{local_path.suffix}"
            counter += 1
        os.replace(local_path, target)
