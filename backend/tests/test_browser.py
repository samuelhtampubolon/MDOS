"""The in-browser engine behind the live demo (mdos.browser), exercised natively with asyncio."""

from __future__ import annotations

import asyncio
import json

import anyio.to_thread
import pytest

from mdos import browser
from mdos.config import get_settings

JSON = [["content-type", "application/json"], ["x-requested-with", "mdos"]]


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    # The engine sets these for the page it runs in; record them so the rest of the suite gets them back.
    for name in ("MDOS_MODE", "MDOS_DATA_DIR", "EXECUTION_MODE", "ANTHROPIC_API_KEY", "DATABASE_URL", "MDOS_LOCAL_KEY"):
        monkeypatch.setenv(name, "")
    monkeypatch.setattr(anyio.to_thread, "run_sync", anyio.to_thread.run_sync)
    eng = browser.Engine(str(tmp_path / "data"))
    asyncio.run(eng.start())
    yield eng
    asyncio.run(eng.stop())
    get_settings.cache_clear()


def call(eng: browser.Engine, method: str, path: str, body: dict | None = None, query: str = "") -> tuple[int, dict]:
    raw = json.dumps(body).encode() if body is not None else b""
    res = asyncio.run(eng.handle(method, path, query, JSON, raw))
    return res["status"], (json.loads(res["body"]) if res["body"] else {})


def test_engine_runs_the_app_offline_in_local_mode(engine, tmp_path):
    status, health = call(engine, "GET", "/api/health")
    assert status == 200 and health["mode"] == "local"
    _, mode = call(engine, "GET", "/api/v1/auth/mode")
    assert mode["local_key_required"] is False  # no launch key in the demo
    assert get_settings().execution_mode == "sync" and get_settings().anthropic_api_key is None
    assert (tmp_path / "data" / "mdos.db").exists()


def test_session_cookie_is_kept_by_the_engine(engine):
    assert call(engine, "GET", "/api/v1/auth/me")[0] == 401
    status, _ = call(engine, "POST", "/api/v1/auth/local-session", {})
    assert status == 200 and engine.jar.cookies  # the jar, not the browser, holds the session
    status, me = call(engine, "GET", "/api/v1/auth/me")
    assert status == 200 and me["email"]


def test_the_whole_demo_builds_in_line(engine):
    call(engine, "POST", "/api/v1/auth/local-session", {})
    status, project = call(engine, "POST", "/api/v1/projects/demo", {})
    assert status == 201
    status, detail = call(engine, "GET", f"/api/v1/projects/{project['id']}")
    assert status == 200 and detail["brief"]["demo_status"] == "ready"


def test_only_api_paths_are_answered(engine):
    res = asyncio.run(engine.handle("GET", "/index.html", "", [], b""))
    assert res["status"] == 404


def test_cookie_jar_follows_set_cookie():
    jar = browser.CookieJar()
    jar.update("mdos_session=abc; Path=/; HttpOnly; SameSite=strict")
    assert jar.header() == "mdos_session=abc"
    jar.update('mdos_session=""; Max-Age=0; Path=/')
    assert jar.cookies == {}
