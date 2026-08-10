"""Ícone de bandeja com 3 estados e menu de contexto (SPEC.md §5).

Verde = tudo sincronizado, amarelo = sincronizando, vermelho = ação necessária
(mais cinza para pausado). O tooltip repete o estado em texto — cor sozinha não
é acessível para quem não distingue verde de vermelho.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

from ui import strings as S
from ui.icons import TrayState, tray_icon


class Tray(QSystemTrayIcon):
    """Bandeja: estado do backup e ações rápidas."""

    open_requested = Signal()
    check_requested = Signal()
    pause_toggled = Signal(bool)
    quit_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._paused = False

        menu = QMenu()
        self._open_action = QAction(S.TRAY_OPEN, menu)
        self._open_action.triggered.connect(self.open_requested)
        menu.addAction(self._open_action)

        self._check_action = QAction(S.TRAY_CHECK_NOW, menu)
        self._check_action.triggered.connect(self.check_requested)
        menu.addAction(self._check_action)

        self._pause_action = QAction(S.TRAY_PAUSE, menu)
        self._pause_action.triggered.connect(self._toggle_pause)
        menu.addAction(self._pause_action)

        menu.addSeparator()
        quit_action = QAction(S.TRAY_QUIT, menu)
        quit_action.triggered.connect(self.quit_requested)
        menu.addAction(quit_action)

        self._menu = menu  # guardar referência: sem isso o menu é coletado
        self.setContextMenu(menu)
        self.activated.connect(self._on_activated)
        self.set_state(TrayState.OK, S.STATUS_NEVER_RAN)

    def set_state(self, state: TrayState, tooltip: str) -> None:
        self.setIcon(tray_icon(state))
        self.setToolTip(f"{S.APP_NAME} — {tooltip}")

    def _toggle_pause(self) -> None:
        self._paused = not self._paused
        self._pause_action.setText(S.TRAY_RESUME if self._paused else S.TRAY_PAUSE)
        self.pause_toggled.emit(self._paused)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.open_requested.emit()

    def notify(self, title: str, message: str) -> None:
        """Balão do Windows — complementa o ntfy quando o PC está à mão."""
        self.showMessage(title, message, self.icon())
