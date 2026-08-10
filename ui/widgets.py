"""Blocos reutilizáveis da janela (cartão, KPI, pílula, segmentado).

Concentrar aqui é o que mantém as quatro abas parecendo a mesma aplicação: quem
escreve uma aba compõe estes blocos em vez de repetir margens e fontes na mão.
"""

from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractButton,
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ui import theme


def label(text: str, role: str = "", *, wrap: bool = True) -> QLabel:
    """``QLabel`` já com o papel tipográfico do tema.

    Títulos passam ``wrap=False``: quebrar "Drive Guardian" em duas linhas por
    causa de alguns pixels faz a janela parecer quebrada.
    """
    widget = QLabel(text)
    if role:
        widget.setProperty("role", role)
    widget.setWordWrap(wrap)
    return widget


def scrollable(content: QWidget) -> QScrollArea:
    """Envolve o conteúdo de uma aba numa área rolável.

    A aba Parâmetros passa da altura da janela em telas menores; sem isto os
    últimos campos ficariam inalcançáveis.
    """
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.Shape.NoFrame)
    area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
    area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    area.setWidget(content)
    return area


def badge(text: str, kind: str = "neutral") -> QLabel:
    """Pílula de status (ok / warn / error / neutral)."""
    widget = QLabel(text)
    widget.setProperty("badge", kind)
    widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return widget


def set_badge(widget: QLabel, text: str, kind: str) -> None:
    """Troca texto e cor de uma pílula já criada (revalida o estilo)."""
    widget.setText(text)
    widget.setProperty("badge", kind)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)


def set_text(widget: QLabel, text: str) -> None:
    """Escreve num rótulo de apoio, escondendo-o quando não há o que dizer.

    Um ``QLabel`` vazio continua ocupando altura e deixa uma faixa solta no
    cartão — o olho lê isso como defeito.
    """
    widget.setText(text)
    widget.setVisible(bool(text))


def divider() -> QFrame:
    line = QFrame()
    line.setProperty("role", "divider")
    line.setFrameShape(QFrame.Shape.NoFrame)
    return line


class Card(QFrame):
    """Cartão com cabeçalho separado do conteúdo por um divisor.

    Sem esse divisor a tela vira "um bloco só, tudo grudado" — a explicação
    encosta no controle e o olho não separa o que é texto do que é ação.
    """

    def __init__(self, title: str, description: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")

        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 16)
        outer.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(4)
        header.addWidget(label(title, "section"))
        if description:
            header.addWidget(label(description, "muted"))
        outer.addLayout(header)
        outer.addWidget(divider())

        self._body = QVBoxLayout()
        self._body.setSpacing(10)
        outer.addLayout(self._body)

    def body(self) -> QVBoxLayout:
        return self._body

    def add(self, widget: QWidget) -> None:
        self._body.addWidget(widget)

    def add_row(self, caption: str, widget: QWidget) -> None:
        """Rótulo em cima, controle em largura total — nunca texto espremido ao lado."""
        row = QVBoxLayout()
        row.setSpacing(4)
        row.addWidget(label(caption, "meta"))
        row.addWidget(widget)
        self._body.addLayout(row)


class Segmented(QWidget):
    """Controle segmentado para 2 a 3 opções mutuamente exclusivas."""

    changed = Signal(str)

    def __init__(self, options: Iterable[tuple[str, str]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._values: dict[QAbstractButton, str] = {}

        buttons = list(options)
        for index, (value, text) in enumerate(buttons):
            button = QPushButton(text)
            button.setProperty("role", "segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            # Cantos arredondados só nas pontas, para parecer um controle único.
            if index == 0:
                button.setStyleSheet("border-top-left-radius:6px; border-bottom-left-radius:6px;")
            if index == len(buttons) - 1:
                button.setStyleSheet(
                    button.styleSheet()
                    + "border-top-right-radius:6px; border-bottom-right-radius:6px;"
                )
            self._values[button] = value
            self._group.addButton(button)
            layout.addWidget(button)
        layout.addStretch(1)

        self._group.buttonClicked.connect(self._emit)
        if buttons:
            next(iter(self._values)).setChecked(True)

    def _emit(self, button: QAbstractButton) -> None:
        self.changed.emit(self._values[button])

    def value(self) -> str:
        checked = self._group.checkedButton()
        return self._values.get(checked, "") if checked else ""

    def set_value(self, value: str) -> None:
        for button, candidate in self._values.items():
            if candidate == value:
                button.setChecked(True)
                return


class Kpi(QFrame):
    """Número grande + rótulo curto. Sem ícone e sem texto de apoio."""

    def __init__(self, caption: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("role", "card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(2)
        self._value = label(value, "kpi")
        layout.addWidget(self._value)
        layout.addWidget(label(caption, "meta"))

    def set_value(self, value: str) -> None:
        self._value.setText(value)


def button(text: str, *, primary: bool = False) -> QPushButton:
    widget = QPushButton(text)
    if primary:
        widget.setProperty("role", "primary")
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    return widget


def row(*widgets: QWidget, spacing: int = 8, stretch_last: bool = False) -> QWidget:
    """Fileira horizontal simétrica (nada de quebra com larguras diferentes)."""
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(spacing)
    for widget in widgets:
        layout.addWidget(widget)
    if not stretch_last:
        layout.addStretch(1)
    return container


__all__ = [
    "Card",
    "Kpi",
    "Segmented",
    "badge",
    "button",
    "divider",
    "label",
    "row",
    "scrollable",
    "set_badge",
    "set_text",
    "theme",
]
