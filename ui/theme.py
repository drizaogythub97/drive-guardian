"""Aparência da janela: paleta, escala tipográfica e QSS.

Segue o padrão "Minimalista" do dono adaptado ao desktop: densidade por
**hierarquia tipográfica com saltos claros**, cartões com cabeçalho separado por
divisor, controles segmentados para 2 a 3 opções, listas de linha única e zero
ícone decorativo. Os valores aqui são os "cheios" (desktop), não os de celular.

Um único tema claro, definido por tokens — trocar a paleta é mexer só no topo.
"""

from __future__ import annotations

# --- Tokens de cor ----------------------------------------------------------
BACKGROUND = "#f7f7f8"
SURFACE = "#ffffff"
BORDER = "#e3e3e6"
BORDER_SOFT = "#eeeef0"
TEXT = "#18181b"
TEXT_MUTED = "#6b6b74"
PRIMARY = "#2563eb"
PRIMARY_HOVER = "#1d4ed8"
PRIMARY_SOFT = "#eff4ff"
SUCCESS = "#15803d"
SUCCESS_SOFT = "#eaf6ee"
WARNING = "#b45309"
WARNING_SOFT = "#fdf3e6"
DANGER = "#b91c1c"
DANGER_SOFT = "#fdeced"

# --- Escala tipográfica (px) ------------------------------------------------
FONT_H1 = 20
FONT_SECTION = 15
FONT_BODY = 13
FONT_META = 11
FONT_KPI = 22

# --- Alturas de controle ----------------------------------------------------
HEIGHT_INPUT = 34
HEIGHT_BUTTON = 36
HEIGHT_ROW = 30


def build_stylesheet() -> str:
    """QSS da aplicação inteira."""
    return f"""
    QWidget {{
        background: {BACKGROUND};
        color: {TEXT};
        font-size: {FONT_BODY}px;
        font-family: "Segoe UI", system-ui, sans-serif;
    }}

    /* Rótulos e caixas herdam o fundo do QWidget e desenhariam uma faixa cinza
       por cima do cartão branco. Transparente resolve — e vale para todos. */
    QLabel, QCheckBox, QWidget[role="row"] {{ background: transparent; }}

    /* --- Tipografia --------------------------------------------------- */
    QLabel[role="h1"]      {{ font-size: {FONT_H1}px; font-weight: 600; }}
    QLabel[role="section"] {{ font-size: {FONT_SECTION}px; font-weight: 600; }}
    QLabel[role="muted"]   {{ color: {TEXT_MUTED}; }}
    QLabel[role="meta"]    {{ color: {TEXT_MUTED}; font-size: {FONT_META}px; }}
    QLabel[role="kpi"]     {{ font-size: {FONT_KPI}px; font-weight: 600; }}
    QLabel[role="mono"]    {{ font-family: Consolas, "Cascadia Mono", monospace; }}

    /* --- Cartão: cabeçalho separado do controle por um divisor -------- */
    QFrame[role="card"] {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
    }}
    QFrame[role="cardHeader"] {{
        background: transparent;
        border: none;
        border-bottom: 1px solid {BORDER_SOFT};
    }}
    QFrame[role="divider"] {{
        background: {BORDER_SOFT};
        border: none;
        max-height: 1px;
        min-height: 1px;
    }}

    /* --- Botões -------------------------------------------------------- */
    QPushButton {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 0 14px;
        min-height: {HEIGHT_BUTTON}px;
    }}
    QPushButton:hover  {{ border-color: #cfcfd4; }}
    QPushButton:disabled {{ color: {TEXT_MUTED}; background: {BACKGROUND}; }}
    QPushButton[role="primary"] {{
        background: {PRIMARY};
        border-color: {PRIMARY};
        color: #ffffff;
        font-weight: 600;
    }}
    QPushButton[role="primary"]:hover {{ background: {PRIMARY_HOVER}; }}
    /* Desligado tem de parecer desligado: um azul mais claro ainda lê como
       "botão azul, pode clicar". Cinza com texto apagado não deixa dúvida. */
    QPushButton[role="primary"]:disabled {{
        background: {BACKGROUND};
        border-color: {BORDER};
        color: {TEXT_MUTED};
        font-weight: 400;
    }}

    /* Botões de menos e mais do campo numérico (ver `widgets.stepper`). */
    QPushButton[role="stepper"] {{
        min-width: 38px;
        max-width: 38px;
        padding: 0;
        font-size: {FONT_SECTION}px;
        font-weight: 600;
        color: {TEXT};
    }}
    QPushButton[role="stepper"]:hover {{ background: {PRIMARY_SOFT}; border-color: {PRIMARY}; }}

    /* Controle segmentado: 2 a 3 opções lado a lado, altura igual */
    QPushButton[role="segment"] {{
        border-radius: 0;
        padding: 0 16px;
        min-height: 32px;
    }}
    QPushButton[role="segment"]:checked {{
        background: {PRIMARY_SOFT};
        border-color: {PRIMARY};
        color: {PRIMARY};
        font-weight: 600;
    }}

    /* --- Campos -------------------------------------------------------- */
    QLineEdit, QSpinBox, QComboBox {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 6px;
        padding: 0 10px;
        min-height: {HEIGHT_INPUT}px;
        selection-background-color: {PRIMARY};
    }}
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {PRIMARY}; }}
    /* Ao estilizar o QSpinBox o Qt para de desenhar as setas nativas: elas
       ficam invisíveis e a área de clique colapsa (todo clique virava "-1").
       Escondemos os sub-botões de vez e usamos os botões de menos/mais do `stepper`. */
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0; height: 0; border: none; }}
    QLineEdit:read-only {{ background: {BACKGROUND}; color: {TEXT_MUTED}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}

    QCheckBox {{ spacing: 8px; min-height: 26px; }}

    /* --- Abas ---------------------------------------------------------- */
    QTabWidget::pane {{ border: none; }}
    QTabBar::tab {{
        background: transparent;
        padding: 8px 14px;
        margin-right: 2px;
        border: none;
        border-bottom: 2px solid transparent;
        color: {TEXT_MUTED};
    }}
    QTabBar::tab:selected {{
        color: {TEXT};
        font-weight: 600;
        border-bottom-color: {PRIMARY};
    }}

    /* --- Listas e tabelas ---------------------------------------------- */
    QTableWidget, QListWidget {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
        gridline-color: {BORDER_SOFT};
    }}
    QTableWidget::item, QListWidget::item {{ padding: 6px 8px; }}
    QTableWidget::item:selected, QListWidget::item:selected {{
        background: {PRIMARY_SOFT};
        color: {TEXT};
    }}
    QHeaderView::section {{
        background: {BACKGROUND};
        border: none;
        border-bottom: 1px solid {BORDER};
        padding: 6px 8px;
        font-size: {FONT_META}px;
        color: {TEXT_MUTED};
        font-weight: 600;
    }}

    /* --- Pílulas de status --------------------------------------------- */
    QLabel[badge="ok"] {{
        background: {SUCCESS_SOFT}; color: {SUCCESS};
        border-radius: 10px; padding: 2px 10px; font-size: {FONT_META}px; font-weight: 600;
    }}
    QLabel[badge="warn"] {{
        background: {WARNING_SOFT}; color: {WARNING};
        border-radius: 10px; padding: 2px 10px; font-size: {FONT_META}px; font-weight: 600;
    }}
    QLabel[badge="error"] {{
        background: {DANGER_SOFT}; color: {DANGER};
        border-radius: 10px; padding: 2px 10px; font-size: {FONT_META}px; font-weight: 600;
    }}
    QLabel[badge="neutral"] {{
        background: {BORDER_SOFT}; color: {TEXT_MUTED};
        border-radius: 10px; padding: 2px 10px; font-size: {FONT_META}px; font-weight: 600;
    }}

    QScrollArea {{ border: none; background: transparent; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: #d4d4d8; border-radius: 5px; min-height: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    """
