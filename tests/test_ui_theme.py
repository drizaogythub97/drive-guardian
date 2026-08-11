"""Regressões do QSS que quebraram controles de verdade na validação da Fase 3.

`ui.theme` não importa PySide6, então estas asserções rodam no CI sem Qt.
"""

from __future__ import annotations

from ui import theme


def test_spinbox_arrows_are_disabled_in_favour_of_the_stepper() -> None:
    """As setas nativas somem sob QSS e o clique caía sempre no "diminuir".

    Enquanto os botões de menos/mais do `widgets.stepper` forem a forma de mexer no
    número, os sub-botões do QSpinBox têm de continuar zerados.
    """
    qss = theme.build_stylesheet()
    assert "QSpinBox::up-button, QSpinBox::down-button" in qss
    assert "width: 0; height: 0" in qss


def test_disabled_primary_button_is_not_blue() -> None:
    """Botão primário desligado não pode continuar parecendo clicável."""
    qss = theme.build_stylesheet()
    disabled = qss.split('QPushButton[role="primary"]:disabled')[1].split("}")[0]
    assert theme.PRIMARY not in disabled
    assert theme.BACKGROUND in disabled


def test_rows_do_not_paint_over_the_card() -> None:
    """A fileira horizontal herdava o cinza do QWidget e riscava o cartão."""
    assert 'QWidget[role="row"]' in theme.build_stylesheet()
