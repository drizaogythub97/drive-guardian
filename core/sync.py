"""Orquestrador de sincronização (SPEC.md §3): amarra reconciliação, fila,
download atômico e polling incremental. Sem dependência de UI (CLAUDE.md §6).

- ``plan_all()`` — só leitura, base do ``--dry-run`` (não grava nada).
- ``run_once()`` — um ciclo completo (reconciliação + processa fila).
- ``watch()`` — reconciliação no boot e depois ``changes.list`` a cada intervalo,
  com reconciliação completa 1x/dia.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from core import disk
from core.auth import Auth
from core.config import Config, SyncPair
from core.downloader import Downloader
from core.drive import build_service, build_tree, iter_files
from core.errors import DiskError
from core.planner import Plan, PlanItem, build_plan
from core.state import State
from core.watcher import FolderResolver, poll_changes

_SECONDS_PER_DAY = 86_400


@dataclass
class CycleReport:
    to_download: int = 0
    downloaded: int = 0
    failed: int = 0
    versioned: int = 0
    skipped_native: int = 0
    bytes_downloaded: int = 0

    def merge_plan(self, plan: Plan) -> None:
        self.to_download += len(plan.to_download)
        self.skipped_native += len(plan.skipped_native)


class SyncEngine:
    """Executa ciclos de sincronização para todos os pares da config."""

    def __init__(self, config: Config, state: State, auth: Auth, logger: logging.Logger) -> None:
        self.config = config
        self.state = state
        self.auth = auth
        self.log = logger
        self.service: Any = build_service(auth)
        self._downloader: Downloader | None = None

    @property
    def downloader(self) -> Downloader:
        if self._downloader is None:  # lazy: dry-run não precisa
            self._downloader = Downloader(self.auth)
        return self._downloader

    # --- Planejamento (só leitura) ---------------------------------------

    def plan_pair(self, pair: SyncPair) -> Plan:
        remote = iter_files(build_tree(self.service, pair.drive_folder_id))
        return build_plan(self.state, remote, pair)

    def plan_all(self) -> list[tuple[SyncPair, Plan]]:
        return [(pair, self.plan_pair(pair)) for pair in self.config.sync.pairs]

    # --- Execução --------------------------------------------------------

    def run_once(self) -> CycleReport:
        """Reconciliação completa + processamento da fila para cada par."""
        report = CycleReport()
        for pair in self.config.sync.pairs:
            disk.ensure_destination(pair.local_path)
            plan = self.plan_pair(pair)
            report.merge_plan(plan)
            self._process_items(pair, plan.to_download, report)
        self._refresh_page_token()
        self.state.mark_full_scan()
        self.state.mark_cycle_ok()
        self.log.info(
            "Ciclo completo: %d baixados, %d versões, %d falhas (%d na fila).",
            report.downloaded, report.versioned, report.failed, report.to_download,
            extra={"category": "cycle"},
        )
        return report

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
            time.sleep(interval)
            try:
                if time.monotonic() - last_full >= _SECONDS_PER_DAY:
                    self.log.info("Reconciliação diária…", extra={"category": "cycle"})
                    self.run_once()
                    last_full = time.monotonic()
                else:
                    for pair in self.config.sync.pairs:
                        self._incremental_cycle(pair, resolvers[pair.drive_folder_id])
            except DiskError as exc:
                self.log.error("Disco (Nível 3): %s", exc, extra={"category": "disk"})
            except Exception as exc:  # nunca derruba o loop de vigília
                self.log.error("Erro no ciclo incremental: %s", exc, extra={"category": "cycle"})

    def _incremental_cycle(self, pair: SyncPair, resolver: FolderResolver) -> None:
        result = poll_changes(self.service, self.state, pair, resolver, self.log)
        if result.items:
            disk.ensure_destination(pair.local_path)
            report = CycleReport()
            self._process_items(pair, result.items, report)
            self.log.info(
                "Incremental: %d baixados, %d falhas.", report.downloaded, report.failed,
                extra={"category": "cycle"},
            )
        self.state.set_page_token(result.new_token)
        self.state.mark_cycle_ok()

    # --- Interno ---------------------------------------------------------

    def _process_items(self, pair: SyncPair, items: list[PlanItem], report: CycleReport) -> None:
        for item in items:
            file = item.file
            self.state.record_pending(
                file.id, file.drive_path, str(item.local_path),
                file.md5, file.size, file.modified_time,
            )
            try:
                result = self.downloader.download(file, item.local_path, pair.local_path)
            except DiskError:
                raise  # Nível 3: aborta o ciclo
            except Exception as exc:  # transitório (rede/5xx): falha só este arquivo
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
