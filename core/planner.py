"""Reconciliação completa: compara o estado remoto (Drive) com o SQLite + disco
e monta a fila de downloads (SPEC.md §3). Função pura (só leitura), para permitir
``--dry-run`` sem gravar nada.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from core.config import SyncPair
from core.drive import DriveFile
from core.state import QUEUEABLE, State

# Motivos de enfileiramento (para log/relatório).
REASON_NEW = "novo"
REASON_MODIFIED = "modificado"
REASON_MISSING_LOCAL = "ausente-local"
REASON_RESUME = "retomar"


@dataclass(frozen=True)
class PlanItem:
    file: DriveFile
    local_path: Path
    reason: str


@dataclass
class Plan:
    to_download: list[PlanItem] = field(default_factory=list)
    synced: list[DriveFile] = field(default_factory=list)
    skipped_native: list[DriveFile] = field(default_factory=list)

    @property
    def bytes_to_download(self) -> int:
        return sum(item.file.size or 0 for item in self.to_download)


def local_path_for(pair: SyncPair, file: DriveFile) -> Path:
    """Caminho local absoluto para um arquivo remoto, sob a raiz do par."""
    return pair.local_path / Path(file.drive_path)


def classify(state: State, file: DriveFile, local_path: Path) -> str | None:
    """Motivo para (re)baixar ``file``, ou ``None`` se já está sincronizado."""
    record = state.get_file(file.id)
    if record is None:
        return REASON_NEW
    if record.md5 != file.md5:
        return REASON_MODIFIED
    if not local_path.exists():
        return REASON_MISSING_LOCAL
    if record.status in QUEUEABLE:
        return REASON_RESUME
    return None


def build_plan(state: State, remote_files: list[DriveFile], pair: SyncPair) -> Plan:
    """Decide, para cada arquivo remoto, se deve baixar. Não grava nada."""
    plan = Plan()
    for file in remote_files:
        if file.is_google_native:
            plan.skipped_native.append(file)
            continue

        local_path = local_path_for(pair, file)
        reason = classify(state, file, local_path)
        if reason is not None:
            plan.to_download.append(PlanItem(file=file, local_path=local_path, reason=reason))
        else:
            plan.synced.append(file)
    return plan
