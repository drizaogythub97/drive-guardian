"""Ponto de entrada da UI: amarra bandeja, janela e thread de sincronização.

O app vive na bandeja: a janela é só uma visita. Por isso ``setQuitOnLastWindowClosed``
é falso — fechar a janela não pode desligar o backup.
"""

from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from core.config import Config, load_config
from core.errors import CriticalError
from core.sync import CycleReport
from ui import icons, theme
from ui import strings as S
from ui.icons import TrayState
from ui.main_window import MainWindow
from ui.tray import Tray
from ui.worker import SyncWorker

DEFAULT_CONFIG = "config.yaml"


class Application:
    """Cola entre bandeja, janela e worker — sem lógica de negócio própria."""

    def __init__(self, config: Config, config_path: str) -> None:
        self.window = MainWindow(config, config_path)
        self.tray = Tray()
        self.worker = SyncWorker(config)

        self.tray.open_requested.connect(self._show_window)
        self.tray.check_requested.connect(self.worker.request_check)
        self.tray.pause_toggled.connect(self._on_pause)
        self.tray.quit_requested.connect(self._quit)

        self.window.check_requested.connect(self.worker.request_check)
        self.window.config_saved.connect(self.worker.apply_config)

        self.worker.cycle_started.connect(self._on_cycle_started)
        self.worker.cycle_finished.connect(self._on_cycle_finished)
        self.worker.cycle_failed.connect(self._on_cycle_failed)

        self.tray.show()
        self.worker.start()

    # --- Reações ----------------------------------------------------------

    def _show_window(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _on_pause(self, paused: bool) -> None:
        self.worker.set_paused(paused)
        if paused:
            self.tray.set_state(TrayState.PAUSED, S.STATUS_PAUSED)
            self.window.set_status(S.STATUS_PAUSED, "neutral")

    def _on_cycle_started(self) -> None:
        self.tray.set_state(TrayState.SYNCING, S.STATUS_SYNCING)
        self.window.on_cycle_started()

    def _on_cycle_finished(self, report: CycleReport) -> None:
        ok = report.failed == 0
        self.tray.set_state(
            TrayState.OK if ok else TrayState.ATTENTION,
            S.STATUS_OK if ok else S.STATUS_ACTION_NEEDED,
        )
        self.window.on_cycle_finished(report)

    def _on_cycle_failed(self, message: str, critical: bool) -> None:
        self.tray.set_state(TrayState.ATTENTION, S.STATUS_ACTION_NEEDED)
        self.window.on_cycle_failed(message, critical)
        if critical:
            self.tray.notify(S.APP_NAME, message.splitlines()[0])

    def _quit(self) -> None:
        self.worker.stop()
        self.worker.wait(5000)
        self.tray.hide()
        QApplication.quit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="drive-guardian-ui", description=S.APP_TAGLINE)
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)

    app = QApplication(sys.argv[:1])
    app.setApplicationName(S.APP_NAME)
    app.setWindowIcon(icons.app_icon())
    app.setStyleSheet(theme.build_stylesheet())
    app.setQuitOnLastWindowClosed(False)

    try:
        config = load_config(args.config)
    except CriticalError as exc:
        # Sem config válida não há o que sincronizar: avisa e sai, em vez de
        # abrir uma janela que não funcionaria.
        QMessageBox.critical(None, S.APP_NAME, str(exc))
        return 1

    application = Application(config, args.config)
    application._show_window()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
