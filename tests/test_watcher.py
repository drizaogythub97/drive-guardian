"""Testes do ciclo incremental (changes.list) — filtragem por subárvore e
política de nunca apagar (SPEC.md §3; critério F1 d). Sem rede — serviço falso."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from core.config import SyncPair
from core.drive import FOLDER_MIME
from core.state import State
from core.watcher import FolderResolver, poll_changes

# Hierarquia de pastas: ROOT -> SUB (dentro); OTHER -> OUT (fora).
_FOLDERS: dict[str, dict[str, Any]] = {
    "ROOT": {"id": "ROOT", "name": "Memorias", "parents": []},
    "SUB": {"id": "SUB", "name": "2024", "parents": ["ROOT"]},
    "OTHER": {"id": "OTHER", "name": "Outra", "parents": []},
    "OUT": {"id": "OUT", "name": "Fora", "parents": ["OTHER"]},
}


class _Exec:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def execute(self) -> dict[str, Any]:
        return self._data


class _Files:
    def get(self, fileId: str, fields: str, supportsAllDrives: bool) -> _Exec:
        return _Exec(_FOLDERS[fileId])


class _Changes:
    def __init__(self, page: dict[str, Any]) -> None:
        self._page = page

    def list(self, **_kwargs: Any) -> _Exec:
        return _Exec(self._page)


class FakeService:
    def __init__(self, page: dict[str, Any]) -> None:
        self._files = _Files()
        self._changes = _Changes(page)

    def files(self) -> _Files:
        return self._files

    def changes(self) -> _Changes:
        return self._changes


def _pair(root: Path) -> SyncPair:
    return SyncPair(drive_folder_id="ROOT", local_path=root)


def test_folder_resolver_scopes_to_root() -> None:
    resolver = FolderResolver(FakeService({}), "ROOT")
    inside = {"id": "Z", "name": "z.jpg", "parents": ["SUB"]}
    outside = {"id": "W", "name": "w.jpg", "parents": ["OUT"]}
    assert resolver.drive_path_of(inside) == "2024/z.jpg"
    assert resolver.drive_path_of(outside) is None


def test_poll_changes_filters_and_never_deletes(tmp_path: Path) -> None:
    page = {
        "newStartPageToken": "T1",
        "changes": [
            {"removed": True, "fileId": "GONE"},
            {"file": {"id": "Y", "name": "y.jpg", "mimeType": "image/jpeg",
                      "parents": ["SUB"], "trashed": True}},
            {"file": {"id": "Z", "name": "z.jpg", "mimeType": "image/jpeg",
                      "md5Checksum": "m", "size": "5", "modifiedTime": "t",
                      "parents": ["SUB"], "trashed": False}},
            {"file": {"id": "W", "name": "w.jpg", "mimeType": "image/jpeg",
                      "md5Checksum": "m", "size": "5", "parents": ["OUT"]}},
            {"file": {"id": "SUB2", "name": "nova", "mimeType": FOLDER_MIME,
                      "parents": ["ROOT"]}},
        ],
    }
    service = FakeService(page)
    resolver = FolderResolver(service, "ROOT")
    with State() as state:
        state.set_page_token("T0")
        result = poll_changes(service, state, _pair(tmp_path), resolver, logging.getLogger("t"))

    # Só o arquivo Z (novo, dentro da raiz) entra na fila.
    assert [i.file.id for i in result.items] == ["Z"]
    assert result.items[0].file.drive_path == "2024/z.jpg"
    # removido + lixeira contam como "removidos" (apenas log, nunca apaga)
    assert result.removed == 2
    assert result.new_token == "T1"
