"""Authentication, tenant isolation and permission behavior."""

from __future__ import annotations


def register(client, email: str, org: str) -> dict:
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "correct horse battery", "name": email.split("@")[0], "organization": org},
    )
    assert res.status_code == 200, res.text
    return res.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_local_session_issues_token_and_me(local_client):
    me = local_client.get("/api/v1/auth/me")
    assert me.status_code == 200
    assert me.json()["role"] == "owner"


def test_requests_without_token_are_rejected(make_client):
    client = make_client("local")
    assert client.get("/api/v1/projects").status_code == 401


def test_untrusted_host_rejected_in_local_mode(make_client):
    client = make_client("local")
    res = client.post("/api/v1/auth/local-session", headers={"Host": "evil.example.com"})
    assert res.status_code == 400


def test_local_session_disabled_in_cloud_mode(make_client):
    client = make_client("cloud")
    assert client.post("/api/v1/auth/local-session").status_code == 404


def test_register_login_and_wrong_password(make_client):
    client = make_client("cloud")
    register(client, "ana@example.com", "Org A")
    ok = client.post("/api/v1/auth/login", json={"email": "ana@example.com", "password": "correct horse battery"})
    assert ok.status_code == 200
    bad = client.post("/api/v1/auth/login", json={"email": "ana@example.com", "password": "wrong password!"})
    assert bad.status_code == 401


def test_cross_tenant_access_is_not_found(make_client):
    client = make_client("cloud")
    a = register(client, "a@example.com", "Org A")
    b = register(client, "b@example.com", "Org B")
    created = client.post(
        "/api/v1/projects",
        json={"name": "Secret", "business_question": "Would tourists pay for a cultural experience?"},
        headers=auth(a["access_token"]),
    )
    pid = created.json()["id"]
    assert client.get(f"/api/v1/projects/{pid}", headers=auth(a["access_token"])).status_code == 200
    assert client.get(f"/api/v1/projects/{pid}", headers=auth(b["access_token"])).status_code == 404
    assert client.delete(f"/api/v1/projects/{pid}", headers=auth(b["access_token"])).status_code == 404
    listed = client.get("/api/v1/projects", headers=auth(b["access_token"])).json()
    assert listed == []


def test_rate_limit_on_login(make_client):
    client = make_client("cloud", RATE_LIMIT_AUTH_PER_MINUTE="3")
    for _ in range(3):
        client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "nope"})
    res = client.post("/api/v1/auth/login", json={"email": "x@example.com", "password": "nope"})
    assert res.status_code == 429


def test_cloud_mode_requires_secret_key(monkeypatch, tmp_path):
    import pytest

    from mdos.config import Settings

    monkeypatch.delenv("SECRET_KEY", raising=False)
    settings = Settings(mdos_mode="cloud", mdos_data_dir=tmp_path, secret_key=None)
    with pytest.raises(RuntimeError):
        settings.resolved_secret_key()


def test_project_crud_and_audit(local_client, project):
    pid = project["id"]
    res = local_client.patch(f"/api/v1/projects/{pid}", json={"decision_to_inform": "Set launch price"})
    assert res.status_code == 200
    assert res.json()["decision_to_inform"] == "Set launch price"
    actions = [e["action"] for e in local_client.get(f"/api/v1/projects/{pid}/audit").json()]
    assert "project.create" in actions and "project.update" in actions
    assert local_client.delete(f"/api/v1/projects/{pid}").status_code == 204
    assert local_client.get(f"/api/v1/projects/{pid}").status_code == 404
