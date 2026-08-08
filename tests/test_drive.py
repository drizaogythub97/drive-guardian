"""Testes da lógica de árvore do Drive, sem rede (usa nós sintéticos)."""

from __future__ import annotations

from cli import _render_tree
from core.drive import FOLDER_MIME, DriveFile, DriveNode, iter_files


def _folder(name: str, path: str) -> DriveNode:
    return DriveNode(
        DriveFile(id=name, name=name, mime_type=FOLDER_MIME, md5=None, size=None,
                  modified_time=None, drive_path=path)
    )


def _file(name: str, path: str, size: int | None, mime: str = "image/jpeg") -> DriveNode:
    return DriveNode(
        DriveFile(id=name, name=name, mime_type=mime, md5="x", size=size,
                  modified_time=None, drive_path=path)
    )


def _sample_tree() -> DriveNode:
    root = _folder("Memorias", "")
    sub = _folder("2024", "2024")
    sub.children.append(_file("a.jpg", "2024/a.jpg", 1500))
    sub.children.append(_file("doc", "2024/doc", None, mime="application/vnd.google-apps.document"))
    root.children.append(sub)
    root.children.append(_file("raiz.png", "raiz.png", 2048))
    return root


def test_iter_files_flattens_and_excludes_folders() -> None:
    files = iter_files(_sample_tree())
    names = sorted(f.name for f in files)
    assert names == ["a.jpg", "doc", "raiz.png"]


def test_google_native_flag() -> None:
    files = {f.name: f for f in iter_files(_sample_tree())}
    assert files["doc"].is_google_native is True
    assert files["a.jpg"].is_google_native is False


def test_render_tree_shows_structure() -> None:
    lines = _render_tree(_sample_tree())
    assert lines[0] == "Memorias/"
    assert any("2024/" in line for line in lines)
    assert any("a.jpg" in line and "1.5 KB" in line for line in lines)
    assert any("[Google Docs]" in line for line in lines)
