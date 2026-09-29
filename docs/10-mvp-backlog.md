# 10. MVP backlog and status

Status of the MVP scope in [`03-mvp-scope.md`](03-mvp-scope.md), the measured weight of each module, and the next
backlog. "Verified" names the automated check that proves the item (backend tests `T`, end-to-end tests `E2E`).

## 1. Research-first guardrail (measured)

The specification requires the Research Lab to stay at or above 40% of product scope. Measured as non-blank lines of
application and test code (Python, TypeScript and CSS; generated files, migrations and the built UI excluded):

| Module | Lines | Share of module code | Share of all code |
|---|---|---|---|
| Research Lab | 8,658 | 67.9% | 42.0% |
| Strategy Simulator | 2,102 | 16.5% | 10.2% |
| Journey Designer (with experiments) | 1,989 | 15.6% | 9.7% |
| Shared platform (auth, agents runtime, UI kit, charts, packaging) | 7,851 | | 38.1% |

The Research Lab is above 40% on both measures. Strategy and Journey are below the specification's long-run targets
(31% and 27%) by design for this phase: they are thin, working slices that consume research evidence, as the MVP scope
states. The measurement script is reproducible (see section 4).

## 2. MVP status

### Research Lab

| Item | Status | Verified |
|---|---|---|
| Projects from a business question (name, decision, context, currency) | Done | T, E2E |
| Research design workflow (framing, design, questionnaire, sampling, fieldwork, QA) with adoption gate and rollback | Done | T agents |
| Construct library (14 constructs, EN and ID items, citations) | Done | T |
| Hypothesis canvas (add, edit until a verdict is approved, verdict approval) and variable dictionary | Done | T, E2E |
| Questionnaire (sections, types, screening), XLSForm, Markdown and codebook exports, approval after pilot | Done | T |
| Sample size calculator (share, mean, margin of error, A/B test) | Done | T formulas, E2E |
| Data import (CSV, TSV, XLSX), profiling, limits | Done | T |
| Data quality diagnostics (9 checks) | Done | T |
| Cleaning plan, approval, versioning with checksum and restore | Done | T, E2E |
| Analysis studio (15 methods) with assumption checks | Done | T (24 analytics tests) |
| Evidence records and evidence graph | Done | T, E2E |
| Insights and recommendations with evidence and causal-language gates | Done | T, E2E |
| Research QA (assumptions, causal language, coverage, sample adequacy, hypothetical bias) | Done | T agents |
| Reports (research report with data appendix, executive summary, decision memo, methods appendix, experiment brief), Markdown and HTML, finalize | Done | T |
| Column-to-variable mapping | Automatic by name; a manual mapping screen is Phase 2 | T |

### Strategy Simulator

| Item | Status | Verified |
|---|---|---|
| Market model canvas with editable assumptions (source and confidence) | Done | T, E2E |
| Simulation per channel and segment | Done | T |
| Evidence-backed baseline (price curve, WTP by segment, segment shares) | Done | T agents |
| Scenarios (price, budget, segment mix, competitor shocks, conversion, word of mouth) and comparison | Done | T, E2E |
| Break-even, CLV, CAC, ROMI, waterfall, tornado, Monte Carlo, price curve, media optimizer | Done | T |
| Positioning map | Done | E2E |
| Decision log with approval | Done | T, E2E |

### Journey Designer

| Item | Status | Verified |
|---|---|---|
| Journey templates (tourism, generic), stages, touchpoints, continue rates | Done | T, E2E |
| Voice of customer (bilingual stage mapping, sentiment, themes, quotes) | Done | T |
| Emotion curve and friction heatmap | Done | E2E |
| Pain-point prioritization (frequency, severity, reach) | Done | T |
| Interventions with low, mid and high simulations | Done | T |
| Experiments (brief, sample size, launch approval, results as experimental evidence) | Done | T, E2E |

### Shared platform

| Item | Status | Verified |
|---|---|---|
| Organizations, users, roles, tenant isolation | Done | T (SQLite and PostgreSQL) |
| Local (desktop) and cloud modes | Done | T, packaged build smoke test |
| Audit log, approvals inbox, agent run log with the 10-field contract | Done | T, E2E |
| Optional Claude drafting with offline fallback and output guards | Done | T with a fake provider |
| Rate limits, upload limits, export formula neutralizing, security headers | Done | T |
| Docker image, docker-compose, desktop executable, CI | Done | CI (Docker smoke test, desktop build workflow) |

## 3. Next backlog (Phase 2, in priority order)

1. **Pilot readiness:** replace demo placeholders with real inputs (market size, costs, funnel rates), Indonesian
   language review of the questionnaire, code signing for the desktop build.
2. **Survey hosting** (public links, quotas, live fieldwork tracker) so fieldwork does not need another tool.
3. **Integrations:** Google Forms and Sheets, KoboToolbox API, Google Business Profile reviews.
4. **PLS-SEM** (most requested by the first segment), then EFA and CFA.
5. **Choice-based conjoint and MaxDiff** for pricing and feature trade-offs.
6. **Background job queue and object storage** (for multiple cloud instances), shared rate limit store.
7. **Observability** next steps (structured logs, error tracking, metrics; see [`14-observability.md`](14-observability.md)).
8. **Billing** once pricing tests conclude (see [`15-pricing-gtm-hypotheses.md`](15-pricing-gtm-hypotheses.md)).
9. **Full Bahasa Indonesia interface.**
10. **DOCX and PPTX report export.**

## 4. Reproducing the measurement

Count non-blank lines per file group from the repository root (the grouping used above):

* Research: `backend/mdos/{analytics,research,reports}`, research-related services and API routers
  (`research`, `datasets`, `analyses`, `evidence`, `reports`), `agents/research_agents.py`,
  `frontend/src/pages/research`, `LineageGraph.tsx`, `AnalysisChart.tsx`, `pages/Reports.tsx`, `pages/Data.tsx`,
  and the research and analytics tests.
* Strategy: `backend/mdos/strategy`, the strategy service and router, `agents/strategy_agents.py`,
  `frontend/src/pages/strategy`, `tests/test_strategy.py`.
* Journey: `backend/mdos/journey`, the journey service, the journey and experiments routers,
  `agents/journey_agents.py`, `frontend/src/pages/journey`, `pages/Experiments.tsx`, `tests/test_journey.py`.
* Everything else is shared platform.
