"""Orquestrador de sincronização (SPEC.md §3): amarra reconciliação, fila,
download atômico e polling incremental. Sem dependência de UI (CLAUDE.md §6).

- ``plan_all()`` — só leitura, base do ``--dry-run`` (não grava nada).
- ``run_once()`` — um ciclo completo (reconciliação + processa fila).
- ``watch()`` — reconciliação no boot e depois ``changes.list`` a cada intervalo,
  com reconciliação completa 1x/dia.

A Fase 2 acrescentou aqui a camada de vigilância: retry de Nível 1, alerta de
Nível 3, heartbeat ao fim de ciclo bem-sucedido, registro de **toda movimentação**
(inclusive o que sumiu do Drive) e o agendamento do resumo semanal.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from typing import Any

from core import disk, summary
from core.alerts import AlertManager
from core.auth import Auth
from core.config import Config, SyncPair
from core.downloader import Downloader
from core.drive import build_service, build_tree, iter_files
from core.errors import CriticalError
from core.heartbeat import Heartbeat
from core.notifier import Notifier, build_notifier
from core.planner import Plan, PlanItem, build_plan
from core.retry import retry_transient
from core.state import STATUS_REMOTE_DELETED, State
from core.watcher import FolderResolver, poll_changes

_SECONDS_PER_DAY = 86_400

KIND_FULL = "completo"
KIND_INCREMENTAL = "incremental"


@dataclass
class CycleReport:
    to_download: int = 0
    downloaded: int = 0
    failed: int = 0
    versioned: int = 0
    skipped_native: int = 0
    bytes_downloaded: int = 0
    remote_deleted: int = 0

    def merge_plan(self, plan: Plan) -> None:
        self.to_download += len(plan.to_download)
        self.skipped_native += len(plan.skipped_native)


class SyncEngine:
    """Executa ciclos de sincronização para todos os pares da config."""

    def __init__(
        self,
        config: Config,
        state: State,
        auth: Auth,
        logger: logging.Logger,
        *,
        notifier: Notifier | None = None,
        heartbeat: Heartbeat | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.config = config
        self.state = state
        self.auth = auth
        self.log = logger
        self.service: Any = build_service(auth)
        self._downloader: Downloader | None = None
        self._sleep = sleep
        self.notifier = notifier if notifier is not None else build_notifier(
            config.notifications, logger
        )
        self.heartbeat = heartbeat if heartbeat is not None else Heartbeat(config.heartbeat, logger)
        self.alerts = AlertManager(self.notifier, state, logger)

    @property
    def downloader(self) -> Downloader:
        if self._downloader is None:  # lazy: dry-run não precisa
            self._downloader = Downloader(self.auth)
        return self._downloader

    # --- Planejamento (só leitura) ---------------------------------------

    def plan_pair(self, pair: SyncPair) -> Plan:
        remote = iter_files(build_tree(self.service, pair.drive_folder_id))
        return build_plan(self.state, remote, pair)

    def _plan_pair_with_retry(self, pair: SyncPair) -> Plan:
        """Listar a árvore é a operação mais sujeita a 429/5xx: vale o backoff."""
        return retry_transient(
            lambda: self.plan_pair(pair),
            description=f"listagem da pasta {pair.drive_folder_id}",
            logger=self.log,
            sleep=self._sleep,
        )

    def plan_all(self) -> list[tuple[SyncPair, Plan]]:
        return [(pair, self.plan_pair(pair)) for pair in self.config.sync.pairs]

    # --- Execução --------------------------------------------------------

    def run_once(self) -> CycleReport:
        """Reconciliação completa + processamento da fila para cada par."""
        started_at = datetime.now(UTC).isoformat()
        report = CycleReport()
        try:
            for pair in self.config.sync.pairs:
                disk.ensure_destination(pair.local_path)
                plan = self._plan_pair_with_retry(pair)
                report.merge_plan(plan)
                self._track_remote_changes(pair, plan, report)
                self._process_items(pair, plan.to_download, report)
            self._refresh_page_token()
        except CriticalError as exc:
            # Nível 3: pausa o ciclo, notifica na hora e derruba o heartbeat.
            self.alerts.critical(exc)
            self.heartbeat.ping_fail(str(exc))
            self._record_cycle(started_at, KIND_FULL, report, ok=False, error=str(exc))
            raise

        self.state.mark_full_scan()
        self.state.mark_cycle_ok()
        self.log.info(
            "Ciclo completo: %d baixados, %d versões, %d falhas, %d sumiram do Drive "
            "(%d na fila).",
            report.downloaded, report.versioned, report.failed, report.remote_deleted,
            report.to_download,
            extra={"category": "cycle"},
        )
        self._record_cycle(started_at, KIND_FULL, report, ok=True)
        self._finish_successful_cycle()
        return report

    def _finish_successful_cycle(self) -> None:
        """Pós-ciclo bem-sucedido: Nível 2 pendente e heartbeat (nesta ordem)."""
        self.alerts.check_degraded()
        self.heartbeat.ping()

    def _record_cycle(
        self,
        started_at: str,
        kind: str,
        report: CycleReport,
        *,
        ok: bool,
        error: str | None = None,
    ) -> None:
        self.state.record_cycle(
            started_at=started_at,
            kind=kind,
            downloaded=report.downloaded,
            versioned=report.versioned,
            failed=report.failed,
            remote_deleted=report.remote_deleted,
            bytes_downloaded=report.bytes_downloaded,
            ok=ok,
            error=error,
        )

    # --- Movimentações no Drive (registro, nunca exclusão) ----------------

    def _track_remote_changes(self, pair: SyncPair, plan: Plan, report: CycleReport) -> None:
        """Registra o que sumiu do Drive e o que voltou. **Nunca** apaga local.

        A reconciliação por ``files.list`` só enxerga o que existe; um arquivo que foi
        para a lixeira simplesmente some da árvore. Sem este passo a movimentação não
        apareceria em lugar nenhum no `sync` completo (só no `watch`).
        """
        remote_ids = {file.id for file in plan.all_remote_files()}

        for file_id in remote_ids:
            record = self.state.get_file(file_id)
            if record is not None and record.status == STATUS_REMOTE_DELETED:
                self.state.restore_remote_deleted(file_id)
                self.log.info(
                    "Voltou a aparecer no Drive: %s", record.drive_path,
                    extra={"category": "cycle", "file_id": file_id},
                )

        for row in self.state.files_by_status():
            if row.status == STATUS_REMOTE_DELETED or row.file_id in remote_ids:
                continue
            if not self._belongs_to_pair(row.local_path, pair):
                continue
            self.state.record_remote_deleted(row.file_id)
            report.remote_deleted += 1
            self.log.info(
                "Sumiu do Drive (lixeira/exclusão); cópia local mantida: %s", row.drive_path,
                extra={"category": "cycle", "file_id": row.file_id},
            )

    @staticmethod
    def _belongs_to_pair(local_path: str, pair: SyncPair) -> bool:
        """O arquivo do estado pertence ao destino deste par? (evita mexer em outros)"""
        try:
            return Path(local_path).is_relative_to(pair.local_path)
        except (ValueError, OSError):
            return False

    def watch(self) -> None:
        """Loop contínuo: boot completo, depois incremental a cada intervalo."""
        interval = self.config.sync.interval_minutes * 60
        self.log.info("Reconciliação inicial (boot)…", extra={"category": "cycle"})
        self.run_once()

        resolvers = {
            pair.drive_folder_id: FolderResolver(self.service, pair.drive_folder_id)
            for pair in self.config.sync.pairs
        }
        last_full = time.monotonic()
        self.log.info("Vigiando mudanças a cada %d min.", self.config.sync.interval_minutes,
                      extra={"category": "cycle"})
        while True:
            self._sleep(interval)
            try:
                if time.monotonic() - last_full >= _SECONDS_PER_DAY:
                    self.log.info("Reconciliação diária…", extra={"category": "cycle"})
                    self.run_once()
                    last_full = time.monotonic()
                else:
                    for pair in self.config.sync.pairs:
                        self._incremental_cycle(pair, resolvers[pair.drive_folder_id])
                self.maybe_send_weekly_summary()
            except CriticalError as exc:
                # Nível 3 já foi notificado em run_once; aqui cobre o caminho incremental.
                self.alerts.critical(exc)
                self.heartbeat.ping_fail(str(exc))
            except Exception as exc:  # nunca derruba o loop de vigília
                self.log.error("Erro no ciclo incremental: %s", exc, extra={"category": "cycle"})
                self.heartbeat.ping_fail(str(exc))

    def _incremental_cycle(self, pair: SyncPair, resolver: FolderResolver) -> None:
        started_at = datetime.now(UTC).isoformat()
        report = CycleReport()
        result = retry_transient(
            lambda: poll_changes(self.service, self.state, pair, resolver, self.log),
            description="polling de mudanças",
            logger=self.log,
            sleep=self._sleep,
        )
        report.remote_deleted = result.removed
        if result.items:
            disk.ensure_destination(pair.local_path)
            self._process_items(pair, result.items, report)
            self.log.info(
                "Incremental: %d baixados, %d falhas.", report.downloaded, report.failed,
                extra={"category": "cycle"},
            )
        self.state.set_page_token(result.new_token)
        self.state.mark_cycle_ok()
        self._record_cycle(started_at, KIND_INCREMENTAL, report, ok=True)
        self._finish_successful_cycle()

    # --- Resumo semanal ---------------------------------------------------

    def maybe_send_weekly_summary(self) -> bool:
        """Envia o resumo se a hora agendada já passou e ele ainda não saiu."""
        if not summary.due(self.config.notifications, self.state):
            return False
        return self.send_weekly_summary()

    def send_weekly_summary(self) -> bool:
        """Monta e envia o resumo semanal agora, marcando o envio."""
        report = summary.build_summary(self.state)
        sent = self.alerts.send("resumo-semanal", report.as_message(), tags="bar_chart", force=True)
        self.state.set_last_summary()
        self.log.info("Resumo semanal gerado (enviado=%s).", sent, extra={"category": "notify"})
        return sent

    # --- Interno ---------------------------------------------------------

    def _process_items(self, pair: SyncPair, items: list[PlanItem], report: CycleReport) -> None:
        for item in items:
            file = item.file
            self.state.record_pending(
                file.id, file.drive_path, str(item.local_path),
                file.md5, file.size, file.modified_time,
            )
            try:
                result = retry_transient(
                    partial(self.downloader.download, file, item.local_path, pair.local_path),
                    description=f"download de {file.drive_path}",
                    logger=self.log,
                    sleep=self._sleep,
                )
            except CriticalError:
                raise  # Nível 3: aborta o ciclo (disco/credencial)
            except Exception as exc:
                # Nível 1 esgotado ou Nível 2: só este arquivo falha, o ciclo segue.
                self.state.record_failed(file.id, str(exc))
                report.failed += 1
                self.log.warning(
                    "Falha ao baixar %s: %s", file.drive_path, exc,
                    extra={"category": "download", "file_id": file.id},
                )
                continue

            if result.ok:
                self.state.record_synced(
                    file.id, file.drive_path, str(item.local_path),
                    file.md5, file.size, file.modified_time,
                )
                report.downloaded += 1
                report.bytes_downloaded += result.bytes_written
                if result.versioned:
                    report.versioned += 1
                self.log.info(
                    "Baixado %s%s", file.drive_path,
                    " (versão anterior preservada em _versões/)" if result.versioned else "",
                    extra={"category": "download", "file_id": file.id},
                )
            else:
                self.state.record_failed(file.id, result.error or "erro desconhecido")
                report.failed += 1
                self.log.warning(
                    "Verificação falhou em %s: %s", file.drive_path, result.error,
                    extra={"category": "download", "file_id": file.id},
                )

    def _refresh_page_token(self) -> None:
        resp = self.service.changes().getStartPageToken(supportsAllDrives=True).execute()
        token = resp.get("startPageToken")
        if token:
            self.state.set_page_token(str(token))
