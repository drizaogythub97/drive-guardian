"""Ícone da bandeja nos 3 estados do SPEC §5 (verde ok / amarelo sincronizando /
vermelho ação necessária).

Desenhado em runtime com ``QPainter`` em vez de arquivos .ico: o PyInstaller da
Fase 4 não precisa empacotar recurso nenhum, e o ícone acompanha a paleta do tema.
Formato: escudo arredondado (o app "guarda" o Drive) com um ponto de status.
"""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QPainter, QPainterPath, QPixmap

from ui import theme

_SIZE = 64


class TrayState(Enum):
    """Os três estados de bandeja previstos no SPEC §5."""

    OK = "ok"
    SYNCING = "syncing"
    ATTENTION = "attention"
    PAUSED = "paused"


_DOT_COLORS: dict[TrayState, str] = {
    TrayState.OK: theme.SUCCESS,
    TrayState.SYNCING: theme.WARNING,
    TrayState.ATTENTION: theme.DANGER,
    TrayState.PAUSED: theme.TEXT_MUTED,
}


def _shield_path(size: int) -> QPainterPath:
    """Escudo simples: ombros retos no topo, afunilando até a ponta embaixo."""
    unit = size / 64.0
    path = QPainterPath()
    path.moveTo(32 * unit, 6 * unit)
    path.lineTo(54 * unit, 15 * unit)
    path.lineTo(54 * unit, 33 * unit)
    path.quadTo(54 * unit, 50 * unit, 32 * unit, 58 * unit)
    path.quadTo(10 * unit, 50 * unit, 10 * unit, 33 * unit)
    path.lineTo(10 * unit, 15 * unit)
    path.closeSubpath()
    return path


def tray_pixmap(state: TrayState, size: int = _SIZE) -> QPixmap:
    """Pixmap do ícone no estado pedido (fundo transparente)."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(theme.TEXT)))
    painter.drawPath(_shield_path(size))

    # Ponto de status no canto inferior direito, com recorte para destacá-lo do escudo.
    unit = size / 64.0
    center = QPointF(46 * unit, 46 * unit)
    radius = 13 * unit
    painter.setBrush(QBrush(QColor(theme.SURFACE)))
    painter.drawEllipse(center, radius + 3 * unit, radius + 3 * unit)
    painter.setBrush(QBrush(QColor(_DOT_COLORS[state])))
    painter.drawEllipse(center, radius, radius)
    painter.end()
    return pixmap


def tray_icon(state: TrayState) -> QIcon:
    """Ícone multi-resolução para a bandeja do Windows."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64):
        icon.addPixmap(tray_pixmap(state, size))
    return icon


def app_icon() -> QIcon:
    """Ícone da janela (estado neutro/ok)."""
    return tray_icon(TrayState.OK)


def dot_pixmap(color: str, size: int = 12) -> QPixmap:
    """Bolinha colorida usada como marcador de status dentro da janela."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(QColor(color)))
    painter.drawEllipse(QRectF(0, 0, size, size))
    painter.end()
    return pixmap
