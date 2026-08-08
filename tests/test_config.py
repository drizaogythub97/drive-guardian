"""Testes de carga e validação da config (SPEC.md §1)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from core.config import load_config, parse_config
from core.errors import ConfigError

VALID: dict = {
    "auth": {"strategy": "service_account", "service_account_key": "./secrets/sa-key.json"},
    "sync": {
        "pairs": [{"drive_folder_id": "ABC123", "local_path": "E:/Backup"}],
        "interval_minutes": 30,
    },
    "notifications": {"ntfy": {"enabled": False}},
    "heartbeat": {"enabled": False},
}


def test_parse_valid_config() -> None:
    cfg = parse_config(VALID)
    assert cfg.auth.strategy == "service_account"
    assert cfg.sync.pairs[0].drive_folder_id == "ABC123"
    assert cfg.sync.pairs[0].local_path == Path("E:/Backup")
    assert cfg.sync.interval_minutes == 30
    assert cfg.logging.level == "INFO"


def test_empty_folder_id_is_critical() -> None:
    raw = {**VALID, "sync": {"pairs": [{"drive_folder_id": "  ", "local_path": "E:/Backup"}]}}
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_interval_below_minimum_is_critical() -> None:
    raw = {
        **VALID,
        "sync": {"pairs": VALID["sync"]["pairs"], "interval_minutes": 3},
    }
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_unknown_strategy_is_critical() -> None:
    raw = {**VALID, "auth": {"strategy": "banana"}}
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_no_pairs_is_critical() -> None:
    raw = {**VALID, "sync": {"pairs": [], "interval_minutes": 30}}
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_ntfy_enabled_without_topic_is_critical() -> None:
    raw = {**VALID, "notifications": {"ntfy": {"enabled": True, "topic": ""}}}
    with pytest.raises(ConfigError):
        parse_config(raw)


def test_missing_file_is_critical(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        load_config(tmp_path / "inexistente.yaml")


def test_load_from_disk_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(VALID), encoding="utf-8")
    cfg = load_config(path)
    assert cfg.sync.pairs[0].drive_folder_id == "ABC123"


def test_example_yaml_is_parseable() -> None:
    """O config.example.yaml deve validar estruturalmente (docs sempre corretos)."""
    example = Path(__file__).resolve().parent.parent / "config.example.yaml"
    raw = yaml.safe_load(example.read_text(encoding="utf-8"))
    cfg = parse_config(raw)
    assert cfg.sync.interval_minutes >= 5
