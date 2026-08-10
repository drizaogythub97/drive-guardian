"""Gravação do config pela UI: ida e volta fiel, validação antes de escrever
e escrita atômica (o usuário nunca deve ficar com um YAML pela metade)."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.config import (
    AuthConfig,
    Config,
    HeartbeatConfig,
    LoggingConfig,
    NotificationsConfig,
    NtfyConfig,
    SyncConfig,
    SyncPair,
    load_config,
    save_config,
)
from core.errors import ConfigError


def _config() -> Config:
    return Config(
        auth=AuthConfig(strategy="service_account", service_account_key=Path("secrets/sa.json")),
        sync=SyncConfig(
            pairs=[SyncPair(drive_folder_id="ABC123", local_path=Path("D:/DriveGuardian"))],
            interval_minutes=45,
            bandwidth_limit_mbps=10,
            export_google_docs=False,
            export_formats={"document": "docx"},
        ),
        notifications=NotificationsConfig(
            ntfy=NtfyConfig(enabled=True, server="https://ntfy.sh", topic="topico-secreto"),
            weekly_summary=True,
            summary_day="sunday",
            summary_hour=20,
        ),
        heartbeat=HeartbeatConfig(enabled=True, url="https://hc-ping.com/uuid"),
        logging=LoggingConfig(level="INFO", max_file_mb=10, backups=5),
    )


def test_round_trip_preserves_everything(tmp_path: Path) -> None:
    original = _config()
    target = tmp_path / "config.yaml"
    save_config(original, target)
    loaded = load_config(target)

    assert loaded.auth.strategy == original.auth.strategy
    assert loaded.auth.service_account_key == original.auth.service_account_key
    assert loaded.sync.pairs[0].drive_folder_id == "ABC123"
    assert loaded.sync.pairs[0].local_path == Path("D:/DriveGuardian")
    assert loaded.sync.interval_minutes == 45
    assert loaded.sync.bandwidth_limit_mbps == 10
    assert loaded.sync.export_formats == {"document": "docx"}
    assert loaded.notifications.ntfy.topic == "topico-secreto"
    assert loaded.notifications.summary_hour == 20
    assert loaded.heartbeat.url == "https://hc-ping.com/uuid"
    assert loaded.logging.backups == 5


def test_written_file_has_a_header_comment(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    save_config(_config(), target)
    assert target.read_text(encoding="utf-8").startswith("# Drive Guardian")


def test_invalid_config_is_rejected_before_touching_the_file(tmp_path: Path) -> None:
    """Intervalo abaixo do mínimo: o arquivo bom não pode ser destruído."""
    target = tmp_path / "config.yaml"
    save_config(_config(), target)
    before = target.read_text(encoding="utf-8")

    broken = Config(
        auth=_config().auth,
        sync=SyncConfig(
            pairs=_config().sync.pairs,
            interval_minutes=1,  # < MIN_INTERVAL_MINUTES
            bandwidth_limit_mbps=0,
            export_google_docs=False,
            export_formats={},
        ),
        notifications=_config().notifications,
        heartbeat=_config().heartbeat,
        logging=_config().logging,
    )
    with pytest.raises(ConfigError):
        save_config(broken, target)

    assert target.read_text(encoding="utf-8") == before  # intacto


def test_creates_parent_directory(tmp_path: Path) -> None:
    target = tmp_path / "novo" / "config.yaml"
    save_config(_config(), target)
    assert target.is_file()


def test_no_temp_file_is_left_behind(tmp_path: Path) -> None:
    target = tmp_path / "config.yaml"
    save_config(_config(), target)
    assert list(tmp_path.glob("*.tmp")) == []
