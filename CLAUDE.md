# CLAUDE.md

Read [AGENTS.md](AGENTS.md) first: it holds the product rules, the architecture map, the security checklist and the
pull request checklist. This file only adds practical notes for Claude Code sessions.

## Quick facts

* Backend: Python 3.11, FastAPI, SQLAlchemy 2, Alembic, pandas, statsmodels, scikit-learn. Virtualenv at
  `backend/.venv` in local setups.
* Frontend: React 18, TypeScript (strict), Vite, TanStack Query, hand-built SVG charts with d3 scales.
* `npm run build` in `frontend/` writes into `backend/mdos/static` (gitignored except `.gitkeep`); the FastAPI app
  serves it, so one process runs everything.
* Two modes: `MDOS_MODE=local` (desktop, loopback only, passwordless) and `cloud` (accounts, needs `SECRET_KEY`).

## Commands

```bash
cd backend && .venv/bin/python -m pytest -q          # backend tests (about 60, under a minute)
cd backend && .venv/bin/ruff check mdos tests         # lint
cd frontend && npm run typecheck && npm test && npm run build
cd frontend && npx playwright test                    # E2E; starts the server itself on port 8765
cd backend && .venv/bin/python -m mdos.desktop --no-browser   # run the app locally
```

## Gotchas

* Run commands from the right folder (`backend/` or `frontend/`); many scripts assume it.
* Tests use an isolated SQLite file per test; set `TEST_DATABASE_URL` to run them on PostgreSQL.
* Agents run synchronously in tests (`EXECUTION_MODE=sync`) and in a background thread otherwise.
* The demo (`POST /projects/demo`) builds the whole loop from `backend/mdos/demo_data`; it is labeled synthetic.
* `scripts/generate_sample_data.py` is seeded; regenerating rewrites the XLSX metadata, so restore that file with git
  if nothing else changed.
* Claude calls use the model in `MDOS_LLM_MODEL` (default `claude-opus-5-5`) with server-side fallbacks enabled;
  without `ANTHROPIC_API_KEY` everything runs offline with deterministic drafting.
* User-facing text: plain language, sentence case, no em dashes.
