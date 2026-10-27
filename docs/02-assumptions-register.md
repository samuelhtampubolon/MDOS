# 02. Assumptions register

Every assumption the build rests on, where it came from, how confident we are, and how it will be validated.
Status values: **Open** (unvalidated), **Validated**, **Invalidated**, **Superseded**.

Source codes: `G` founder vision notes (Graph1), `S` specification, `J` professional judgment, `D` technical default.

## Product and market

| ID | Assumption | Source | Confidence | Impact if wrong | Validation method | Status |
|---|---|---|---|---|---|---|
| A01 | Indonesian university researchers and consultants will pay before SMEs do. | G, J | Medium | Wrong first segment; slower revenue | 10 discovery interviews per segment; Van Westendorp study run in MDOS itself | Open |
| A02 | "Business question to defensible evidence" is more valuable to the target users than faster questionnaire generation. | G | Medium-high | Differentiation collapses into commodity AI survey tools | Pilot: measure insight acceptance rate and customer-reported decision value | Open |
| A03 | Tourism is the best showcase domain for the journey module. | G | High | Demo resonates less with non-tourism buyers | Offer a retail and an education template in Phase 3 | Open |
| A04 | Users need a desktop executable as well as a web app (privacy, connectivity, institutional habits). | G | High | Wasted packaging effort | Track desktop versus web usage among pilots | Open |
| A05 | English UI is acceptable for v1 if instruments and text analytics are bilingual. | J | Medium | Adoption friction among SMEs | Pilot feedback; i18n-ready UI makes Bahasa Indonesia a translation task | Open |
| A06 | Rupiah is the right default currency; other currencies must remain possible. | G | High | Minor: currency is a per-project setting | n/a | Validated |

## Research method

| ID | Assumption | Source | Confidence | Impact if wrong | Validation method | Status |
|---|---|---|---|---|---|---|
| A10 | Most first projects are cross-sectional surveys with 100 to 1,000 respondents. | J | High | Performance tuning and method defaults need revisiting | Log dataset sizes (anonymized counts only) | Open |
| A11 | Stated willingness to pay overstates real willingness to pay; results must be labeled and validated behaviorally. | J (literature on hypothetical bias) | High | Over-optimistic pricing decisions | Built-in limitation text plus experiment recommendation | Validated (literature) |
| A12 | Van Westendorp plus Gabor-Granger plus a direct target-price question is an adequate MVP price-research design. | J | Medium-high | Need conjoint earlier | Compare with conjoint in Phase 2 on the same sample | Open |
| A13 | Five-point Likert items adapted from established scales are acceptable to academic users if the source construct is cited. | J | Medium | Users want exact published wording | Construct library cites the source; researcher verifies wording (manual step) | Open |
| A14 | PROCESS Models 1 and 4 cover most moderation and mediation needs of the first users. | J | Medium | Users need Models 7, 8, 14 or serial mediation | Usage logs and requests; add models in Phase 2 | Open |
| A15 | A curated bilingual lexicon gives usable sentiment for short tourism reviews; an LLM improves it when available. | J | Medium | Mis-classified sentiment misleads journey maps | Human-labeled validation sample (manual step); show confidence and allow overrides | Open |
| A16 | Percentile bootstrap with 5,000 resamples is an acceptable default for indirect effects. | J (Hayes 2022) | High | Slow on large data | Configurable; seed recorded for reproducibility | Validated (literature) |

## Strategy and journey models

| ID | Assumption | Source | Confidence | Impact if wrong | Validation method | Status |
|---|---|---|---|---|---|---|
| A20 | A transparent funnel model (reach, engagement, leads, conversion) is more useful to target users than a black-box marketing mix model. | S, G, J | High | Users want MMM from historical data | Phase 2: calibrate funnel rates from uploaded campaign data | Open |
| A21 | Reach saturates following a Poisson exposure model: reach = N(1 - e^(-impressions/N)). | J | Medium | Mis-estimated returns on budget shifts | Calibrate with platform reach data; allow a custom saturation factor | Open |
| A22 | Competitor price shocks can be approximated with a cross-price elasticity per segment. | J | Medium | Over or under-reaction to competitor moves | Sensitivity analysis always shown; Phase 2 logit choice model from conjoint | Open |
| A23 | Step-level drop-off in booking flows is roughly independent, so completion = p^steps. | J | Low-medium | Overstates the gain from removing steps | A dampening factor is applied by default and the result is labeled as an estimate to validate with an A/B test | Open |
| A24 | Mean sentiment by journey stage is a reasonable first proxy for the emotion curve. | J | Medium | Emotion map misleads | Allow manual overrides; show number of mentions per stage | Open |

## Technical

| ID | Assumption | Source | Confidence | Impact if wrong | Validation method | Status |
|---|---|---|---|---|---|---|
| A30 | Python (FastAPI, pandas, statsmodels, scipy, scikit-learn) is the right backend for statistical correctness. | D | High | n/a | Validation tests against library oracles | Validated |
| A31 | SQLite for desktop and PostgreSQL for cloud through SQLAlchemy is sufficient; no database-specific features are needed in v1. | D | High | Migration friction | CI runs tests on SQLite; PostgreSQL smoke test in Docker | Open |
| A32 | Agents can run in-process with persisted status in v1; a queue (Redis with a worker) is needed only for multi-user cloud scale. | D | Medium | Slow requests under load | Load test before public launch | Open |
| A33 | The product must work fully without an LLM API key (offline, deterministic), with Claude improving generative steps when configured. | J (cost, privacy, offline desktop) | High | n/a | Tests run in offline mode by default | Validated |
| A34 | LLMs never compute statistics; all numbers come from deterministic code. | J | High | n/a | Architecture rule; tests check that evidence values match analysis results | Validated |
| A35 | Datasets up to about 50,000 rows by 300 columns fit in memory for analysis. | D | High | Large imports fail | Upload size limit and row limit with clear errors | Open |

## Change log for this register

| Date | Change |
|---|---|
| 2026-09-28 | Register created from the specification and founder vision notes. |
