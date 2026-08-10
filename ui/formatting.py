"""Formatação de texto da interface — sem nenhuma dependência do Qt.

Fica separado das telas de propósito: assim a lógica de apresentação (que tem
casos de borda de verdade) é testável no CI, que não instala o Qt.
"""

from __future__ import annotations

from datetime import datetime

_LEVEL_LABELS = {
    "INFO": "Normal",
    "WARNING": "Atenção",
    "ERROR": "Erro",
    "CRITICAL": "Crítico",
}
_LEGACY_MARKER = "[alerta:"


def format_time(raw: str) -> str:
    """Carimbo ISO em UTC → data/hora local legível (``10/08 11:29:55``)."""
    try:
        return datetime.fromisoformat(raw).astimezone().strftime("%d/%m %H:%M:%S")
    except ValueError:
        return raw[:19]


def level_text(level: str) -> str:
    """Nível do log em português; níveis desconhecidos passam como estão."""
    return _LEVEL_LABELS.get(level.upper(), level)


def clean_message(message: str) -> str:
    """Remove o prefixo ``[alerta:chave]`` gravado por versões anteriores.

    O formato atual guarda a chave na coluna ``category``, mas bancos criados antes
    disso ainda têm o prefixo no texto — e ele não diz nada para quem lê.
    """
    if message.startswith(_LEGACY_MARKER) and "] " in message:
        return message.split("] ", 1)[1]
    return message
