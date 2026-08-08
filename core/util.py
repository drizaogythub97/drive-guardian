"""Utilidades pequenas e sem dependências externas."""

from __future__ import annotations


def human_size(num_bytes: int | None) -> str:
    """Formata bytes em unidade legível (ex.: '1.4 MB'). ``None`` -> '—'."""
    if num_bytes is None:
        return "—"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"
