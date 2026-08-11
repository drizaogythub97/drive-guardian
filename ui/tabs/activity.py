"""Aba Atividade: o log de movimentações e os números do último ciclo.

Esta é a aba que o dono pediu explicitamente (10/08/2026): toda movimentação
registrada e visível para controle. A fonte é a tabela ``events`` do SQLite — a
mesma que o `cli.py events` imprime — e os contadores vêm de ``cycles``.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QGridLayout,
    QHeaderView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.state import STATUS_REMOTE_DELETED, State
from core.util import human_size
from ui import strings as S
from ui.formatting import clean_message, format_time, level_text
from ui.widgets import Card, Kpi, Segmented, button, label, row

# Filtros do segmentado -> níveis de log consultados.
_FILTERS: dict[str, tuple[str, ...]] = {
    "all": (),
    "info": ("INFO",),
    "problem": ("WARNING", "ERROR", "CRITICAL"),
}
_EVENT_LIMIT = 300


class ActivityTab(QWidget):
    """Tabela de eventos + KPIs do último ciclo."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._filter = "all"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(self._build_kpis())
        layout.addWidget(self._build_log_card(), 1)
        self.refresh()

    # --- Construção -------------------------------------------------------

    def _build_kpis(self) -> QWidget:
        container = QWidget()
        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(10)

        self._kpi_downloaded = Kpi(S.KPI_DOWNLOADED)
        self._kpi_versioned = Kpi(S.KPI_VERSIONED)
        self._kpi_failed = Kpi(S.KPI_FAILED)
        self._kpi_kept = Kpi(S.KPI_KEPT)
        for index, kpi in enumerate(
            (self._kpi_downloaded, self._kpi_versioned, self._kpi_failed, self._kpi_kept)
        ):
            grid.addWidget(kpi, 0, index)

        self._last_cycle = label("", "meta")
        grid.addWidget(self._last_cycle, 1, 0, 1, 4)
        return container

    def _build_log_card(self) -> Card:
        card = Card(S.ACTIVITY_TITLE, S.ACTIVITY_DESC)

        self._segmented = Segmented(
            [
                ("all", S.ACTIVITY_FILTER_ALL),
                ("info", S.ACTIVITY_FILTER_INFO),
                ("problem", S.ACTIVITY_FILTER_PROBLEM),
            ]
        )
        self._segmented.changed.connect(self._on_filter)

        refresh = button(S.ACTIVITY_REFRESH)
        refresh.clicked.connect(self.refresh)
        export = button(S.ACTIVITY_EXPORT)
        export.clicked.connect(self._export)
        card.add(row(self._segmented, refresh, export))

        # Sem isto o "Atualizar" não dá sinal nenhum: a leitura do banco é
        # instantânea e a tabela costuma vir igual, então o clique parece
        # ignorado. O carimbo de hora muda a cada clique e prova o contrário.
        self._refreshed = label("", "meta")
        card.add(self._refreshed)

        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(
            [S.ACTIVITY_COL_TIME, S.ACTIVITY_COL_LEVEL, S.ACTIVITY_COL_MESSAGE]
        )
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        card.body().addWidget(self._table, 1)
        return card

    # --- Dados ------------------------------------------------------------

    def refresh(self) -> None:
        """Relê o banco. Chamada ao abrir a aba e ao fim de cada ciclo."""
        with State() as state:
            rows = state.recent_events(limit=_EVENT_LIMIT, levels=_FILTERS[self._filter])
            cycles = state.recent_cycles(limit=1)
            counts = state.count_by_status()

        self._fill_table(rows)
        self._refreshed.setText(
            S.ACTIVITY_REFRESHED.format(time=datetime.now().strftime("%H:%M:%S"), n=len(rows))
        )

        if cycles:
            last = cycles[0]
            self._kpi_downloaded.set_value(str(last.downloaded))
            self._kpi_versioned.set_value(str(last.versioned))
            self._kpi_failed.set_value(str(last.failed))
            self._last_cycle.setText(
                f"{S.KPI_LAST_CYCLE}: {format_time(last.finished_at)} — "
                f"{last.kind}, {human_size(last.bytes_downloaded)} transferidos"
            )
        else:
            self._last_cycle.setText(f"{S.KPI_LAST_CYCLE}: {S.KPI_NEVER}")

        self._kpi_kept.set_value(str(counts.get(STATUS_REMOTE_DELETED, 0)))

    def _fill_table(self, rows: list) -> None:  # type: ignore[type-arg]
        self._table.setRowCount(len(rows))
        for index, event in enumerate(rows):
            time_item = QTableWidgetItem(format_time(event["ts"]))
            level_item = QTableWidgetItem(level_text(event["level"]))
            text = clean_message(event["message"])
            message_item = QTableWidgetItem(text)
            message_item.setToolTip(text)
            for column, item in enumerate((time_item, level_item, message_item)):
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self._table.setItem(index, column, item)

        if not rows:
            self._table.setRowCount(1)
            self._table.setItem(0, 2, QTableWidgetItem(S.ACTIVITY_EMPTY))

    # --- Ações ------------------------------------------------------------

    def _on_filter(self, value: str) -> None:
        self._filter = value
        self.refresh()

    def _export(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, S.ACTIVITY_EXPORT, "drive-guardian-log.txt", "Texto (*.txt)"
        )
        if not path:
            return
        with State() as state:
            rows = state.recent_events(limit=10_000)
        lines = [
            f"{event['ts']}\t{event['level']}\t{event['category']}\t{event['message']}"
            for event in reversed(rows)
        ]
        Path(path).write_text("\n".join(lines), encoding="utf-8")
        self._last_cycle.setText(S.ACTIVITY_EXPORTED.format(path=path))
