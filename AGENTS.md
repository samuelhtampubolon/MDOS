# AGENTS.md: working on MDOS

Instructions for coding agents (Codex, Claude Code, Antigravity, Grok Build, OpenCode, OpenClaw) and for people.
Read this before changing code. Product background: [README](README.md) and [docs/00-synthesis.md](docs/00-synthesis.md).

## 1. Roles

| Agent | Best used for in this repository |
|---|---|
| **Codex** | Full-stack implementation of backlog items, tests, multi-file refactors (for example a new analysis method end to end) |
| **Claude Code** | Exploring the codebase, debugging failing tests or workflows, code review against this file, careful refactors |
| **Antigravity** | Longer multi-step builds that span backend, frontend and docs (for example survey hosting), coordinating sub-tasks |
| **Grok Build** | Quick UI prototypes and chart experiments in `frontend/` that are then hardened by another agent or a person |
| **OpenCode** | Model-driven experiments (prompt changes, new agent drafts) behind the offline fallback |
| **OpenClaw** | Operational workflows: scheduled checks, release notes, notifications; never merges or approves on its own |

Any agent may do any task; the table says where each is strongest. People approve pull requests.

## 2. Workflow

1. Inspect the repository and read the relevant docs (`docs/04-architecture.md`, `docs/05-agent-architecture.md`).
2. Work on a branch or worktree; keep each change a small vertical slice (engine, service, API, UI, tests, docs).
3. Run the checks (section 6) and fix everything before asking for review.
4. Review security (section 5) and UX (docs/09-design-system.md) for the change.
5. Record decisions that change behavior in `docs/decisions/` and user-visible changes in `CHANGELOG.md`.
6. Open a pull request with the checklist (section 7).

## 3. Product rules (do not break these)

* **Numbers come from code.** Statistics, simulations and sample sizes are computed in `backend/mdos/analytics`,
  `strategy` and `journey`. A language model may choose methods and draft wording; it never produces numbers. Drafted
  text must pass the numeric grounding check.
* **People decide.** Cleaning plans, design adoption, hypothesis verdicts, insights, recommendations, decisions,
  experiment launches and final reports go through an approval. Agents propose.
* **Evidence first.** Insights, recommendations and decisions cite evidence records. Causal wording requires
  experimental evidence (the quality gate enforces it; do not bypass it).
* **Label what is not data.** Assumptions carry a source and confidence; synthetic data and model-generated wording
  are labeled wherever they appear.
* **Every analysis reports** its sample size, assumption checks, warnings and limitations.
* **Research stays the core.** The Research Lab must remain at least 40% of product scope
  (measured in docs/10-mvp-backlog.md).
* **Out of scope:** mass content generation, autonomous decisions, presenting generated numbers as data.

## 4. Where code goes

```
backend/mdos/
  analytics/  strategy/  journey/   pure engines: pandas in, results out; no database, no HTTP
  services/                         persistence, lineage, audit and evidence around the engines
  api/                              thin FastAPI routers (validation, access checks, commit)
  agents/                           agent classes, tool allowlists, supervisor workflows, Claude provider
  models.py  migrations/            SQLAlchemy models and Alembic revisions
frontend/src/
  pages/                            one folder or file per module page
  components/  components/charts/   shared UI and hand-built SVG charts
  api/                              typed client, React Query hooks, response types
```

* New analysis method: engine function with checks and evidence candidates, registry entry with a parameter schema,
  validation test against a reference library or formula, a parameter form in `AnalysisStudio.tsx`, a chart mapping in
  `AnalysisChart.tsx` if needed, and a row in `docs/17-methods-reference.md`.
* New agent: subclass in `agents/`, declare its tools (allowlist), return the 10-field contract, add it to a workflow
  and to the registry coverage table, test it with the fake provider.

## 5. Security checklist for every change

* Project routes use `project_access`; child entities use `get_owned(..., project_id)`; writes call
  `access.require("editor")`; mutations call `audit.record(...)`.
* No raw SQL from input; no secrets in code, logs or the frontend; `.env` stays untracked.
* Uploads and exports go through the existing limits and `safe_cell` sanitizing.
* Customer text sent to a model is wrapped with `wrap_untrusted`; model output is validated before use.
* Local mode stays loopback-only; never relax the trusted-host check.
* See docs/12-security-threat-model.md.

## 6. Commands

```bash
make install                      # backend (editable, dev extras) and frontend dependencies
make test                         # backend tests and frontend unit tests
make lint                         # ruff, migration drift check, TypeScript typecheck
make e2e                          # Playwright against the real server
cd backend && TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/mdos_test pytest   # PostgreSQL
make migration m="describe change"   # after changing models
```

Conventions: Python 3.11, ruff (line length 110); TypeScript strict with no unused code; sentence case and plain
language in the UI; no em dashes in user-facing text; rupiah as `Rp 150.000`; Indonesian text marked `lang="id"`.
Migrations are additive (add columns and tables; migrate data in a separate step) so a previous image can still run.

## 7. Pull request checklist

- [ ] The change is a small vertical slice with tests (engine tests validate numbers against a reference).
- [ ] `make lint`, `make test` and, for UI changes, `make e2e` pass; CI is green.
- [ ] Access checks, audit records and approval gates are in place (section 5).
- [ ] No causal wording without experimental evidence; generated content is labeled.
- [ ] Models changed: migration added and `alembic check` passes; tested on PostgreSQL if queries changed.
- [ ] UI follows docs/09-design-system.md (status with icon and text, table view for charts, keyboard access).
- [ ] Docs and CHANGELOG updated; decisions recorded in docs/decisions when behavior changes.
- [ ] No secrets, personal data or real respondent data in the diff.
