from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dabjob.config import Settings, enforce_bind_policy, is_loopback
from dabjob.main import create_app


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1", "127.0.0.53"])
def test_loopback_hosts_are_recognised(host: str) -> None:
    assert is_loopback(host)


@pytest.mark.parametrize("host", ["0.0.0.0", "192.168.1.10", "job.example.com"])
def test_public_hosts_are_not_loopback(host: str) -> None:
    assert not is_loopback(host)


def test_remote_bind_is_refused_without_opt_in(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, host="0.0.0.0", allow_remote=False)

    with pytest.raises(RuntimeError, match="Refusing to bind"):
        enforce_bind_policy(settings)


def test_remote_bind_is_allowed_with_opt_in(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, host="0.0.0.0", allow_remote=True)

    enforce_bind_policy(settings)


def test_startup_fails_on_a_public_host(tmp_path: Path) -> None:
    app = create_app(Settings(data_dir=tmp_path, host="0.0.0.0", allow_remote=False))

    with pytest.raises(RuntimeError, match="Refusing to bind"), TestClient(app):
        pass
