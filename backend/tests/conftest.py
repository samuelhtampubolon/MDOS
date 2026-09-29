"""Shared test fixtures: isolated data directory, fresh database, local and cloud clients."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = REPO_ROOT / "samples"


def _reset_settings() -> None:
    from mdos.config import get_settings

    get_settings.cache_clear()


@pytest.fixture()
def make_client(tmp_path, monkeypatch) -> Iterator:
    """Factory: ``make_client("local")`` or ``make_client("cloud")`` with an isolated database."""
    clients: list[TestClient] = []

    def _make(mode: str = "local", **env: str) -> TestClient:
        monkeypatch.setenv("MDOS_MODE", mode)
        monkeypatch.setenv("MDOS_DATA_DIR", str(tmp_path / "data"))
        monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
        monkeypatch.setenv("EXECUTION_MODE", "sync")
        monkeypatch.setenv("SECRET_KEY", "test-secret-key-that-is-long-enough-1234567890")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        for key, value in env.items():
            monkeypatch.setenv(key, value)
        _reset_settings()
        from mdos.ratelimit import limiter

        limiter.reset()
        from mdos.main import create_app

        client = TestClient(create_app())
        client.__enter__()
        clients.append(client)
        return client

    yield _make
    for c in clients:
        c.__exit__(None, None, None)
    _reset_settings()


@pytest.fixture()
def local_client(make_client) -> TestClient:
    client = make_client("local")
    token = client.post("/api/v1/auth/local-session").json()["access_token"]
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


@pytest.fixture()
def project(local_client) -> dict:
    res = local_client.post(
        "/api/v1/projects",
        json={
            "name": "Lake Toba cultural experience",
            "business_question": "I want to know whether tourists would pay Rp 150,000 for a new Lake Toba cultural experience.",
            "industry": "tourism",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


def pytest_configure(config):  # noqa: D401 - pytest hook
    os.environ.setdefault("MDOS_MODE", "local")
