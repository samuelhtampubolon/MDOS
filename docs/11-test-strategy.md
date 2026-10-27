# 11. Test strategy

## Goals

1. **Statistical correctness** (a spec quality metric): every analytics function is checked against an independent
   oracle.
2. **Traceability**: evidence values equal analysis values; every recommendation cites evidence.
3. **Safety of agent behavior**: output contract, tool authorization, approval gates, rollback.
4. **Security**: tenant isolation and permission checks are tested as behavior, not assumed.
5. **Working product**: the Lake Toba closed loop runs end to end in a real browser.

## Test layers

| Layer | Tooling | What it covers | Runs in CI |
|---|---|---|---|
| Analytics unit tests | pytest | Each statistical method against an oracle (below) | Yes |
| Engine unit tests | pytest | Strategy simulation math, sensitivity, Monte Carlo reproducibility; journey simulation, prioritization | Yes |
| Agent tests | pytest | Contract shape for every agent, offline determinism, tool allowlists, fallback on LLM failure, numeric grounding check, prompt-injection containment | Yes |
| API integration tests | pytest with FastAPI TestClient on SQLite, and on PostgreSQL via `TEST_DATABASE_URL` | Auth, projects, uploads, analyses, evidence, insights, approvals, reports, scenarios, journeys, experiments, audit entries | Yes (both databases) |
| Security tests | pytest | Cross-tenant access returns 404, viewer cannot mutate, upload limits, formula-injection neutralization, rate limiting | Yes |
| Frontend unit tests | Vitest | Formatting (rupiah, percentages, p-values, signed changes) | Yes |
| Type checks and lint | ruff, TypeScript `tsc -b` (strict), Alembic drift check | Static correctness; migrations match the models | Yes |
| End-to-end | Playwright (Chromium) against the real server in desktop mode | Demo loads through the agents; every module renders without console errors; insight approval; causal-language gate and suggested rewrite; hypothesis add; sample size; pricing scenario; touchpoint; intervention to A/B test to experimental evidence; approvals; dark theme | Yes |
| Packaging smoke tests | Docker, PyInstaller | The image starts in cloud mode and serves the UI; the desktop executable starts and answers the health check on Windows, macOS and Linux | Yes |

## Current counts (version 0.1.0)

| Suite | Count | Location |
|---|---|---|
| Backend tests | 87 | `backend/tests` (security 25, analytics 24, auth and tenancy 12, strategy 10, agents 7, journey 6, research flow 3) |
| Frontend unit tests | 7 | `frontend/src/lib/format.test.ts` (4), `frontend/src/styles/styles.test.ts` (3: no shadows, gradients, scale transforms or fixed radii) |
| End-to-end tests | 13 | `frontend/e2e/closed-loop.spec.ts` (includes the desktop launch key, cookie and CSRF checks, the sandboxed export and phone-width layout) |
| CI security job | 3 steps | secret scan (`scripts/check_secrets.py`), `pip-audit` on `backend/requirements.txt`, `npm audit` with npm registry signature verification |

## Statistical oracles

| Method | Oracle |
|---|---|
| Descriptive statistics | numpy and pandas reference computations |
| Cross-tab and chi-square, Cramér's V | `scipy.stats.chi2_contingency`, hand-computed V |
| Correlation | `scipy.stats.pearsonr`, `spearmanr` |
| OLS regression, robust errors, VIF, Breusch-Pagan | statsmodels `OLS`, `variance_inflation_factor`, `het_breuschpagan` on known data; closed-form coefficients on noiseless data |
| Logistic regression | statsmodels `Logit`; recovery of known coefficients on simulated data |
| Cronbach's alpha | Hand-computed formula on a small matrix; alpha of identical items equals 1 |
| PROCESS Model 4 | a, b, c and c' equal separate OLS fits; c = c' + ab identity holds exactly for OLS; bootstrap interval contains the true indirect effect on simulated data |
| PROCESS Model 1 | Interaction coefficient equals statsmodels formula fit; simple slope standard errors equal delta-method values |
| Van Westendorp | Hand-constructed data with known intersection points |
| Gabor-Granger | Known acceptance shares and revenue-maximizing price |
| Sample size | Closed-form formulas (for example n = 385 for p = 0.5, e = 0.05, 95%) |
| Two-proportion test | `statsmodels.stats.proportion.proportions_ztest` |
| k-means | Recovery of well-separated synthetic clusters; silhouette from scikit-learn |
| Sentiment | Labeled bilingual sentences including negation and intensifiers |

## Quality gates as tests

Each specification quality gate has at least one test:

| Quality gate | Test |
|---|---|
| No statistical method without checking assumptions | Every analysis result must include a non-empty `assumptions` list |
| No causal language without an appropriate design | Insight creation with "causes" on survey-only evidence is rejected with HTTP 422 |
| No segmentation without objective and variable rationale | Segmentation request without them is rejected with HTTP 422 |
| No hypothesis marked supported solely because an AI agent says so | Agent verdicts are created as `proposed_*`; only an approval changes the status, and approval requires linked evidence |
| Every recommendation cites evidence | Recommendation without evidence is rejected with HTTP 422 |

## Test data

* Unit tests generate their own data with fixed seeds.
* Integration and end-to-end tests use the synthetic Lake Toba datasets in `samples/`, generated by
  `scripts/generate_sample_data.py` with a fixed seed and planted data-quality issues.
* No real personal data is used anywhere in the test suite.

## After each major change (spec build rule)

The pull-request checklist in `AGENTS.md` asks for: validation run, regression risk, UX consistency, data lineage,
security implications and a `CHANGELOG.md` entry.
