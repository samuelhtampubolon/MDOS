# Marketing Decision OS (MDOS)

From a business question to defensible marketing evidence, strategy scenarios and a customer journey you can test.

MDOS is one application with three connected modules:

| Module | What it does |
|---|---|
| **Research Lab** | Turns a business question into a research design, a bilingual (English and Indonesian) questionnaire, a sampling and fieldwork plan, then cleans the data, runs the statistics, and drafts insights and a report. |
| **Strategy Simulator** | Builds a market model from the research evidence and simulates what happens if you change the price, the media mix or the audience, with sensitivity, Monte Carlo risk and a decision log. |
| **Journey Designer** | Maps the customer journey, finds friction in reviews and comments, simulates interventions and turns the best ones into A/B tests whose results flow back into research as evidence. |

Agents orchestrate the work and draft wording. **Numbers always come from code**, every statistic shows its assumption checks, and **people approve** every insight, verdict, decision, cleaning step and experiment launch.

> Status: MVP (version 0.1.0). The Lake Toba demo uses synthetic data. Replace the placeholder assumptions before making real decisions; the app marks them.

## Quick start

### 1. Desktop app (single user, runs only on your computer)

Download the zip for your system from the repository's **Actions** (workflow "Desktop build") or a release, unzip it and run `MDOS` (`MDOS.exe` on Windows). Your browser opens at `http://127.0.0.1:8765`. Data is stored in your user data folder (`%LOCALAPPDATA%\MDOS`, `~/Library/Application Support/MDOS` or `~/.local/share/mdos`).

Click **Load the Lake Toba demo** to see the whole loop on synthetic data.

### 2. From source

Requirements: Python 3.11+, Node.js 20+.

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# frontend (built into backend/mdos/static)
cd ../frontend
npm ci && npm run build

# run the desktop mode
cd ../backend && mdos            # or: python -m mdos.desktop
```

For development with hot reload, run `uvicorn mdos.main:create_app --factory --reload` in `backend/` and `npm run dev` in `frontend/`, then open `http://localhost:5173`. See the `Makefile` for shortcuts.

### 3. Cloud (teams, accounts, PostgreSQL)

```bash
cp .env.example .env      # set SECRET_KEY and POSTGRES_PASSWORD
docker compose up --build
```

Open `http://localhost:8000` and create the first account. For production, put TLS in front, set `ALLOWED_HOSTS`, and see [docs/13-deployment.md](docs/13-deployment.md).

## Turning on Claude (optional)

Without an API key everything works offline with deterministic drafting. To let Claude draft wording (numbers never depend on it), set:

```bash
ANTHROPIC_API_KEY=...          # enables Claude
MDOS_LLM_MODEL=claude-opus-5-5 # default
MDOS_LLM_EFFORT=medium         # low, medium or high
MDOS_LLM_FALLBACKS=true        # server-side fallback to another model when the default is unavailable
```

Model text is checked before use: prompts wrap untrusted content, numbers in drafted text must match the computed results, and causal wording is blocked unless the evidence comes from an experiment.

## How it keeps research defensible

- Every analysis reports its sample size, assumption checks (with robust alternatives when violated) and limitations.
- Insights and recommendations must cite evidence records; the evidence graph traces any item back to the dataset version it came from.
- Causal words ("causes", "drives", "increases") are rejected unless the cited evidence is experimental.
- Segmentation requires a stated objective and a variable rationale.
- Agents propose hypothesis verdicts and decisions; only a person can approve them.
- Cleaning creates a new dataset version with a checksum and an operations log; earlier versions stay restorable.

## Repository layout

```
backend/            FastAPI app, analytics engines, agents, tests (Python)
  mdos/analytics/   statistics: descriptive, cross-tabs, correlation, regression, reliability, mediation/moderation,
                    pricing (Van Westendorp, Gabor-Granger, WTP), segmentation, text themes, sentiment
  mdos/strategy/    market model, simulation engine, sensitivity, Monte Carlo, media optimizer
  mdos/journey/     journey templates, voice-of-customer mapping, intervention simulation
  mdos/agents/      agent contract, tool allowlists, Claude provider, supervisor workflows
  mdos/migrations/  database migrations (applied automatically at start-up)
frontend/           React + TypeScript web app (built into backend/mdos/static)
  e2e/              Playwright end-to-end tests (run against the real server)
packaging/          desktop executable build (PyInstaller)
docs/               synthesis, architecture, backlog, security, deployment and method notes
samples/            synthetic Lake Toba data for trying the app
```

## Development

```bash
make test        # backend tests + frontend unit tests
make lint        # ruff + TypeScript typecheck
make e2e         # end-to-end tests in a real browser
make desktop     # build the desktop executable for this OS
```

The backend test suite also runs against PostgreSQL when `TEST_DATABASE_URL` is set (CI does this).

## Documentation

Start with [docs/00-synthesis.md](docs/00-synthesis.md). Architecture: [docs/04-architecture.md](docs/04-architecture.md) and [docs/05-agent-architecture.md](docs/05-agent-architecture.md). Contributing and the rules for coding agents: [AGENTS.md](AGENTS.md).

## License

Not yet chosen. Until a license is added, all rights are reserved by the repository owner.
