# 04. System architecture

## 1. Shape of the system

One Python application serves a JSON API and the built single-page frontend. The same code runs in two deployment
targets: a **cloud web app** and a **local desktop executable** (Graph1: "the web-based and the local exe").

```
                ┌──────────────── Browser: React + TypeScript SPA ─────────────────┐
                │ Home · Research · Strategy · Journey · Data · Agents · Reports    │
                │ Experiments · Settings                                           │
                └───────────────────────────────┬──────────────────────────────────┘
                                                │ JSON over HTTP(S), /api/v1
┌───────────────────────────────────────────────▼──────────────────────────────────┐
│ FastAPI application  (package: mdos)                                              │
│                                                                                   │
│  api/            routers, request validation, auth and permission dependencies    │
│  services/       use cases that combine domain engines, persistence and audit     │
│                                                                                   │
│  ┌──────────────────┐ ┌──────────────────┐ ┌───────────────────┐ ┌─────────────┐ │
│  │ Research engine  │ │ Strategy engine  │ │ Experience engine │ │ Agent layer │ │
│  │ analytics/       │ │ strategy/        │ │ journey/          │ │ agents/     │ │
│  │ research/        │ │  simulate, MC,   │ │  VOC, simulate,   │ │  contract,  │ │
│  │ reports/         │ │  sensitivity     │ │  experiments      │ │  registry,  │ │
│  └──────────────────┘ └──────────────────┘ └───────────────────┘ │  supervisor,│ │
│                                                                  │  providers  │ │
│  Shared kernel: auth · tenancy · permissions · audit · evidence  └─────────────┘ │
│                 graph · lineage · approvals · rate limits                         │
└───────────────┬───────────────────────────────────┬──────────────────────────────┘
                │ SQLAlchemy 2 (+ Alembic)          │ file storage (dataset versions)
      SQLite (desktop) or PostgreSQL (cloud)   Local data directory or mounted volume

      Optional outbound: Anthropic Claude API, only when ANTHROPIC_API_KEY is configured
```

## 2. Layering rules

1. **Domain engines are pure.** `analytics/`, `strategy/` and `journey/` take plain data (pandas DataFrames, dicts,
   dataclasses) and return plain results. They never touch the database, the network or an LLM. This is what makes
   statistical correctness testable.
2. **Services own persistence and side effects.** They load data, call engines, write results, create evidence and
   write audit entries in one transaction.
3. **Agents orchestrate, they do not compute numbers.** An agent may call engines through authorized tools and may
   use an LLM to draft text. Every number in an agent output comes from an engine.
4. **Routers are thin.** Validation (Pydantic), authentication, project permission checks, then one service call.

## 3. Hybrid deployment

| Concern | Desktop executable | Cloud web app |
|---|---|---|
| Process | PyInstaller bundle starts Uvicorn on `127.0.0.1` at a free port and opens the browser | Container runs Uvicorn behind a reverse proxy with TLS |
| Database | SQLite file in the user data directory | PostgreSQL (`DATABASE_URL`) |
| Files | User data directory | Mounted volume (object storage in Phase 2) |
| Auth | `MDOS_MODE=local`: single local owner, no password, API bound to loopback only | `MDOS_MODE=cloud`: email and password, JWT, organizations |
| LLM | Optional; works offline | Optional; key held in the secret manager |
| Updates | New executable; Alembic migrations run at start-up | Rolling deploy; migrations run as a release step |

## 4. Data flow and lineage

The lineage chain from the specification is implemented literally:

```
Capture source  →  Normalize  →  Transform  →  Analyze  →  Evidence  →  Insight  →  Recommendation  →  Approval
 (upload file)     (version 1)   (version n,    (Analysis   (Evidence    (Insight    (Recommendation    (Approval
                                 operations      record,     record,      linked to   linked to          record +
                                 log, checksum)  params,     value copied evidence)   evidence)          audit log)
                                                 checks)     from result)
```

* Every dataset version stores its parent, the list of operations applied, the checksum of the stored file and who
  approved it.
* Every analysis stores the dataset version, method, parameters, results, assumption checks, warnings and limitations.
* Every evidence record stores its origin: `user_data`, `external`, `model_generated`, `experiment` or `synthetic_demo`.
* The evidence graph endpoint assembles these links into nodes and edges for the UI.

## 5. Agent layer (summary)

Supervisor plus specialists, as the specification requires. Details are in
[`05-agent-architecture.md`](05-agent-architecture.md).

* A **workflow** is a bounded list of agent steps. The supervisor runs steps in order, persists a run record per step
  and stops at approval gates.
* Each step returns the **agent output contract** (`task_id`, `status`, `inputs_used`, `actions_taken`, `tools_used`,
  `evidence`, `assumptions`, `uncertainties`, `outputs`, `recommended_next_step`).
* Agents write **proposals**. Applying a proposal is a separate, audited user action that can be rolled back.
* Generative steps use a provider interface: `OfflineProvider` (deterministic templates and heuristics) or
  `AnthropicProvider` (Claude with schema-validated JSON output). If the LLM fails or returns invalid output the step
  falls back to offline logic and records the fallback as an uncertainty.

## 6. Security architecture (summary)

Full threat model: [`12-security-threat-model.md`](12-security-threat-model.md).

* Every query is scoped by organization, and every project route checks membership and role.
* Passwords hashed with Argon2id; short-lived JWT access tokens; secrets only from environment variables.
* Upload limits (size, rows, columns, file type); files stored under generated IDs, never user file names.
* Uploaded text is treated as data: it is delimited in prompts, the model is told not to follow instructions inside it,
  and outputs are schema-validated.
* Agents may call only tools on their allowlist; tools may not delete data.
* CSV exports neutralize spreadsheet formula injection.
* Audit log for every mutation, approval and agent action. Project deletion removes rows and files.

## 7. Technology choices (decision records)

| ADR | Decision | Why | Alternatives considered |
|---|---|---|---|
| ADR-001 | Python 3.11 with FastAPI for the backend | Research is 42% of the product and statistical correctness is a quality metric; statsmodels, scipy and scikit-learn are mature oracles | Node or TypeScript (weak statistics ecosystem) |
| ADR-002 | React, TypeScript and Vite SPA, served by the backend | One origin, one binary for desktop, strong typing, fast builds | Server-rendered templates (poor interactivity for canvases) |
| ADR-003 | SQLAlchemy with SQLite (desktop) and PostgreSQL (cloud) | Same models in both targets; Alembic migrations for upgrades | Separate stores per target |
| ADR-004 | LLMs never compute statistics | Hallucinated numbers would destroy trust | LLM-computed summaries (rejected) |
| ADR-005 | Agents propose, people approve | Spec: human approval gates, agents cannot silently modify critical data | Autonomous apply (rejected) |
| ADR-006 | Offline-first deterministic fallback for every agent | Desktop and low-connectivity users, cost control, reproducible tests | LLM-required design (rejected) |
| ADR-007 | Hand-built SVG charts with d3-scale and d3-shape | Waterfall, tornado, heatmap and funnel charts with consistent theming and accessibility, small bundle | A general chart library (awkward for tornado and heatmap) |
| ADR-008 | In-process execution with persisted run status in v1 | Simplest thing that satisfies "long-running tasks expose status"; queue is Phase 2 | Celery or RQ from day one |

## 8. Repository layout

```
backend/                 Python package `mdos`, tests, Alembic migrations
  mdos/api/              FastAPI routers
  mdos/services/         Use cases (persistence, audit, evidence creation)
  mdos/analytics/        Pure statistics (validated)
  mdos/research/         Construct library, design generator, questionnaire export
  mdos/strategy/         Market simulation engine
  mdos/journey/          Journey templates, VOC, journey simulation, experiments math
  mdos/agents/           Contract, registry, supervisor, providers, agent implementations
  mdos/reports/          Report builder (Markdown and HTML)
  mdos/models.py         SQLAlchemy models
  mdos/desktop.py        Desktop launcher (PyInstaller entry point)
frontend/                React + TypeScript SPA and Playwright end-to-end tests
docs/                    Specification artifacts (this folder)
packaging/               PyInstaller spec and launcher for the desktop executable
samples/                 Synthetic Lake Toba datasets (clearly labeled as synthetic)
scripts/                 Desktop build helper, sample data generator, secret scan
```
