"""Drive Guardian — interface de linha de comando (núcleo headless).

Comandos:
  list            Imprime a árvore da pasta monitorada no Drive (Fase 0).
  sync            Executa um ciclo de sincronização (Fase 1).
  watch           Loop contínuo no intervalo da config (Fase 1).

Opções globais:
  -c/--config     Caminho do config.yaml (padrão: ./config.yaml).
"""

from __future__ import annotations

import argparse
import sys

from core.auth import build_auth
from core.config import Config, load_config
from core.drive import DriveNode, build_service, build_tree, iter_files
from core.errors import CriticalError
from core.logger import setup_logging
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


def cmd_not_implemented(name: str, phase: str) -> int:
    print(f"'{name}' ainda não implementado ({phase}).", file=sys.stderr)
    return 2


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
        setup_logging(config.logging)

        if args.command == "list":
            return cmd_list(config)
        if args.command == "sync":
            return cmd_not_implemented("sync", "Fase 1")
        if args.command == "watch":
            return cmd_not_implemented("watch", "Fase 1")
    except CriticalError as exc:
        print(f"ERRO (Nível 3): {exc}", file=sys.stderr)
        return 1

    parser.error(f"comando desconhecido: {args.command}")
    return 2  # inalcançável; satisfaz o type checker


if __name__ == "__main__":
    raise SystemExit(main())
