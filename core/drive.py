"""Cliente fino da Google Drive API: monta o serviço e lista a árvore de uma
pasta (usado pelo ``cli.py list`` na Fase 0 e pela reconciliação na Fase 1).

Escopo de leitura apenas. Campos alinhados ao SPEC.md §3 (reconciliação).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from googleapiclient.discovery import build

from core.auth import Auth
from core.errors import AuthError

FOLDER_MIME = "application/vnd.google-apps.folder"
_LIST_FIELDS = "nextPageToken, files(id, name, mimeType, md5Checksum, size, modifiedTime, trashed)"
_GET_FIELDS = "id, name, mimeType"


@dataclass(frozen=True)
class DriveFile:
    """Metadados de um item do Drive relevantes para o backup."""

    id: str
    name: str
    mime_type: str
    md5: str | None
    size: int | None
    modified_time: str | None
    drive_path: str  # caminho lógico relativo à raiz monitorada

    @property
    def is_folder(self) -> bool:
        return self.mime_type == FOLDER_MIME

    @property
    def is_google_native(self) -> bool:
        """Docs/Sheets/Slides nativos: sem md5/size, exigem export (Fase 4)."""
        return self.mime_type.startswith("application/vnd.google-apps.") and not self.is_folder


@dataclass
class DriveNode:
    """Nó da árvore: um :class:`DriveFile` e seus filhos (vazio se arquivo)."""

    file: DriveFile
    children: list[DriveNode] = field(default_factory=list)


def build_service(auth: Auth) -> Any:
    """Constrói o recurso ``drive.v3`` autenticado."""
    return build("drive", "v3", credentials=auth.credentials(), cache_discovery=False)


def _list_children(service: Any, parent_id: str) -> list[dict[str, Any]]:
    children: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        response = (
            service.files()
            .list(
                q=f"'{parent_id}' in parents and trashed=false",
                fields=_LIST_FIELDS,
                pageSize=1000,
                orderBy="folder,name",
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        children.extend(response.get("files", []))
        page_token = response.get("nextPageToken")
        if not page_token:
            return children


def _to_drive_file(raw: dict[str, Any], parent_path: str) -> DriveFile:
    name = str(raw.get("name", "?"))
    drive_path = f"{parent_path}/{name}" if parent_path else name
    size_raw = raw.get("size")
    return DriveFile(
        id=str(raw["id"]),
        name=name,
        mime_type=str(raw.get("mimeType", "")),
        md5=raw.get("md5Checksum"),
        size=int(size_raw) if size_raw is not None else None,
        modified_time=raw.get("modifiedTime"),
        drive_path=drive_path,
    )


@dataclass(frozen=True)
class FolderEntry:
    """Pasta do Drive listada no navegador da UI (SPEC §5, aba Pastas)."""

    id: str
    name: str


def list_folders(service: Any, parent_id: str | None = None) -> list[FolderEntry]:
    """Subpastas de ``parent_id``; sem ele, as pastas compartilhadas com a conta.

    A conta de serviço não tem "Meu Drive" com conteúdo: o que ela enxerga é o que
    foi compartilhado com o e-mail dela. Por isso a raiz do navegador é
    ``sharedWithMe``, e não ``root`` — que viria vazio e pareceria um erro.
    """
    if parent_id:
        query = f"'{parent_id}' in parents and mimeType='{FOLDER_MIME}' and trashed=false"
    else:
        query = f"sharedWithMe=true and mimeType='{FOLDER_MIME}' and trashed=false"

    folders: list[FolderEntry] = []
    page_token: str | None = None
    while True:
        response = (
            service.files()
            .list(
                q=query,
                fields="nextPageToken, files(id, name)",
                pageSize=200,
                orderBy="name",
                pageToken=page_token,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
        folders.extend(
            FolderEntry(id=str(f["id"]), name=str(f.get("name", "?")))
            for f in response.get("files", [])
        )
        page_token = response.get("nextPageToken")
        if not page_token:
            return folders


def folder_name(service: Any, folder_id: str) -> str:
    """Nome de uma pasta pelo ID (para a UI mostrar algo legível)."""
    meta = (
        service.files()
        .get(fileId=folder_id, fields="id, name", supportsAllDrives=True)
        .execute()
    )
    return str(meta.get("name", folder_id))


def build_tree(service: Any, root_folder_id: str) -> DriveNode:
    """Monta recursivamente a árvore da pasta monitorada."""
    try:
        root_meta = (
            service.files()
            .get(fileId=root_folder_id, fields=_GET_FIELDS, supportsAllDrives=True)
            .execute()
        )
    except Exception as exc:
        raise AuthError(
            f"drive: não foi possível acessar a pasta '{root_folder_id}'. "
            f"Confirme o ID e o compartilhamento com a conta de serviço. Detalhe: {exc}"
        ) from exc

    root_file = DriveFile(
        id=str(root_meta["id"]),
        name=str(root_meta.get("name", root_folder_id)),
        mime_type=str(root_meta.get("mimeType", FOLDER_MIME)),
        md5=None,
        size=None,
        modified_time=None,
        drive_path="",
    )
    root = DriveNode(file=root_file)
    _populate(service, root, parent_path="")
    return root


def _populate(service: Any, node: DriveNode, parent_path: str) -> None:
    for raw in _list_children(service, node.file.id):
        child_file = _to_drive_file(raw, parent_path)
        child = DriveNode(file=child_file)
        node.children.append(child)
        if child_file.is_folder:
            _populate(service, child, parent_path=child_file.drive_path)


def iter_files(node: DriveNode) -> list[DriveFile]:
    """Achata a árvore em lista de arquivos (exclui pastas)."""
    out: list[DriveFile] = []
    for child in node.children:
        if child.file.is_folder:
            out.extend(iter_files(child))
        else:
            out.append(child.file)
    return out
