"""Session cookie, CSRF, sign-out, desktop launch key, response headers and safe deletion."""

from __future__ import annotations

import pytest

NO_CSRF = {"X-Requested-With": ""}
PROJECT = {"name": "Pricing test", "business_question": "Would tourists pay Rp 150,000 for a cultural experience?"}


def register(client, email: str, org: str = "Org") -> dict:
    res = client.post("/api/v1/auth/register",
                      json={"email": email, "password": "correct horse battery", "name": "Ana", "organization": org})
    assert res.status_code == 200, res.text
    return res.json()


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_session_cookie_is_httponly_and_same_site_strict(make_client):
    client = make_client("local")
    res = client.post("/api/v1/auth/local-session")
    cookie = res.headers["set-cookie"]
    assert cookie.startswith("mdos_session=")
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
    assert "Secure" not in cookie  # plain loopback HTTP


def test_secure_cookie_uses_host_prefix(make_client):
    client = make_client("cloud", COOKIE_SECURE="true")
    res = client.post("/api/v1/auth/register",
                      json={"email": "ana@example.com", "password": "correct horse battery", "name": "Ana",
                            "organization": "Org"})
    cookie = res.headers["set-cookie"]
    assert cookie.startswith("__Host-mdos_session=") and "Secure" in cookie and "HttpOnly" in cookie


def test_cookie_requests_need_the_csrf_header(local_client):
    assert local_client.get("/api/v1/projects", headers=NO_CSRF).status_code == 200  # reads are safe
    blocked = local_client.post("/api/v1/projects", json=PROJECT, headers=NO_CSRF)
    assert blocked.status_code == 403
    assert local_client.post("/api/v1/projects", json=PROJECT).status_code == 201


def test_sign_in_endpoints_need_the_csrf_header(make_client):
    local = make_client("local")
    assert local.post("/api/v1/auth/local-session", headers=NO_CSRF).status_code == 403
    cloud = make_client("cloud")
    body = {"email": "ana@example.com", "password": "correct horse battery", "name": "Ana", "organization": "Org"}
    assert cloud.post("/api/v1/auth/register", json=body, headers=NO_CSRF).status_code == 403
    assert cloud.post("/api/v1/auth/login", json=body, headers=NO_CSRF).status_code == 403


def test_bearer_tokens_do_not_need_the_csrf_header(make_client):
    client = make_client("cloud")
    token = register(client, "ana@example.com")["access_token"]
    client.cookies.clear()
    res = client.post("/api/v1/projects", json=PROJECT, headers={**NO_CSRF, **bearer(token)})
    assert res.status_code == 201


def test_logout_clears_the_session(local_client):
    assert local_client.get("/api/v1/auth/me").status_code == 200
    assert local_client.post("/api/v1/auth/logout").status_code == 204
    assert local_client.get("/api/v1/auth/me").status_code == 401


def test_logout_everywhere_revokes_every_token(make_client):
    client = make_client("cloud")
    first = register(client, "ana@example.com")["access_token"]
    login = client.post("/api/v1/auth/login", json={"email": "ana@example.com", "password": "correct horse battery"})
    second = login.json()["access_token"]
    assert client.post("/api/v1/auth/logout-all", headers=bearer(second)).status_code == 204
    for token in (first, second):
        assert client.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401
    client.cookies.clear()
    again = client.post("/api/v1/auth/login", json={"email": "ana@example.com", "password": "correct horse battery"})
    assert client.get("/api/v1/auth/me", headers=bearer(again.json()["access_token"])).status_code == 200

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from mdos.db import get_engine
    from mdos.models import AuditLog

    with Session(get_engine()) as db:
        assert db.scalars(select(AuditLog.action).where(AuditLog.action == "auth.logout_all")).all() == ["auth.logout_all"]


def test_desktop_launch_key_is_required(make_client):
    key = "launch-key-" + "x" * 32
    client = make_client("local", MDOS_LOCAL_KEY=key)
    assert client.get("/api/v1/auth/mode").json()["local_key_required"] is True
    assert client.post("/api/v1/auth/local-session").status_code == 401
    assert client.post("/api/v1/auth/local-session", json={"key": "wrong"}).status_code == 401
    ok = client.post("/api/v1/auth/local-session", json={"key": key})
    assert ok.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 200


def test_sessions_end_when_the_desktop_app_restarts(make_client):
    first = make_client("local", MDOS_LOCAL_KEY="first-launch-" + "a" * 32)
    token = first.post("/api/v1/auth/local-session", json={"key": "first-launch-" + "a" * 32}).json()["access_token"]
    assert first.get("/api/v1/auth/me", headers=bearer(token)).status_code == 200
    relaunched = make_client("local", MDOS_LOCAL_KEY="second-launch-" + "b" * 32)
    assert relaunched.get("/api/v1/auth/me", headers=bearer(token)).status_code == 401


def test_security_headers_on_app_and_api(make_client):
    client = make_client("local")
    page = client.get("/")
    csp = page.headers["content-security-policy"]
    assert "script-src 'self'" in csp and "frame-ancestors 'none'" in csp and "unsafe-inline" not in csp
    assert page.headers["cross-origin-opener-policy"] == "same-origin"
    assert "camera=()" in page.headers["permissions-policy"]
    api = client.get("/api/health")
    assert api.headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in api.headers  # loopback HTTP


def test_api_docs_are_off_unless_enabled(make_client):
    assert make_client("local").get("/api/docs").status_code == 404
    enabled = make_client("local", ENABLE_API_DOCS="true")
    docs = enabled.get("/api/docs")
    assert docs.status_code == 200 and "cdn.jsdelivr.net" in docs.headers["content-security-policy"]


def test_cors_wildcard_is_refused(make_client):
    with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
        make_client("cloud", CORS_ORIGINS="*")


def test_project_file_cleanup_stays_inside_storage(make_client, tmp_path):
    make_client("local")
    from mdos import storage

    outside = tmp_path / "keep-me"
    outside.mkdir()
    (outside / "file.txt").write_text("keep", encoding="utf-8")
    for org, project in (("..", "keep-me"), ("../..", "x"), ("not-a-uuid", "also-not"), ("", "")):
        storage.delete_project_files(org, project)
    assert (outside / "file.txt").exists()


def test_desktop_launcher_file_is_private_and_escaped(tmp_path):
    import os

    from mdos.desktop import _write_launcher

    path = _write_launcher(tmp_path / "data", 'http://127.0.0.1:8765/#key=abc"<x>')
    page = path.read_text(encoding="utf-8")
    assert 'content="0;url=http://127.0.0.1:8765/#key=abc&quot;&lt;x&gt;"' in page
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
    again = _write_launcher(tmp_path / "data", "http://127.0.0.1:8765/#key=new")  # a stale file is replaced
    assert "key=new" in again.read_text(encoding="utf-8")


def test_personal_identifiers_are_masked():
    from mdos.privacy import mask_pii

    text = ("Contact ana.putri@example.co.id or 0812-3456-7890, +62 812 3456 7890, 081234567890, "
            "+1 415 555 0100. NIK 3201234567890123.")
    masked, count = mask_pii(text)
    assert "example.co.id" not in masked and "3456" not in masked and "0100" not in masked and "3201" not in masked
    assert masked.count("[phone]") == 4 and "[email]" in masked and "[id number]" in masked and count == 6
    stats = ("Price Rp 150.000 (n = 385, p = 0.032) on 2026-08-15 at 08:30; effect +15.2 (95% CI 12.1 to 18.3), "
             "coefficient 0.85, 628 respondents, 1,250,000 visitors.")
    assert mask_pii(stats) == (stats, 0)


def test_prompts_sent_to_claude_are_masked(monkeypatch):
    import httpx
    from pydantic import BaseModel

    from mdos.agents.providers import AnthropicProvider
    from mdos.config import Settings

    provider = AnthropicProvider(Settings(anthropic_api_key="sk-ant-test-not-a-real-key", mdos_mode="local"))
    sent: dict = {}

    class FakeMessages:
        def parse(self, **kwargs):
            sent.update(kwargs)
            raise provider._anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))

    class FakeClient:
        class beta:  # noqa: N801 - mirrors the SDK attribute
            messages = FakeMessages()

    provider.client = FakeClient()

    class Out(BaseModel):
        text: str

    result = provider.generate(system="Project owner: budi@example.com", prompt="Review: call me on 0812 3456 7890",
                               schema=Out)
    assert result.parsed is None and result.meta["masked_identifiers"] == 2
    assert "budi@example.com" not in sent["system"] and "[email]" in sent["system"]
    assert sent["messages"][0]["content"] == "Review: call me on [phone]"


def test_oversized_requests_are_refused(make_client):
    client = make_client("local", MAX_JSON_MB="1", MAX_UPLOAD_MB="1")
    assert client.post("/api/v1/auth/local-session").status_code == 200
    big = b'{"name": "' + b"x" * (2 * 1024 * 1024) + b'"}'
    declared = client.post("/api/v1/projects", content=big, headers={"Content-Type": "application/json"})
    assert declared.status_code == 413 and declared.json()["error"]["code"] == "too_large"

    def chunks():  # no Content-Length: counted while streaming
        for _ in range(3):
            yield b"x" * (1024 * 1024)

    streamed = client.post("/api/v1/projects", content=chunks(), headers={"Content-Type": "application/json"})
    assert streamed.status_code == 413


def test_upload_over_the_limit_is_refused(local_client):
    pid = local_client.post("/api/v1/projects", json=PROJECT).json()["id"]
    too_big = b"a,b\n" + b"1,2\n" * (8 * 1024 * 1024)  # 32 MB, above the 25 MB default
    res = local_client.post(f"/api/v1/projects/{pid}/datasets", files={"file": ("big.csv", too_big, "text/csv")},
                            data={"kind": "survey"})
    assert res.status_code == 413


def test_xlsx_zip_bombs_are_refused(monkeypatch):
    import io
    import zipfile

    from mdos.errors import ValidationFailed
    from mdos.services import datasets

    monkeypatch.setattr(datasets, "XLSX_MIN_EXPANDED_MB", 1)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("xl/worksheets/sheet1.xml", b"0" * (30 * 1024 * 1024))  # 30 MB that compresses to ~30 KB
    with pytest.raises(ValidationFailed, match="expands"):
        datasets._check_xlsx(buffer.getvalue(), max_upload_mb=1)  # may expand to 20 MB; this one expands to 30
    with pytest.raises(ValidationFailed, match="not a valid XLSX"):
        datasets.parse_upload("fake.xlsx", b"this is not a zip file")


def test_sign_up_closes_after_the_first_account(make_client):
    body = {"email": "owner@example.com", "password": "correct horse battery", "name": "Owner", "organization": "Org"}
    client = make_client("cloud")
    assert client.get("/api/v1/auth/mode").json()["registration"] is True
    assert client.post("/api/v1/auth/register", json=body).status_code == 200
    assert client.get("/api/v1/auth/mode").json()["registration"] is False
    stranger = {**body, "email": "stranger@example.com"}
    assert client.post("/api/v1/auth/register", json=stranger).status_code == 403
    opened = make_client("cloud", ALLOW_REGISTRATION="true")
    assert opened.post("/api/v1/auth/register", json=stranger).status_code == 200
    closed = make_client("cloud", ALLOW_REGISTRATION="false")
    assert closed.post("/api/v1/auth/register", json={**body, "email": "third@example.com"}).status_code == 403


def test_login_hashes_even_for_unknown_emails(make_client, monkeypatch):
    from mdos.api import auth as auth_api

    calls: list[str | None] = []
    real = auth_api.verify_password
    monkeypatch.setattr(auth_api, "verify_password", lambda pw, h: calls.append(h) or real(pw, h))
    client = make_client("cloud")
    res = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever-123"})
    assert res.status_code == 401 and len(calls) == 1 and calls[0]  # a real hash was checked


def test_empty_settings_values_count_as_unset(monkeypatch, tmp_path):
    from mdos.config import Settings

    monkeypatch.setenv("SECRET_KEY", "")
    monkeypatch.setenv("ALLOW_REGISTRATION", "")
    settings = Settings(mdos_data_dir=tmp_path)
    assert settings.secret_key is None and settings.allow_registration is None
