"""Drive Guardian — interface de linha de comando (núcleo headless).

Comandos:
  list            Imprime a árvore da pasta monitorada no Drive (Fase 0).
  sync            Executa um ciclo de sincronização (Fase 1).
  watch           Loop contínuo no intervalo da config (Fase 1).
  status          Panorama do último ciclo e dos arquivos por status (Fase 2).
  events          Log de movimentações persistido no SQLite (Fase 2).
  summary         Monta (e opcionalmente envia) o resumo semanal (Fase 2).
  test-alert      Envia uma notificação de teste pelo ntfy (Fase 2).

Opções globais:
  -c/--config     Caminho do config.yaml (padrão: ./config.yaml).
"""

from __future__ import annotations

import argparse
import sys

from core import summary as summary_mod
from core.alerts import AlertManager
from core.auth import build_auth
from core.config import Config, load_config
from core.drive import DriveNode, build_service, build_tree, iter_files
from core.errors import CriticalError
from core.heartbeat import Heartbeat
from core.logger import null_logger, setup_logging
from core.notifier import build_notifier
from core.paths import state_db_path
from core.planner import Plan
from core.state import State
from core.sync import SyncEngine
from core.util import human_size

DEFAULT_CONFIG = "config.yaml"


def _render_tree(node: DriveNode) -> list[str]:
    """Renderiza a árvore com conectores ├──/└── (raiz no topo)."""
    lines = [f"{node.file.name}/"]

    def walk(children: list[DriveNode], prefix: str) -> None:
        for i, child in enumerate(children):
            last = i == len(children) - 1
            connector = "└── " if last else "├── "
            if child.file.is_folder:
                lines.append(f"{prefix}{connector}{child.file.name}/")
                walk(child.children, prefix + ("    " if last else "│   "))
            else:
                size = human_size(child.file.size)
                tag = " [Google Docs]" if child.file.is_google_native else ""
                lines.append(f"{prefix}{connector}{child.file.name}  ({size}){tag}")

    walk(node.children, "")
    return lines


def cmd_list(config: Config) -> int:
    """Autentica via SA e imprime a árvore da(s) pasta(s) monitorada(s)."""
    auth = build_auth(config.auth)
    print(f"Conta autenticada: {auth.account_label()}\n")
    service = build_service(auth)

    total_files = 0
    total_bytes = 0
    for pair in config.sync.pairs:
        tree = build_tree(service, pair.drive_folder_id)
        for line in _render_tree(tree):
            print(line)
        files = iter_files(tree)
        pair_bytes = sum(f.size or 0 for f in files)
        total_files += len(files)
        total_bytes += pair_bytes
        print(
            f"\n  {len(files)} arquivo(s), {human_size(pair_bytes)} "
            f"— destino: {pair.local_path}\n"
        )

    print(f"Total: {total_files} arquivo(s), {human_size(total_bytes)}.")
    return 0


def _open_state(*, read_only_ok: bool) -> State:
    """Abre o estado. Em modo leitura (dry-run), usa banco em memória se o real
    ainda não existe — assim ``--dry-run`` não cria nada em disco."""
    db = state_db_path()
    if read_only_ok and not db.exists():
        return State(":memory:")
    return State(db)


def _print_plan(pair_local: str, plan: Plan) -> None:
    by_reason: dict[str, int] = {}
    for item in plan.to_download:
        by_reason[item.reason] = by_reason.get(item.reason, 0) + 1
    detail = ", ".join(f"{n} {r}" for r, n in sorted(by_reason.items())) or "—"
    print(f"Destino: {pair_local}")
    print(f"  A baixar: {len(plan.to_download)} arquivo(s) ({detail})")
    print(f"  Volume:   {human_size(plan.bytes_to_download)}")
    print(f"  Já sincronizados: {len(plan.synced)}")
    if plan.skipped_native:
        print(f"  Ignorados (Google Docs nativos): {len(plan.skipped_native)}")
    for item in plan.to_download[:20]:
        print(f"    • [{item.reason}] {item.file.drive_path}  ({human_size(item.file.size)})")
    if len(plan.to_download) > 20:
        print(f"    … e mais {len(plan.to_download) - 20} arquivo(s).")


def cmd_sync(config: Config, *, dry_run: bool) -> int:
    """Executa um ciclo de sincronização (ou simula, com ``--dry-run``)."""
    auth = build_auth(config.auth)

    if dry_run:
        print("=== DRY-RUN — nada será baixado ou gravado ===\n")
        with _open_state(read_only_ok=True) as state:
            engine = SyncEngine(config, state, auth, null_logger())
            for pair, plan in engine.plan_all():
                _print_plan(str(pair.local_path), plan)
                print()
        return 0

    with _open_state(read_only_ok=False) as state:
        logger = setup_logging(config.logging, state)
        engine = SyncEngine(config, state, auth, logger)
        report = engine.run_once()
    print(
        f"Concluído: {report.downloaded} baixado(s), {report.versioned} versão(ões), "
        f"{report.failed} falha(s), {human_size(report.bytes_downloaded)} transferidos."
    )
    return 1 if report.failed else 0


def cmd_watch(config: Config) -> int:
    """Loop contínuo: reconciliação no boot e polling incremental."""
    auth = build_auth(config.auth)
    with _open_state(read_only_ok=False) as state:
        logger = setup_logging(config.logging, state)
        engine = SyncEngine(config, state, auth, logger)
        print(f"Vigiando a cada {config.sync.interval_minutes} min. Ctrl+C para sair.")
        try:
            engine.watch()
        except KeyboardInterrupt:
            print("\nEncerrado pelo usuário.")
    return 0


def cmd_status(config: Config) -> int:
    """Panorama rápido: último ciclo, arquivos por status, erros pendentes."""
    with _open_state(read_only_ok=True) as state:
        counts = state.count_by_status()
        total = sum(counts.values())
        print(f"Arquivos conhecidos: {total}")
        for status, n in sorted(counts.items()):
            print(f"  {status:<20} {n}")

        last_ok = state.get_last_cycle_ok()
        print(f"\nÚltimo ciclo bem-sucedido: {last_ok or '—'}")
        print(f"Último resumo semanal:     {state.get_last_summary() or '—'}")

        cycles = state.recent_cycles(limit=5)
        if cycles:
            print("\nÚltimos ciclos:")
            for c in cycles:
                flag = "ok" if c.ok else "FALHOU"
                print(
                    f"  {c.finished_at[:19]}  {c.kind:<12} {flag:<7} "
                    f"{c.downloaded} baixado(s), {c.versioned} versão(ões), "
                    f"{c.failed} falha(s), {c.remote_deleted} sumiram, "
                    f"{human_size(c.bytes_downloaded)}"
                )

        ntfy_on = "ligadas" if config.notifications.ntfy.enabled else "desligadas"
        print(f"\nNotificações ntfy: {ntfy_on}")
        print(f"Heartbeat:         {'ligado' if config.heartbeat.enabled else 'desligado'}")
    return 0


def cmd_events(config: Config, *, limit: int, level: str | None, category: str | None) -> int:
    """Imprime o log de movimentações gravado no SQLite (mesma fonte da futura UI)."""
    levels = (level,) if level else ()
    with _open_state(read_only_ok=True) as state:
        rows = state.recent_events(limit=limit, levels=levels, category=category)
    if not rows:
        print("Nenhum evento registrado ainda.")
        return 0
    for row in reversed(rows):  # cronológico: mais antigo primeiro
        print(f"{row['ts'][:19]}  {row['level']:<8} {row['category']:<9} {row['message']}")
    return 0


def cmd_summary(config: Config, *, send: bool) -> int:
    """Mostra o resumo semanal; com ``--send`` também dispara a notificação."""
    with _open_state(read_only_ok=True) as state:
        report = summary_mod.build_summary(state)
        print(report.as_message())
        if not send:
            print("\n(use --send para enviar pelo ntfy)")
            return 0

        logger = setup_logging(config.logging, state)
        alerts = AlertManager(build_notifier(config.notifications, logger), state, logger)
        sent = alerts.send("resumo-semanal", report.as_message(), tags="bar_chart", force=True)
        state.set_last_summary()
    print("\nResumo enviado." if sent else "\nResumo NÃO enviado (ntfy desligado ou falhou).")
    return 0 if sent else 1


def cmd_test_alert(config: Config) -> int:
    """Envia uma notificação de teste — valida tópico ntfy e heartbeat de ponta a ponta."""
    with _open_state(read_only_ok=False) as state:
        logger = setup_logging(config.logging, state)
        notifier = build_notifier(config.notifications, logger)
        if not notifier.enabled:
            print("ntfy desligado na config (notifications.ntfy.enabled: false).")
            return 1

        alerts = AlertManager(notifier, state, logger)
        sent = alerts.send(
            "teste",
            "Teste do Drive Guardian: se você recebeu isto no celular, os alertas "
            "estão funcionando.",
            tags="white_check_mark",
            force=True,
        )
        print("Notificação enviada." if sent else "Falha ao enviar (veja o log).")

        heartbeat = Heartbeat(config.heartbeat, logger)
        if heartbeat.enabled:
            print("Heartbeat: ping enviado." if heartbeat.ping() else "Heartbeat: falhou.")
        else:
            print("Heartbeat desligado na config.")
    return 0 if sent else 1


def _notify_critical(config_path: str, exc: CriticalError) -> None:
    """Alerta de Nível 3 no celular mesmo quando o erro impede montar o engine.

    É o caminho que cobre credencial revogada em ``cli.py sync``: a exceção estoura
    no ``build_auth``, antes de existir um ``SyncEngine`` para notificar. Falhar aqui
    nunca pode piorar a situação, então tudo é engolido.
    """
    try:
        config = load_config(config_path)
        with _open_state(read_only_ok=True) as state:
            logger = setup_logging(config.logging, state)
            AlertManager(build_notifier(config.notifications, logger), state, logger).critical(exc)
            Heartbeat(config.heartbeat, logger).ping_fail(str(exc))
    except Exception:
        pass  # best-effort: um alerta que falha não pode mascarar o erro original


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="drive-guardian", description="Backup local do Google Drive."
    )
    parser.add_argument("-c", "--config", default=DEFAULT_CONFIG, help="Caminho do config.yaml")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list", help="Imprime a árvore da pasta do Drive (Fase 0)")
    sync = sub.add_parser("sync", help="Executa um ciclo de sincronização (Fase 1)")
    sync.add_argument("--dry-run", action="store_true", help="Simula sem gravar nada")
    sub.add_parser("watch", help="Loop contínuo no intervalo da config (Fase 1)")

    sub.add_parser("status", help="Panorama do último ciclo e dos status (Fase 2)")

    events = sub.add_parser("events", help="Log de movimentações do SQLite (Fase 2)")
    events.add_argument("-n", "--limit", type=int, default=30, help="Quantos eventos (padrão 30)")
    events.add_argument("--level", help="Filtra por nível (INFO, WARNING, ERROR…)")
    events.add_argument("--category", help="Filtra por categoria (download, cycle, notify…)")

    summary_cmd = sub.add_parser("summary", help="Resumo semanal (Fase 2)")
    summary_cmd.add_argument("--send", action="store_true", help="Também envia pelo ntfy")

    sub.add_parser("test-alert", help="Envia notificação de teste pelo ntfy (Fase 2)")
    return parser


def _force_utf8_stdout() -> None:
    """Evita UnicodeEncodeError no console cp1252 do Windows (árvore usa ├└│—)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="replace")


def main(argv: list[str] | None = None) -> int:
    _force_utf8_stdout()
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)

        if args.command == "list":
            return cmd_list(config)
        if args.command == "sync":
            return cmd_sync(config, dry_run=args.dry_run)
        if args.command == "watch":
            return cmd_watch(config)
        if args.command == "status":
            return cmd_status(config)
        if args.command == "events":
            return cmd_events(
                config, limit=args.limit, level=args.level, category=args.category
            )
        if args.command == "summary":
            return cmd_summary(config, send=args.send)
        if args.command == "test-alert":
            return cmd_test_alert(config)
    except CriticalError as exc:
        print(f"ERRO (Nível 3): {exc}", file=sys.stderr)
        _notify_critical(args.config, exc)
        return 1

    parser.error(f"comando desconhecido: {args.command}")
    return 2  # inalcançável; satisfaz o type checker


if __name__ == "__main__":
    raise SystemExit(main())
