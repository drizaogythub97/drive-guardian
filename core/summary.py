"""Resumo semanal (SPEC.md §4): arquivos novos, bytes, versões criadas, erros pendentes.

Os números saem da tabela ``cycles`` (um registro por ciclo, gravado pelo
``SyncEngine``) — não de contagem de linhas de log, que mudaria de sentido a cada
ajuste de mensagem.

O agendamento é "preguiçoso": não há thread de cron. A cada ciclo o ``watch``
pergunta ``due()``, que responde ``True`` quando já passou do dia/hora configurados
e ainda não houve envio nesta semana. Isso sobrevive a máquina desligada — se o PC
estava off no domingo às 20h, o resumo sai no primeiro ciclo depois disso.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from core.config import NotificationsConfig
from core.state import STATUS_FAILED, STATUS_REMOTE_DELETED, State
from core.util import human_size

# Nome do dia na config -> índice de ``datetime.weekday()`` (segunda = 0).
_WEEKDAYS: dict[str, int] = {
    "monday": 0, "segunda": 0,
    "tuesday": 1, "terca": 1, "terça": 1,
    "wednesday": 2, "quarta": 2,
    "thursday": 3, "quinta": 3,
    "friday": 4, "sexta": 4,
    "saturday": 5, "sabado": 5, "sábado": 5,
    "sunday": 6, "domingo": 6,
}
_DEFAULT_WEEKDAY = 6  # domingo


@dataclass(frozen=True)
class WeeklySummary:
    """Números da semana, prontos para virar texto."""

    downloaded: int
    versioned: int
    failed: int
    remote_deleted: int
    bytes_downloaded: int
    cycles: int
    pending_errors: int
    kept_after_remote_delete: int

    def as_message(self) -> str:
        linhas = [
            f"Resumo da semana: {self.downloaded} arquivo(s) baixado(s) "
            f"({human_size(self.bytes_downloaded)}).",
            f"Versões criadas: {self.versioned}.",
            f"Sumiram do Drive (cópia local mantida): {self.remote_deleted}.",
            f"Ciclos executados: {self.cycles}.",
        ]
        if self.pending_errors:
            linhas.append(f"⚠ {self.pending_errors} arquivo(s) com erro pendente.")
        else:
            linhas.append("Nenhum erro pendente.")
        linhas.append(
            f"Total preservado localmente após exclusão no Drive: "
            f"{self.kept_after_remote_delete} arquivo(s)."
        )
        return "\n".join(linhas)


def weekday_index(name: str) -> int:
    """Índice de ``datetime.weekday()`` para o dia configurado (domingo por padrão)."""
    return _WEEKDAYS.get(name.strip().lower(), _DEFAULT_WEEKDAY)


def build_summary(state: State, *, since: datetime | None = None) -> WeeklySummary:
    """Agrega os ciclos dos últimos 7 dias (ou desde ``since``)."""
    start = since or (datetime.now(UTC) - timedelta(days=7))
    cycles = state.cycles_since(start.isoformat())
    by_status = state.count_by_status()
    return WeeklySummary(
        downloaded=sum(c.downloaded for c in cycles),
        versioned=sum(c.versioned for c in cycles),
        failed=sum(c.failed for c in cycles),
        remote_deleted=sum(c.remote_deleted for c in cycles),
        bytes_downloaded=sum(c.bytes_downloaded for c in cycles),
        cycles=len(cycles),
        pending_errors=by_status.get(STATUS_FAILED, 0),
        kept_after_remote_delete=by_status.get(STATUS_REMOTE_DELETED, 0),
    )


def due(config: NotificationsConfig, state: State, *, now: datetime | None = None) -> bool:
    """O resumo desta semana já deveria ter saído e ainda não saiu?"""
    if not config.weekly_summary:
        return False

    moment = now or datetime.now(UTC)
    scheduled = _scheduled_time(config, moment)
    if moment < scheduled:
        return False  # ainda não chegou a hora desta semana

    last_raw = state.get_last_summary()
    if last_raw is None:
        return True
    try:
        last = datetime.fromisoformat(last_raw)
    except ValueError:
        return True
    return last < scheduled


def _scheduled_time(config: NotificationsConfig, moment: datetime) -> datetime:
    """Momento agendado dentro da semana corrente de ``moment``."""
    target = weekday_index(config.summary_day)
    days_back = (moment.weekday() - target) % 7
    day = (moment - timedelta(days=days_back)).date()
    hour = max(0, min(23, config.summary_hour))
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)
