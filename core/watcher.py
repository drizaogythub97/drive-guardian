"""Ciclo incremental via ``changes.list`` (SPEC.md §3).

Detecta mudanças desde o último ``pageToken``. Novos/modificados dentro da pasta
monitorada entram na fila; removidos/lixeira geram apenas log INFO (política:
nunca apagar localmente). Filtra para a subárvore da pasta monitorada resolvendo
os pais de cada arquivo (memoizado em :class:`FolderResolver`).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from core.config import SyncPair
from core.drive import FOLDER_MIME, DriveFile
from core.planner import PlanItem, classify, local_path_for
from core.state import State

_CHANGES_FIELDS = (
    "nextPageToken, newStartPageToken, "
    "changes(removed, fileId, "
    "file(id, name, mimeType, md5Checksum, size, modifiedTime, parents, trashed))"
)


@dataclass
class ChangeResult:
    items: list[PlanItem]
    removed: int
    new_token: str


class FolderResolver:
    """Resolve o caminho lógico de um item se ele estiver sob a pasta monitorada.

    Memoiza ``folder_id -> caminho relativo`` (``""`` para a raiz, ``None`` se fora
    da raiz), consultando os pais sob demanda.
    """

    def __init__(self, service: Any, root_id: str) -> None:
        self._service = service
        self._root_id = root_id
        self._cache: dict[str, str | None] = {root_id: ""}

    def _folder_rel(self, folder_id: str, _depth: int = 0) -> str | None:
        if folder_id in self._cache:
            return self._cache[folder_id]
        if _depth > 50:  # proteção contra ciclos/hierarquias absurdas
            return None
        meta = (
            self._service.files()
            .get(fileId=folder_id, fields="id, name, parents", supportsAllDrives=True)
            .execute()
        )
        parents = meta.get("parents") or []
        rel: str | None = None
        if parents:
            parent_rel = self._folder_rel(parents[0], _depth + 1)
            if parent_rel is not None:
                name = meta.get("name", folder_id)
                rel = f"{parent_rel}/{name}" if parent_rel else name
        self._cache[folder_id] = rel
        return rel

    def drive_path_of(self, file_meta: dict[str, Any]) -> str | None:
        """Caminho relativo do arquivo sob a raiz, ou ``None`` se estiver fora dela."""
        parents = file_meta.get("parents") or []
        if not parents:
            return None
        parent_rel = self._folder_rel(parents[0])
        if parent_rel is None:
            return None
        name = file_meta.get("name", file_meta.get("id", "?"))
        return f"{parent_rel}/{name}" if parent_rel else name


def _to_drive_file(meta: dict[str, Any], drive_path: str) -> DriveFile:
    size_raw = meta.get("size")
    return DriveFile(
        id=str(meta["id"]),
        name=str(meta.get("name", "?")),
        mime_type=str(meta.get("mimeType", "")),
        md5=meta.get("md5Checksum"),
        size=int(size_raw) if size_raw is not None else None,
        modified_time=meta.get("modifiedTime"),
        drive_path=drive_path,
    )


def list_changes(service: Any, page_token: str) -> tuple[list[dict[str, Any]], str]:
    """Coleta todas as mudanças desde ``page_token``; retorna (mudanças, novo_token)."""
    changes: list[dict[str, Any]] = []
    token = page_token
    while True:
        resp = (
            service.changes()
            .list(
                pageToken=token,
                spaces="drive",
                includeRemoved=True,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                pageSize=1000,
                fields=_CHANGES_FIELDS,
            )
            .execute()
        )
        changes.extend(resp.get("changes", []))
        next_token = resp.get("nextPageToken")
        if next_token:
            token = next_token
            continue
        return changes, str(resp.get("newStartPageToken", token))


def poll_changes(
    service: Any,
    state: State,
    pair: SyncPair,
    resolver: FolderResolver,
    logger: logging.Logger,
) -> ChangeResult:
    """Processa mudanças incrementais e monta os itens de fila da subárvore monitorada."""
    token = state.get_page_token()
    if token is None:
        raise RuntimeError("watcher: sem pageToken; rode a reconciliação completa primeiro")

    raw_changes, new_token = list_changes(service, token)
    items: list[PlanItem] = []
    removed = 0

    for change in raw_changes:
        meta = change.get("file")
        if change.get("removed") or (meta and meta.get("trashed")):
            removed += 1
            file_id = change.get("fileId", "?")
            logger.info(
                "Item removido/lixeira no Drive; mantido localmente (fileId=%s)",
                file_id,
                extra={"category": "cycle", "file_id": file_id},
            )
            continue
        if not meta or meta.get("mimeType") == FOLDER_MIME:
            continue

        drive_path = resolver.drive_path_of(meta)
        if drive_path is None:
            continue  # fora da pasta monitorada

        file = _to_drive_file(meta, drive_path)
        if file.is_google_native:
            logger.info(
                "Ignorando Google Doc nativo (export é Fase 4): %s",
                file.drive_path,
                extra={"category": "download", "file_id": file.id},
            )
            continue

        local_path = local_path_for(pair, file)
        if classify(state, file, local_path) is not None:
            items.append(PlanItem(file=file, local_path=local_path, reason="incremental"))

    return ChangeResult(items=items, removed=removed, new_token=new_token)
