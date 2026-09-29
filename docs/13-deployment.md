# 13 · Deployment Architecture

One codebase ships two ways. The same FastAPI process serves the API and the built React app in both.

```
Desktop (local mode)                              Cloud (cloud mode)
┌──────────────────────────────┐                  ┌───────────────┐   ┌──────────────────────────┐
│ MDOS executable (PyInstaller)│                  │ TLS proxy /   │──▶│ mdos container(s)        │
│  uvicorn on 127.0.0.1:8765   │                  │ load balancer │   │  uvicorn :8000, non-root │
│  SQLite + files in user data │                  │ (HSTS, limits)│   │  migrations at start-up  │
│  browser opens automatically │                  └───────────────┘   └───────┬──────────┬───────┘
└──────────────────────────────┘                                              │          │
                                                                    PostgreSQL 16     /data volume
                                                                    (managed, TLS)    (uploaded files)
```

## 1. Desktop

| Item | Detail |
|---|---|
| Build | `python scripts/build_desktop.py` (frontend build, then PyInstaller with `packaging/mdos.spec`); CI workflow "Desktop build" produces Windows, macOS and Linux zips |
| Run | Unzip and run `MDOS` / `MDOS.exe`; options: `--port`, `--strict-port`, `--data-dir`, `--no-browser` |
| Data | `%LOCALAPPDATA%\MDOS`, `~/Library/Application Support/MDOS` or `~/.local/share/mdos`: `mdos.db` (SQLite, WAL), `files/`, `secret.key` |
| Network | Listens on 127.0.0.1 only; rejects foreign Host headers |
| Updates | Replace the folder; the database migrates automatically on start. Back up the data folder first |
| Size | About 130 MB zipped (Python runtime, scientific stack, built UI) |

Open items: code signing (Windows Authenticode, Apple Developer ID and notarization) so users do not see
SmartScreen or Gatekeeper warnings; an installer and auto-update are Phase 2.

## 2. Cloud

### Container

* `Dockerfile`: stage 1 builds the web app with Node 20; stage 2 is `python:3.11-slim` with the dependencies, runs as
  user `mdos` (uid 10001), exposes 8000, has a health check on `/api/health` and stores files in the `/data` volume.
* Start command: `uvicorn mdos.main:create_app --factory --host 0.0.0.0 --port $PORT --proxy-headers`.
* Migrations run at start-up (Alembic). With several replicas, start one first or run
  `alembic -c alembic.ini upgrade head` as a release step.

### Required configuration

| Variable | Value |
|---|---|
| `MDOS_MODE` | `cloud` (set in the image) |
| `SECRET_KEY` | 48+ random characters from the platform's secret store |
| `DATABASE_URL` | `postgresql+psycopg://user:password@host:5432/mdos?sslmode=require` |
| `ALLOWED_HOSTS` | Public host name(s), for example `mdos.example.com` |
| `ALLOW_REGISTRATION` | Empty (default): only the first account may sign up. `true`: open sign-up. `false`: closed |
| `FORWARDED_ALLOW_IPS` | Your reverse proxy's address (default `127.0.0.1`); only it may set client IP and https headers |
| `COOKIE_SECURE` | Empty: Secure cookie when the request arrived over https. `true` to always require https |
| `ANTHROPIC_API_KEY` | Optional; enables Claude drafting |
| `MDOS_LLM_MODEL`, `MDOS_LLM_EFFORT`, `MDOS_LLM_FALLBACKS` | Optional model settings (defaults `claude-opus-5-5`, `medium`, `true`) |

See `.env.example` for limits and rate limits.

### Hosting options (choose one)

| Option | Fit | Notes |
|---|---|---|
| A container platform (Google Cloud Run, AWS App Runner, Azure Container Apps, Fly.io, Railway, Render) with managed PostgreSQL | Recommended for the MVP | Mount or attach persistent storage for `/data`, or move files to object storage (Phase 2). Keep one instance until the rate limiter uses a shared store |
| A single VM with `docker compose` (the included `docker-compose.yml`) behind Caddy or Nginx | Cheapest; fine for pilots | Add TLS in the proxy, daily `pg_dump` backups and OS updates |
| Kubernetes | Later, for enterprise customers | Needs a shared rate limit store and object storage first |

For Indonesian customers, choose a Jakarta region (available on the major clouds) to keep latency low and to simplify
personal data residency conversations.

### Backups and recovery

* PostgreSQL: daily snapshots plus point-in-time recovery; test a restore every quarter.
* `/data` volume (uploaded files): daily snapshot; files are referenced by generated keys from the database.
* Recovery objective for the MVP: restore within 4 hours, lose at most 24 hours of data (tighten later).

### Release process

1. Merge to `main` after CI passes (lint, tests on SQLite and PostgreSQL, migration drift check, E2E, Docker smoke test).
2. Build and push the image (tag with the commit SHA and the version).
3. Deploy; the container migrates the database on start.
4. Smoke test `/api/health` and one login; roll back by redeploying the previous image (migrations are additive by
   policy, see AGENTS.md).

## 3. Local development

```bash
make install     # backend (editable) and frontend dependencies
make dev-api     # API with reload on :8000
make dev-web     # Vite on :5173 (proxies /api)
```
