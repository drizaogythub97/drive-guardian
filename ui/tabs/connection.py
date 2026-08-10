"""Aba Conexão: credencial, e-mail para compartilhar a pasta e teste de acesso.

O e-mail da conta de serviço em destaque é o item mais importante da aba: sem
compartilhar a pasta do Drive com ele, nada funciona — e essa é a etapa que mais
confunde quem instala o app pela primeira vez.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from core.auth import build_auth
from core.config import AuthConfig, Config
from core.drive import build_service, list_folders
from ui import strings as S
from ui.widgets import Card, badge, button, label, row, set_badge, set_text


class _ConnectionTest(QThread):
    """Testa a credencial fora da thread da UI (chamada de rede, pode demorar)."""

    done = Signal(bool, str)

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config

    def run(self) -> None:
        try:
            service = build_service(build_auth(self._config.auth))
            folders = list_folders(service)
            self.done.emit(True, S.CONN_OK.format(n=len(folders)))
        except Exception as exc:
            self.done.emit(False, S.CONN_FAIL.format(error=exc))


class ConnectionTab(QWidget):
    """Estado da credencial + ação de teste."""

    changed = Signal()

    def __init__(self, config: Config, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config = config
        self._test: _ConnectionTest | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = Card(S.CONN_TITLE, S.CONN_DESC)

        self._key_field = QLineEdit(str(config.auth.service_account_key or ""))
        self._key_field.setReadOnly(True)
        choose = button(S.CONN_KEY_CHOOSE)
        choose.clicked.connect(self._choose_key)
        card.add_row(S.CONN_KEY_FILE, row(self._key_field, choose, stretch_last=True))

        self._email = QLineEdit()
        self._email.setReadOnly(True)
        copy = button(S.CONN_COPY)
        copy.clicked.connect(self._copy_email)
        card.add_row(S.CONN_SA_EMAIL, row(self._email, copy, stretch_last=True))

        self._test_button = button(S.CONN_TEST, primary=True)
        self._test_button.clicked.connect(self._run_test)
        self._status = badge(S.CONN_UNTESTED, "neutral")
        card.add(row(self._test_button, self._status))

        self._result = label("", "muted")
        self._result.setVisible(False)
        card.add(self._result)

        layout.addWidget(card)
        layout.addStretch(1)
        self._refresh_email()

    # --- Dados ------------------------------------------------------------

    def apply_to(self, config: Config) -> Config:
        """Devolve o config com o que esta aba controla."""
        key = self._key_field.text().strip()
        auth = AuthConfig(
            strategy=config.auth.strategy,
            service_account_key=Path(key) if key else None,
        )
        return Config(
            auth=auth,
            sync=config.sync,
            notifications=config.notifications,
            heartbeat=config.heartbeat,
            logging=config.logging,
        )

    def set_config(self, config: Config) -> None:
        self._config = config
        self._key_field.setText(str(config.auth.service_account_key or ""))
        self._refresh_email()

    # --- Ações ------------------------------------------------------------

    def _choose_key(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, S.CONN_KEY_CHOOSE, "", "JSON (*.json)"
        )
        if path:
            self._key_field.setText(path)
            self._refresh_email()
            self.changed.emit()

    def _refresh_email(self) -> None:
        """Lê o ``client_email`` do JSON sem autenticar (não precisa de rede)."""
        key = self._key_field.text().strip()
        if not key or not Path(key).is_file():
            self._email.setText(S.CONN_NO_KEY)
            return
        try:
            import json

            data = json.loads(Path(key).read_text(encoding="utf-8"))
            self._email.setText(str(data.get("client_email", "")) or S.CONN_NO_KEY)
        except Exception:
            self._email.setText(S.CONN_NO_KEY)

    def _copy_email(self) -> None:
        clipboard = QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self._email.text())
            set_text(self._result, S.CONN_COPIED)

    def _run_test(self) -> None:
        self._test_button.setEnabled(False)
        self._test_button.setText(S.CONN_TESTING)
        set_badge(self._status, S.CONN_TESTING, "neutral")

        self._test = _ConnectionTest(self.apply_to(self._config), self)
        self._test.done.connect(self._on_test_done)
        self._test.start()

    def _on_test_done(self, ok: bool, message: str) -> None:
        self._test_button.setEnabled(True)
        self._test_button.setText(S.CONN_TEST)
        set_badge(self._status, "OK" if ok else "Falhou", "ok" if ok else "error")
        set_text(self._result, message)
