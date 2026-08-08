"""Carrega e valida o ``config.yaml`` (SPEC.md §1).

Config inválida na inicialização é erro Nível 3 (ver ``core.errors``): ID de
pasta vazio, intervalo < 5 min, estratégia desconhecida, etc.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from core.errors import ConfigError

MIN_INTERVAL_MINUTES = 5
VALID_STRATEGIES = ("service_account", "user_oauth")


@dataclass(frozen=True)
class AuthConfig:
    strategy: str
    service_account_key: Path | None


@dataclass(frozen=True)
class SyncPair:
    drive_folder_id: str
    local_path: Path


@dataclass(frozen=True)
class SyncConfig:
    pairs: list[SyncPair]
    interval_minutes: int
    bandwidth_limit_mbps: int
    export_google_docs: bool
    export_formats: dict[str, str]


@dataclass(frozen=True)
class NtfyConfig:
    enabled: bool
    server: str
    topic: str


@dataclass(frozen=True)
class NotificationsConfig:
    ntfy: NtfyConfig
    weekly_summary: bool
    summary_day: str
    summary_hour: int


@dataclass(frozen=True)
class HeartbeatConfig:
    enabled: bool
    url: str


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    max_file_mb: int = 10
    backups: int = 5


@dataclass(frozen=True)
class Config:
    auth: AuthConfig
    sync: SyncConfig
    notifications: NotificationsConfig
    heartbeat: HeartbeatConfig
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _require(mapping: dict[str, Any], key: str, context: str) -> Any:
    if key not in mapping:
        raise ConfigError(f"config: chave obrigatória ausente: '{context}{key}'")
    return mapping[key]


def _as_mapping(value: Any, context: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        got = type(value).__name__
        raise ConfigError(f"config: esperado um mapa em '{context}', recebido {got}")
    return value


def _parse_auth(raw: dict[str, Any]) -> AuthConfig:
    auth = _as_mapping(_require(raw, "auth", ""), "auth")
    strategy = str(_require(auth, "strategy", "auth."))
    if strategy not in VALID_STRATEGIES:
        raise ConfigError(
            f"config: auth.strategy inválida: '{strategy}' (use {' ou '.join(VALID_STRATEGIES)})"
        )
    key_raw = auth.get("service_account_key")
    key = Path(str(key_raw)) if key_raw else None
    if strategy == "service_account" and key is None:
        raise ConfigError("config: auth.service_account_key é obrigatório para service_account")
    return AuthConfig(strategy=strategy, service_account_key=key)


def _parse_sync(raw: dict[str, Any]) -> SyncConfig:
    sync = _as_mapping(_require(raw, "sync", ""), "sync")
    pairs_raw = _require(sync, "pairs", "sync.")
    if not isinstance(pairs_raw, list) or not pairs_raw:
        raise ConfigError("config: sync.pairs deve conter ao menos um par pasta->destino")

    pairs: list[SyncPair] = []
    for i, entry in enumerate(pairs_raw):
        ctx = f"sync.pairs[{i}]."
        pair = _as_mapping(entry, f"sync.pairs[{i}]")
        folder_id = str(_require(pair, "drive_folder_id", ctx)).strip()
        local_path = str(_require(pair, "local_path", ctx)).strip()
        if not folder_id:
            raise ConfigError(f"config: {ctx}drive_folder_id está vazio")
        if not local_path:
            raise ConfigError(f"config: {ctx}local_path está vazio")
        pairs.append(SyncPair(drive_folder_id=folder_id, local_path=Path(local_path)))

    interval = int(sync.get("interval_minutes", 30))
    if interval < MIN_INTERVAL_MINUTES:
        raise ConfigError(
            f"config: sync.interval_minutes < {MIN_INTERVAL_MINUTES} (recebido {interval})"
        )

    formats_map = _as_mapping(sync.get("export_formats") or {}, "sync.export_formats")
    export_formats = {str(k): str(v) for k, v in formats_map.items()}

    return SyncConfig(
        pairs=pairs,
        interval_minutes=interval,
        bandwidth_limit_mbps=int(sync.get("bandwidth_limit_mbps", 0)),
        export_google_docs=bool(sync.get("export_google_docs", False)),
        export_formats=export_formats,
    )


def _parse_notifications(raw: dict[str, Any]) -> NotificationsConfig:
    notif = _as_mapping(raw.get("notifications") or {}, "notifications")
    ntfy_raw = _as_mapping(notif.get("ntfy") or {}, "notifications.ntfy")
    ntfy = NtfyConfig(
        enabled=bool(ntfy_raw.get("enabled", False)),
        server=str(ntfy_raw.get("server", "https://ntfy.sh")),
        topic=str(ntfy_raw.get("topic", "")),
    )
    if ntfy.enabled and not ntfy.topic:
        raise ConfigError(
            "config: notifications.ntfy.topic é obrigatório quando ntfy está habilitado"
        )
    return NotificationsConfig(
        ntfy=ntfy,
        weekly_summary=bool(notif.get("weekly_summary", False)),
        summary_day=str(notif.get("summary_day", "sunday")),
        summary_hour=int(notif.get("summary_hour", 20)),
    )


def _parse_heartbeat(raw: dict[str, Any]) -> HeartbeatConfig:
    hb = _as_mapping(raw.get("heartbeat") or {}, "heartbeat")
    heartbeat = HeartbeatConfig(enabled=bool(hb.get("enabled", False)), url=str(hb.get("url", "")))
    if heartbeat.enabled and not heartbeat.url:
        raise ConfigError("config: heartbeat.url é obrigatório quando heartbeat está habilitado")
    return heartbeat


def _parse_logging(raw: dict[str, Any]) -> LoggingConfig:
    log = _as_mapping(raw.get("logging") or {}, "logging")
    return LoggingConfig(
        level=str(log.get("level", "INFO")).upper(),
        max_file_mb=int(log.get("max_file_mb", 10)),
        backups=int(log.get("backups", 5)),
    )


def parse_config(raw: dict[str, Any]) -> Config:
    """Valida um dicionário já carregado e monta o :class:`Config` tipado."""
    return Config(
        auth=_parse_auth(raw),
        sync=_parse_sync(raw),
        notifications=_parse_notifications(raw),
        heartbeat=_parse_heartbeat(raw),
        logging=_parse_logging(raw),
    )


def load_config(path: str | Path) -> Config:
    """Lê e valida o arquivo de config. Levanta :class:`ConfigError` (Nível 3)."""
    config_path = Path(path)
    if not config_path.is_file():
        raise ConfigError(
            f"config: arquivo não encontrado: {config_path}. "
            "Copie config.example.yaml para config.yaml e ajuste."
        )
    try:
        loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"config: YAML inválido em {config_path}: {exc}") from exc
    if loaded is None:
        raise ConfigError(f"config: arquivo vazio: {config_path}")
    return parse_config(_as_mapping(loaded, "<raiz>"))
