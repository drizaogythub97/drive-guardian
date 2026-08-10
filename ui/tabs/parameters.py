"""Aba Parâmetros: intervalo, banda, avisos no celular, heartbeat e startup.

Cada assunto num cartão próprio (sincronização / avisos / aviso de parada), com o
cabeçalho separado do controle por divisor — é o que impede a tela de virar um
paredão de campos.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.alerts import AlertManager
from core.config import (
    MIN_INTERVAL_MINUTES,
    Config,
    HeartbeatConfig,
    NotificationsConfig,
    NtfyConfig,
    SyncConfig,
)
from core.logger import get_logger
from core.notifier import build_notifier
from core.paths import state_db_path
from core.state import State
from ui import startup
from ui import strings as S
from ui.widgets import Card, button, label, row, set_text


class ParametersTab(QWidget):
    """Ajustes gerais do app."""

    changed = Signal()

    def __init__(self, config: Config, config_path: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._config_path = config_path

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(self._build_sync_card(config))
        layout.addWidget(self._build_alerts_card(config))
        layout.addWidget(self._build_heartbeat_card(config))
        layout.addStretch(1)

    # --- Cartões ----------------------------------------------------------

    def _build_sync_card(self, config: Config) -> Card:
        card = Card(S.PARAMS_SYNC_TITLE)

        self._interval = QSpinBox()
        self._interval.setRange(MIN_INTERVAL_MINUTES, 1440)
        self._interval.setValue(config.sync.interval_minutes)
        self._interval.setSuffix(S.PARAMS_INTERVAL_SUFFIX)
        self._interval.valueChanged.connect(self.changed)
        card.add_row(S.PARAMS_INTERVAL, self._interval)

        self._bandwidth = QSpinBox()
        self._bandwidth.setRange(0, 10_000)
        self._bandwidth.setValue(config.sync.bandwidth_limit_mbps)
        self._bandwidth.setSuffix(S.PARAMS_BANDWIDTH_SUFFIX)
        self._bandwidth.valueChanged.connect(self.changed)
        card.add_row(S.PARAMS_BANDWIDTH, self._bandwidth)

        self._startup = QCheckBox(S.PARAMS_STARTUP)
        self._startup.setChecked(startup.is_enabled())
        self._startup.setEnabled(startup.is_supported())
        self._startup.toggled.connect(self._toggle_startup)
        card.add(self._startup)
        return card

    def _build_alerts_card(self, config: Config) -> Card:
        card = Card(S.PARAMS_ALERTS_TITLE)
        notif = config.notifications

        self._ntfy_enabled = QCheckBox(S.PARAMS_NTFY_ENABLED)
        self._ntfy_enabled.setChecked(notif.ntfy.enabled)
        self._ntfy_enabled.toggled.connect(self.changed)
        card.add(self._ntfy_enabled)

        self._ntfy_server = QLineEdit(notif.ntfy.server)
        self._ntfy_server.textChanged.connect(self.changed)
        card.add_row(S.PARAMS_NTFY_SERVER, self._ntfy_server)

        self._ntfy_topic = QLineEdit(notif.ntfy.topic)
        self._ntfy_topic.textChanged.connect(self.changed)
        card.add_row(S.PARAMS_NTFY_TOPIC, self._ntfy_topic)
        card.add(label(S.PARAMS_NTFY_TOPIC_HINT, "meta"))

        self._summary = QCheckBox(S.PARAMS_SUMMARY)
        self._summary.setChecked(notif.weekly_summary)
        self._summary.toggled.connect(self.changed)
        card.add(self._summary)

        self._summary_day = QComboBox()
        for value, text in S.WEEKDAYS:
            self._summary_day.addItem(text, value)
        index = self._summary_day.findData(notif.summary_day.lower())
        self._summary_day.setCurrentIndex(index if index >= 0 else len(S.WEEKDAYS) - 1)
        self._summary_day.currentIndexChanged.connect(self.changed)

        self._summary_hour = QSpinBox()
        self._summary_hour.setRange(0, 23)
        self._summary_hour.setValue(notif.summary_hour)
        self._summary_hour.valueChanged.connect(self.changed)

        card.add_row(S.PARAMS_SUMMARY_DAY, self._summary_day)
        card.add_row(S.PARAMS_SUMMARY_HOUR, self._summary_hour)

        self._test_button = button(S.PARAMS_TEST_ALERT)
        self._test_button.clicked.connect(self._send_test_alert)
        self._test_result = label("", "meta")
        self._test_result.setVisible(False)
        card.add(row(self._test_button))
        card.add(self._test_result)
        return card

    def _build_heartbeat_card(self, config: Config) -> Card:
        card = Card(S.PARAMS_HEARTBEAT_TITLE)

        self._hb_enabled = QCheckBox(S.PARAMS_HEARTBEAT_ENABLED)
        self._hb_enabled.setChecked(config.heartbeat.enabled)
        self._hb_enabled.toggled.connect(self.changed)
        card.add(self._hb_enabled)

        self._hb_url = QLineEdit(config.heartbeat.url)
        self._hb_url.textChanged.connect(self.changed)
        card.add_row(S.PARAMS_HEARTBEAT_URL, self._hb_url)
        card.add(label(S.PARAMS_HEARTBEAT_HINT, "meta"))
        return card

    # --- Dados ------------------------------------------------------------

    def apply_to(self, config: Config) -> Config:
        sync = SyncConfig(
            pairs=config.sync.pairs,
            interval_minutes=self._interval.value(),
            bandwidth_limit_mbps=self._bandwidth.value(),
            export_google_docs=config.sync.export_google_docs,
            export_formats=config.sync.export_formats,
        )
        notifications = NotificationsConfig(
            ntfy=NtfyConfig(
                enabled=self._ntfy_enabled.isChecked(),
                server=self._ntfy_server.text().strip() or "https://ntfy.sh",
                topic=self._ntfy_topic.text().strip(),
            ),
            weekly_summary=self._summary.isChecked(),
            summary_day=str(self._summary_day.currentData()),
            summary_hour=self._summary_hour.value(),
        )
        heartbeat = HeartbeatConfig(
            enabled=self._hb_enabled.isChecked(), url=self._hb_url.text().strip()
        )
        return Config(
            auth=config.auth,
            sync=sync,
            notifications=notifications,
            heartbeat=heartbeat,
            logging=config.logging,
        )

    def set_config(self, config: Config) -> None:
        self._interval.setValue(config.sync.interval_minutes)
        self._bandwidth.setValue(config.sync.bandwidth_limit_mbps)
        self._ntfy_enabled.setChecked(config.notifications.ntfy.enabled)
        self._ntfy_server.setText(config.notifications.ntfy.server)
        self._ntfy_topic.setText(config.notifications.ntfy.topic)
        self._summary.setChecked(config.notifications.weekly_summary)
        self._summary_hour.setValue(config.notifications.summary_hour)
        self._hb_enabled.setChecked(config.heartbeat.enabled)
        self._hb_url.setText(config.heartbeat.url)

    # --- Ações ------------------------------------------------------------

    def _toggle_startup(self, enabled: bool) -> None:
        startup.set_enabled(enabled, self._config_path)

    def _send_test_alert(self) -> None:
        """Usa os valores da tela, não os salvos — testar antes de salvar é o ponto."""
        notifications = NotificationsConfig(
            ntfy=NtfyConfig(
                enabled=self._ntfy_enabled.isChecked(),
                server=self._ntfy_server.text().strip() or "https://ntfy.sh",
                topic=self._ntfy_topic.text().strip(),
            ),
            weekly_summary=self._summary.isChecked(),
            summary_day=str(self._summary_day.currentData()),
            summary_hour=self._summary_hour.value(),
        )
        logger = get_logger()
        with State(state_db_path()) as state:
            alerts = AlertManager(build_notifier(notifications, logger), state, logger)
            sent = alerts.send(
                "teste",
                "Teste do Drive Guardian: se você recebeu isto no celular, os alertas "
                "estão funcionando.",
                tags="white_check_mark",
                force=True,
            )
        set_text(self._test_result, S.PARAMS_TEST_SENT if sent else S.PARAMS_TEST_FAIL)
