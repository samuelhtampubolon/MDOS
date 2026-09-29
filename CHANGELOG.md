# Changelog

All notable changes to MDOS are recorded here. The format follows Keep a Changelog; versions follow semantic
versioning.

## [Unreleased]

### Security

- Browser sessions moved to an HttpOnly, SameSite=Strict cookie with a CSRF header check; sign out and sign out on
  all devices; the desktop app needs a per-launch key and ends sessions when it closes.
- Strict Content Security Policy, sandboxed HTML exports, COOP, CORP, Permissions-Policy, HSTS and `no-store`.
- Personal identifiers masked before prompts reach Claude; request body limits; XLSX zip-bomb check; confirmed,
  confined project deletion; sign-up open only for the first cloud account by default; login timing equalized.
- Container published on 127.0.0.1, read-only root, no capabilities, proxy headers trusted only from
  `FORWARDED_ALLOW_IPS`; interactive API docs off by default; `CORS_ORIGINS="*"` refused.
- Supply chain: hash-pinned Python dependencies, npm without install scripts, actions pinned to commits,
  Dependabot, `pip-audit`, `npm audit` and a secret scan in CI; vulnerable packages upgraded; Node.js 24 LTS.
- New [SECURITY.md](SECURITY.md) and [docs/19-security-hardening-review.md](docs/19-security-hardening-review.md).
- Second review: owner-only desktop data folder, stray `.env` files ignored by the desktop app, a browser-session
  cookie on the desktop, no server header, masked CI keys, npm registry signature checks, explicit setup errors.

### Added

- MIT License and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md); the desktop bundle leaves out the PostgreSQL
  driver.

### Changed

- Interface redesigned as "Quiet Ledger" ([docs/18-interface-brief.md](docs/18-interface-brief.md)): IBM Plex
  type, flat surfaces with one radius, a single accent job, a next-step-led research dashboard, projects-first Home,
  designed loading, empty and error states, and layouts that fit phones.
- README in a numbered, badge-led layout with screenshots; issue forms, a pull request template and CODEOWNERS.

## [0.1.0] - 2026-09-29

First MVP: the Research Lab in full, with working slices of the Strategy Simulator and the Journey Designer connected
in a closed loop.

### Added

- **Research Lab:** projects from a business question; research design workflow (problem framing, design,
  questionnaire, sampling, fieldwork, QA) with an adoption gate and rollback; construct library with English and
  Indonesian items; hypothesis canvas with evidence-based verdicts approved by people; bilingual questionnaire with
  XLSForm, Markdown and codebook exports; sample size calculator; CSV and Excel import with profiling; nine data quality
  checks; cleaning plans with approval, versioning, checksums and restore; 15 analysis methods with assumption checks
  (descriptives, cross-tabs, correlation, OLS and logistic regression, reliability, mediation, moderation, Van
  Westendorp, Gabor-Granger, willingness to pay, segmentation with personas, text themes, sentiment, voice of the
  customer); evidence register and lineage graph; insights and recommendations with evidence and causal-language
  gates; reports with citations in Markdown and HTML.
- **Strategy Simulator:** evidence-backed market model with labeled assumptions; scenarios for price, budget, segment
  mix and competitor moves; profit bridge, sensitivity, Monte Carlo risk, price curves limited to tested prices, media
  optimizer, positioning map and a decision log with approval.
- **Journey Designer:** tourism and generic journey templates, touchpoints, emotion curve, friction heatmap, ranked pain
  points, interventions with low, mid and high simulations, and A/B tests whose results become experimental evidence.
- **Agents:** 26 executable agents covering 47 of the 50 agents in the specification, a 10-field output contract, tool
  allowlists, supervisor workflows with retry, cancel and rollback, and optional Claude drafting with offline
  fallback, untrusted-data wrapping and numeric grounding.
- **Platform:** organizations, roles and tenant isolation; desktop mode (loopback only) and cloud mode (accounts);
  audit log and approvals inbox; rate limits, upload limits, security headers and allowed hosts; Alembic migrations;
  light and dark themes with an accessible, color-blind-safe chart palette.
- **Delivery:** desktop executable build (PyInstaller) for Windows, macOS and Linux; Docker image and docker-compose
  with PostgreSQL; CI with tests on SQLite and PostgreSQL, a migration drift check, Playwright end-to-end tests and a
  Docker smoke test.
- **Demo:** one-click Lake Toba project on synthetic data that runs the whole loop through the agents.
- **Docs:** synthesis, interview, assumptions, scope, architecture, agent architecture, design system, backlog, test
  strategy, threat model, deployment, observability, pricing and go-to-market hypotheses, section catalog and methods
  reference.
