"""Navegador de pastas da aba Pastas: a raiz precisa ser ``sharedWithMe``.

A conta de serviço não tem Meu Drive com conteúdo — listar ``root`` devolveria
vazio e o usuário concluiria que o app não funciona.
"""

from __future__ import annotations

from typing import Any

from core.drive import FOLDER_MIME, list_folders


class _Exec:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def execute(self) -> dict[str, Any]:
        return self._data


class _Files:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self.queries: list[str] = []
        self._pages = pages

    def list(self, **kwargs: Any) -> _Exec:
        self.queries.append(str(kwargs.get("q", "")))
        return _Exec(self._pages[len(self.queries) - 1])


class FakeService:
    def __init__(self, pages: list[dict[str, Any]]) -> None:
        self._files = _Files(pages)

    def files(self) -> _Files:
        return self._files


def test_root_listing_uses_shared_with_me() -> None:
    service = FakeService([{"files": [{"id": "A", "name": "Fotos"}]}])
    folders = list_folders(service)

    assert [f.name for f in folders] == ["Fotos"]
    query = service.files().queries[0]
    assert "sharedWithMe=true" in query
    assert FOLDER_MIME in query


def test_child_listing_filters_by_parent() -> None:
    service = FakeService([{"files": [{"id": "B", "name": "2024"}]}])
    folders = list_folders(service, "A")

    assert folders[0].id == "B"
    query = service.files().queries[0]
    assert "'A' in parents" in query
    assert "sharedWithMe" not in query


def test_pagination_is_followed() -> None:
    service = FakeService(
        [
            {"files": [{"id": "A", "name": "um"}], "nextPageToken": "T"},
            {"files": [{"id": "B", "name": "dois"}]},
        ]
    )
    assert [f.name for f in list_folders(service)] == ["um", "dois"]


def test_empty_result_is_not_an_error() -> None:
    assert list_folders(FakeService([{"files": []}])) == []
