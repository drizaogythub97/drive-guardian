"""Thread de sincronização por trás da UI.

A janela nunca pode congelar durante um download de 12 GB, então todo o trabalho
do ``SyncEngine`` roda aqui e volta para a interface só por sinais.

Detalhe que importa: o ``State`` (SQLite) é criado **dentro** da thread. Conexões
sqlite são presas à thread que as abriu; compartilhar a da janela daria erro
intermitente e difícil de rastrear. A UI lê o banco pela própria conexão — o modo
WAL permite ler enquanto a thread escreve.
"""

from __future__ import annotations

import threading
from typing import Any

from PySide6.QtCore import QThread, Signal

from core.alerts import is_critical
from core.auth import build_auth
from core.config import Config
from core.logger import setup_logging
from core.paths import state_db_path
from core.state import State
from core.sync import SyncEngine


class SyncWorker(QThread):
    """Roda ciclos de sincronização em segundo plano, sob controle da UI."""

    cycle_started = Signal()
    cycle_finished = Signal(object)  # core.sync.CycleReport
    cycle_failed = Signal(str, bool)  # (mensagem, é crítico?)
    state_changed = Signal()  # algo mudou no banco: a aba Atividade se atualiza

    def __init__(self, config: Config, parent: Any = None) -> None:
        super().__init__(parent)
        self._config = config
        self._wake = threading.Event()
        self._stopping = False
        self._paused = False
        self._check_requested = False
        self._rebuild = False
        self._lock = threading.Lock()

    # --- Controle vindo da UI (thread da interface) -----------------------

    def request_check(self) -> None:
        """"Verificar agora": acorda a thread fora do intervalo."""
        with self._lock:
            self._check_requested = True
        self._wake.set()

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self._paused = paused
        self._wake.set()

    def is_paused(self) -> bool:
        with self._lock:
            return self._paused

    def apply_config(self, config: Config) -> None:
        """Config salva na UI: reconstrói o engine no próximo ciclo."""
        with self._lock:
            self._config = config
            self._rebuild = True
        self._wake.set()

    def stop(self) -> None:
        self._stopping = True
        self._wake.set()

    # --- Execução (thread de trabalho) ------------------------------------

    def run(self) -> None:
        state = State(state_db_path())
        logger = setup_logging(self._config.logging, state)
        engine: SyncEngine | None = None

        try:
            while not self._stopping:
                with self._lock:
                    config = self._config
                    rebuild = self._rebuild
                    self._rebuild = False
                    paused = self._paused
                    forced = self._check_requested
                    self._check_requested = False

                if engine is None or rebuild:
                    engine = self._build_engine(config, state, logger)

                if engine is not None and (forced or not paused):
                    self._run_cycle(engine)

                self._wake.wait(timeout=self._interval_seconds(config))
                self._wake.clear()
        finally:
            state.close()

    def _interval_seconds(self, config: Config) -> float:
        return float(config.sync.interval_minutes * 60)

    def _build_engine(self, config: Config, state: State, logger: Any) -> SyncEngine | None:
        """Monta o engine; credencial inválida é Nível 3 e vira aviso na UI."""
        try:
            return SyncEngine(config, state, build_auth(config.auth), logger)
        except Exception as exc:
            self.cycle_failed.emit(str(exc), is_critical(exc))
            self.state_changed.emit()
            return None

    def _run_cycle(self, engine: SyncEngine) -> None:
        self.cycle_started.emit()
        try:
            report = engine.run_once()
        except Exception as exc:
            # O engine já notificou/alertou o que era Nível 3; aqui é só a UI.
            self.cycle_failed.emit(str(exc), is_critical(exc))
        else:
            self.cycle_finished.emit(report)
        finally:
            self.state_changed.emit()
