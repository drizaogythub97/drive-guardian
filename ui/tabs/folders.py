"""Aba Pastas: par "pasta do Drive → destino local" e espaço livre do disco.

O navegador de pastas evita o pior pedido possível para um leigo — "cole aqui o ID
da pasta". A raiz da navegação são as pastas compartilhadas com a conta de serviço,
que é exatamente o que ela consegue enxergar.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core import disk
from core.auth import build_auth
from core.config import Config, SyncConfig, SyncPair
from core.drive import FolderEntry, build_service, folder_name, list_folders
from core.util import human_size
from ui import strings as S
from ui.widgets import Card, button, label, row, set_text


class _FolderLoader(QThread):
    """Lista subpastas sem travar o diálogo."""

    loaded = Signal(object, str)  # (list[FolderEntry] | None, erro)

    def __init__(self, config: Config, parent_id: str | None, parent: QWidget) -> None:
        super().__init__(parent)
        self._config = config
        self._parent_id = parent_id

    def run(self) -> None:
        try:
            service = build_service(build_auth(self._config.auth))
            self.loaded.emit(list_folders(service, self._parent_id), "")
        except Exception as exc:
            self.loaded.emit(None, str(exc))


class _NameResolver(QThread):
    """Traduz o ID salvo no config para o nome da pasta, em segundo plano."""

    resolved = Signal(str)

    def __init__(self, config: Config, folder_id: str, parent: QWidget) -> None:
        super().__init__(parent)
        self._config = config
        self._folder_id = folder_id

    def run(self) -> None:
        try:
            service = build_service(build_auth(self._config.auth))
            self.resolved.emit(folder_name(service, self._folder_id))
        except Exception:
            self.resolved.emit("")  # sem rede/credencial: fica o ID mesmo


class DriveFolderPicker(QDialog):
    """Navegador simples: uma lista por nível, com "Voltar" para subir."""

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(S.FOLDERS_PICKER_TITLE)
        self.setMinimumSize(460, 420)

        self._config = config
        self._loader: _FolderLoader | None = None
        self._stack: list[tuple[str, str]] = []  # (id, nome) do caminho atual
        self.selected: FolderEntry | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        self._breadcrumb = label(S.FOLDERS_PICKER_ROOT, "meta")
        layout.addWidget(self._breadcrumb)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._descend)
        layout.addWidget(self._list, 1)

        self._up = button(S.FOLDERS_PICKER_UP)
        self._up.clicked.connect(self._go_up)
        self._up.setEnabled(False)
        choose = button(S.CHOOSE, primary=True)
        choose.clicked.connect(self._accept_current)
        cancel = button(S.CANCEL)
        cancel.clicked.connect(self.reject)
        layout.addWidget(row(self._up, cancel, choose))

        self._load(None)

    # --- Navegação --------------------------------------------------------

    def _current_id(self) -> str | None:
        return self._stack[-1][0] if self._stack else None

    def _load(self, parent_id: str | None) -> None:
        self._list.clear()
        self._list.addItem(S.FOLDERS_PICKER_LOADING)
        self._loader = _FolderLoader(self._config, parent_id, self)
        self._loader.loaded.connect(self._on_loaded)
        self._loader.start()

    def _on_loaded(self, folders: list[FolderEntry] | None, error: str) -> None:
        self._list.clear()
        if folders is None:
            self._list.addItem(S.CONN_FAIL.format(error=error))
            return
        if not folders:
            self._list.addItem(S.FOLDERS_PICKER_EMPTY)
            return
        for folder in folders:
            item = QListWidgetItem(folder.name)
            item.setData(0x0100, folder.id)  # Qt.UserRole
            self._list.addItem(item)

    def _descend(self, item: QListWidgetItem) -> None:
        folder_id = item.data(0x0100)
        if not folder_id:
            return
        self._stack.append((str(folder_id), item.text()))
        self._update_breadcrumb()
        self._load(str(folder_id))

    def _go_up(self) -> None:
        if self._stack:
            self._stack.pop()
        self._update_breadcrumb()
        self._load(self._current_id())

    def _update_breadcrumb(self) -> None:
        path = " > ".join(name for _id, name in self._stack)
        self._breadcrumb.setText(path or S.FOLDERS_PICKER_ROOT)
        self._up.setEnabled(bool(self._stack))

    def _accept_current(self) -> None:
        """Escolhe a pasta marcada na lista; sem marcação, a pasta atual."""
        item = self._list.currentItem()
        folder_id = item.data(0x0100) if item is not None else None
        if folder_id:
            self.selected = FolderEntry(id=str(folder_id), name=item.text())
        elif self._stack:
            current_id, current_name = self._stack[-1]
            self.selected = FolderEntry(id=current_id, name=current_name)
        else:
            return  # nada escolhido ainda
        self.accept()


class FoldersTab(QWidget):
    """Configura o par pasta do Drive → destino local."""

    changed = Signal()

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        pair = config.sync.pairs[0] if config.sync.pairs else None
        self._folder_id = pair.drive_folder_id if pair else ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = Card(S.FOLDERS_TITLE, S.FOLDERS_DESC)

        self._drive_field = QLineEdit(self._folder_id or S.FOLDERS_NONE)
        self._drive_field.setReadOnly(True)
        pick = button(S.FOLDERS_DRIVE_CHOOSE)
        pick.clicked.connect(self._pick_drive_folder)
        card.add_row(S.FOLDERS_DRIVE, row(self._drive_field, pick, stretch_last=True))

        self._local_field = QLineEdit(str(pair.local_path) if pair else "")
        self._local_field.setReadOnly(True)
        browse = button(S.FOLDERS_LOCAL_CHOOSE)
        browse.clicked.connect(self._pick_local)
        card.add_row(S.FOLDERS_LOCAL, row(self._local_field, browse, stretch_last=True))

        self._space = label("", "meta")
        card.add(self._space)

        layout.addWidget(card)
        layout.addStretch(1)
        self._refresh_space()

        # Mostrar "1a2b3c..." não diz nada a ninguém: busca o nome real da pasta.
        self._resolver: _NameResolver | None = None
        if self._folder_id:
            self._resolver = _NameResolver(config, self._folder_id, self)
            self._resolver.resolved.connect(self._on_name_resolved)
            self._resolver.start()

    def _on_name_resolved(self, name: str) -> None:
        if name:
            self._drive_field.setText(f"{name}  ({self._folder_id})")

    # --- Dados ------------------------------------------------------------

    def apply_to(self, config: Config) -> Config:
        local = self._local_field.text().strip()
        pairs = (
            [SyncPair(drive_folder_id=self._folder_id, local_path=Path(local))]
            if self._folder_id and local
            else list(config.sync.pairs)
        )
        sync = SyncConfig(
            pairs=pairs,
            interval_minutes=config.sync.interval_minutes,
            bandwidth_limit_mbps=config.sync.bandwidth_limit_mbps,
            export_google_docs=config.sync.export_google_docs,
            export_formats=config.sync.export_formats,
        )
        return Config(
            auth=config.auth,
            sync=sync,
            notifications=config.notifications,
            heartbeat=config.heartbeat,
            logging=config.logging,
        )

    def set_config(self, config: Config) -> None:
        self._config = config
        if config.sync.pairs:
            pair = config.sync.pairs[0]
            self._folder_id = pair.drive_folder_id
            self._drive_field.setText(pair.drive_folder_id)
            self._local_field.setText(str(pair.local_path))
        self._refresh_space()

    # --- Ações ------------------------------------------------------------

    def _pick_drive_folder(self) -> None:
        picker = DriveFolderPicker(self._config, self)
        if picker.exec() == QDialog.DialogCode.Accepted and picker.selected:
            self._folder_id = picker.selected.id
            self._drive_field.setText(f"{picker.selected.name}  ({picker.selected.id})")
            self.changed.emit()

    def _pick_local(self) -> None:
        path = QFileDialog.getExistingDirectory(self, S.FOLDERS_LOCAL_CHOOSE)
        if path:
            self._local_field.setText(path)
            self._refresh_space()
            self.changed.emit()

    def _refresh_space(self) -> None:
        path = self._local_field.text().strip()
        if not path:
            set_text(self._space, "")
            return
        if not disk.drive_available(path):
            set_text(self._space, S.FOLDERS_DISK_MISSING)
            return
        try:
            free = disk.free_space_bytes(path)
        except OSError:
            set_text(self._space, S.FOLDERS_DISK_MISSING)
            return
        set_text(self._space, S.FOLDERS_FREE_SPACE.format(free=human_size(free)))
