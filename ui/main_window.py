"""Janela principal: cabeçalho com status + as quatro abas do SPEC §5.

Fechar a janela **não** encerra o app — ele volta para a bandeja e continua
sincronizando. Sair de verdade é pelo menu da bandeja, para ninguém desligar o
backup sem querer ao clicar no X.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.config import Config, save_config
from core.sync import CycleReport
from ui import icons
from ui import strings as S
from ui.tabs.activity import ActivityTab
from ui.tabs.connection import ConnectionTab
from ui.tabs.folders import FoldersTab
from ui.tabs.parameters import ParametersTab
from ui.widgets import badge, button, label, scrollable, set_badge


class MainWindow(QMainWindow):
    """Janela de configuração e acompanhamento."""

    config_saved = Signal(object)  # Config
    check_requested = Signal()

    def __init__(self, config: Config, config_path: str) -> None:
        super().__init__()
        self._config = config
        self._config_path = config_path
        self._dirty = False

        self.setWindowTitle(S.APP_NAME)
        self.setWindowIcon(icons.app_icon())
        self.resize(880, 660)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)
        layout.addWidget(self._build_header())

        self.connection_tab = ConnectionTab(config)
        self.folders_tab = FoldersTab(config)
        self.parameters_tab = ParametersTab(config, config_path)
        self.activity_tab = ActivityTab()

        for tab in (self.connection_tab, self.folders_tab, self.parameters_tab):
            tab.changed.connect(self._mark_dirty)

        self._tabs = QTabWidget()
        self._tabs.setUsesScrollButtons(False)
        self._tabs.addTab(scrollable(self.connection_tab), S.TAB_CONNECTION)
        self._tabs.addTab(scrollable(self.folders_tab), S.TAB_FOLDERS)
        self._tabs.addTab(scrollable(self.parameters_tab), S.TAB_PARAMETERS)
        self._tabs.addTab(self.activity_tab, S.TAB_ACTIVITY)
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs, 1)

        self.setCentralWidget(central)

    # --- Cabeçalho --------------------------------------------------------

    def _build_header(self) -> QWidget:
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label(S.APP_NAME, "h1", wrap=False))
        titles.addWidget(label(S.APP_TAGLINE, "muted", wrap=False))
        layout.addLayout(titles)
        layout.addStretch(1)

        self._status = badge(S.STATUS_NEVER_RAN, "neutral")
        layout.addWidget(self._status)

        self._check_button = button(S.TRAY_CHECK_NOW)
        self._check_button.clicked.connect(self.check_requested)
        layout.addWidget(self._check_button)

        self._save_button = button(S.SAVE, primary=True)
        self._save_button.clicked.connect(self.save)
        self._save_button.setEnabled(False)
        layout.addWidget(self._save_button)
        return container

    # --- Estado -----------------------------------------------------------

    def _mark_dirty(self) -> None:
        self._dirty = True
        self._save_button.setEnabled(True)

    def _on_tab_changed(self, index: int) -> None:
        if self._tabs.widget(index) is self.activity_tab:
            self.activity_tab.refresh()

    def collect_config(self) -> Config:
        """Junta o que as três abas de configuração controlam."""
        config = self.connection_tab.apply_to(self._config)
        config = self.folders_tab.apply_to(config)
        return self.parameters_tab.apply_to(config)

    def save(self) -> bool:
        try:
            config = self.collect_config()
            save_config(config, self._config_path)
        except Exception as exc:
            QMessageBox.warning(self, S.APP_NAME, S.SAVE_FAILED.format(error=exc))
            return False

        self._config = config
        self._dirty = False
        self._save_button.setEnabled(False)
        self.set_status(S.SAVED, "ok")
        self.config_saved.emit(config)
        return True

    def set_status(self, text: str, kind: str = "neutral") -> None:
        set_badge(self._status, text, kind)

    # --- Reações aos sinais do worker -------------------------------------

    def on_cycle_started(self) -> None:
        self.set_status(S.STATUS_SYNCING, "warn")

    def on_cycle_finished(self, report: CycleReport) -> None:
        self.set_status(S.STATUS_OK if not report.failed else S.STATUS_ACTION_NEEDED,
                        "ok" if not report.failed else "error")
        self.activity_tab.refresh()

    def on_cycle_failed(self, message: str, critical: bool) -> None:
        self.set_status(S.STATUS_ACTION_NEEDED, "error")
        self.activity_tab.refresh()
        if critical:
            QMessageBox.critical(self, S.APP_NAME, S.CYCLE_ERROR.format(error=message))

    # --- Fechamento -------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        """X fecha a janela, não o app: o backup continua na bandeja."""
        if self._dirty:
            answer = QMessageBox.question(
                self,
                S.UNSAVED_TITLE,
                S.UNSAVED_BODY,
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
            )
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Save and not self.save():
                event.ignore()
                return
        self.hide()
        event.ignore()
