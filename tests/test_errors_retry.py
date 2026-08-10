"""Classificação de erros por nível e retry com backoff (SPEC.md §4)."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from core.errors import (
    LEVEL_CRITICAL,
    LEVEL_DEGRADED,
    LEVEL_TRANSIENT,
    AuthError,
    ChecksumError,
    DiskError,
    classify,
    http_status_of,
    is_transient,
)
from core.retry import retry_transient

LOG = logging.getLogger("test")


class _Resp:
    """Imita ``googleapiclient.errors.HttpError.resp``."""

    def __init__(self, status: int) -> None:
        self.status = status


class FakeHttpError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.resp = _Resp(status)


class FakeRequestsError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.response = type("R", (), {"status_code": status})()


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (429, LEVEL_TRANSIENT),
        (500, LEVEL_TRANSIENT),
        (503, LEVEL_TRANSIENT),
        (408, LEVEL_TRANSIENT),
        (401, LEVEL_CRITICAL),   # credencial revogada
        (403, LEVEL_CRITICAL),   # perdeu acesso à pasta
        (404, LEVEL_DEGRADED),   # some este arquivo, o ciclo segue
    ],
)
def test_classify_by_http_status(status: int, expected: int) -> None:
    assert classify(FakeHttpError(status)) == expected
    assert classify(FakeRequestsError(status)) == expected


def test_classify_app_errors_win_over_status() -> None:
    assert classify(DiskError("disco sumiu")) == LEVEL_CRITICAL
    assert classify(AuthError("credencial")) == LEVEL_CRITICAL
    assert classify(ChecksumError("md5 diverge")) == LEVEL_DEGRADED


def test_classify_unknown_defaults_to_transient() -> None:
    assert is_transient(TimeoutError("timeout"))
    assert is_transient(ConnectionError("reset"))
    assert is_transient(RuntimeError("???"))


def test_http_status_of_returns_none_without_status() -> None:
    assert http_status_of(ValueError("nada")) is None


def test_retry_returns_on_first_success() -> None:
    calls: list[int] = []

    def op() -> str:
        calls.append(1)
        return "ok"

    assert retry_transient(op, description="x", logger=LOG, sleep=lambda _s: None) == "ok"
    assert len(calls) == 1


def test_retry_recovers_after_transient_failures() -> None:
    slept: list[float] = []
    attempts: list[int] = []

    def op() -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise FakeHttpError(503)
        return "ok"

    result = retry_transient(
        op, description="x", logger=LOG, sleep=slept.append, backoff=(60, 300, 1800)
    )
    assert result == "ok"
    assert len(attempts) == 3
    assert slept == [60, 300]  # backoff do SPEC: 1 min, depois 5 min


def test_retry_gives_up_after_max_attempts() -> None:
    attempts: list[int] = []

    def op() -> str:
        attempts.append(1)
        raise FakeHttpError(500)

    with pytest.raises(FakeHttpError):
        retry_transient(op, description="x", logger=LOG, sleep=lambda _s: None)
    assert len(attempts) == 3


def test_retry_does_not_retry_critical() -> None:
    attempts: list[int] = []

    def op() -> Any:
        attempts.append(1)
        raise DiskError("disco ausente")

    with pytest.raises(DiskError):
        retry_transient(op, description="x", logger=LOG, sleep=lambda _s: None)
    assert len(attempts) == 1  # Nível 3 sobe na hora, sem esperar backoff


def test_retry_does_not_retry_degraded() -> None:
    attempts: list[int] = []

    def op() -> Any:
        attempts.append(1)
        raise ChecksumError("md5 diverge")

    with pytest.raises(ChecksumError):
        retry_transient(op, description="x", logger=LOG, sleep=lambda _s: None)
    assert len(attempts) == 1
