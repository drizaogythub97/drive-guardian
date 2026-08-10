"""Formatação da aba Atividade (sem Qt: roda no CI)."""

from __future__ import annotations

from datetime import UTC, datetime

from ui.formatting import clean_message, format_time, level_text


def test_format_time_converts_utc_to_local() -> None:
    moment = datetime(2026, 8, 10, 14, 29, 55, tzinfo=UTC)
    expected = moment.astimezone().strftime("%d/%m %H:%M:%S")
    assert format_time(moment.isoformat()) == expected


def test_format_time_survives_garbage() -> None:
    assert format_time("não é data") == "não é data"[:19]


def test_level_text_translates_known_levels() -> None:
    assert level_text("INFO") == "Normal"
    assert level_text("warning") == "Atenção"
    assert level_text("CRITICAL") == "Crítico"
    assert level_text("TRACE") == "TRACE"  # desconhecido passa direto


def test_clean_message_strips_legacy_marker() -> None:
    assert clean_message("[alerta:disco] O backup parou.") == "O backup parou."


def test_clean_message_leaves_normal_text_alone() -> None:
    text = "Baixado foto.jpg (versão anterior preservada em _versões/)"
    assert clean_message(text) == text
    # Um colchete no começo que não é marcador não pode ser comido.
    assert clean_message("[importante] leia") == "[importante] leia"
