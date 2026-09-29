# 16 · Section Catalog (54 topics)

The specification's `detailed_section_catalog` has 420 entries, which are 54 topics repeated with one sentence
template ("define acceptance criteria, failure modes, data inputs, outputs, human approval requirements, tests and
documentation"). This table is that instruction carried out once per topic, against what is built.

Status: **MVP** built and tested; **Partial** part of the topic is built, the rest is listed; **Phase 2** deferred
on purpose (see [`03-mvp-scope.md`](03-mvp-scope.md)). Tests are in `backend/tests` (T) and `frontend/e2e` (E2E).

## Research Lab (27 topics)

| Topic | Status | Inputs to outputs | Acceptance criteria | Failure modes handled | Human approval | Tests |
|---|---|---|---|---|---|---|
| research_problem | MVP | Business question, decision, context to problem framing (study type, decision statement, problem) | Lake Toba question yields a pricing and concept study with a decision statement | Vague question: parser notes gaps; missing price: no price module | Design package adoption | T research flow, agents |
| research_objective | MVP | Framing to objectives and decision criteria | 3 or more objectives tied to the decision | Objectives without a decision are flagged by Research QA | Adoption | T agents |
| research_questions | MVP | Objectives to research questions RQ1..n | Each objective covered by a question | Duplicates removed | Adoption; editable | T research flow |
| hypotheses | MVP | Constructs and questions to H1..n with IV, DV, mediator, moderator, direction | Hypotheses reference measured variables; verdicts need evidence | Verdict without evidence rejected; causal wording flagged | Verdicts: agents propose, people approve; editing locked after approval | T research flow, E2E |
| constructs | MVP | Curated library (14 constructs, EN and ID items, citations) | Every questionnaire item maps to a construct with a source | Unknown construct codes rejected | Adoption | T research flow |
| variables | MVP | Questionnaire to variable dictionary (type, role, scale, construct) | Names match questionnaire codes and uploaded columns | Name mismatches surface as unmapped columns | Adoption; editable via API | T research flow |
| measurement | MVP | Items to scales; reliability (alpha, item-total) | Alpha and item diagnostics per construct; construct scores as a new version | Low alpha warned; reverse-coded items noted | Scores computed by a person or the analysis workflow | T analytics |
| sampling | MVP | Population, margin, confidence to sample size, quotas, frame | Sizes match closed-form formulas with finite population correction | Unrealistic inputs rejected; small subgroups warned | Adoption | T analytics (formulas), E2E calculator |
| survey_logic | Partial | Screening and termination rules in the questionnaire | Terminate rules exported to XLSForm | Invalid option values rejected | Questionnaire approval after pilot | T exports. Branching editor: Phase 2 |
| fieldwork | MVP | Sampling plan to channels, timeline, quality control rules | Plan lists channels, weeks and QC rules | Missing attention check flagged by QA | Adoption | T agents |
| data_import | MVP | CSV, TSV, XLSX to dataset version 1 with profiling | Types inferred; 25 MB, 100,000 rows, 500 columns limits | Wrong type, oversize, bad encoding, semicolons handled or rejected with a message | None (upload is the person's act) | T research flow |
| data_quality | MVP | Version to issues with severity (attention, speeders, straight-lining, duplicates, out of range, outliers, missing, personal data, price logic) | Planted issues in the sample are all found | False positives reduced (rating-name rules, battery-level checks, pseudonymized columns skipped) | Issues are advisory | T analytics |
| cleaning | MVP | Issues to a cleaning plan to version n+1 with operations log and checksum | New version keeps parent link; earlier versions restorable | Unknown operations rejected; out-of-range values set to missing, not guessed | Cleaning plan approval | T analytics, research flow, agents |
| eda | MVP | Variables to descriptives, frequencies, cross-tabs, correlations | Values equal numpy, scipy and statsmodels results | Small expected counts switch to Fisher's exact; multiple testing adjusted (Holm) | None | T analytics |
| regression | MVP | DV and predictors to OLS or logistic with checks | Coefficients equal statsmodels; robust errors when checks fail | Multicollinearity, heteroscedasticity, non-normal residuals, separation reported | None | T analytics |
| mediation | MVP | X, M, Y to PROCESS Model 4 with bootstrap CI | Indirect effect CI from seeded bootstrap; reproducible | Too few cases or constant variables rejected | None | T analytics |
| moderation | MVP | X, W, Y to PROCESS Model 1 with simple slopes and Johnson-Neyman | Interaction equals statsmodels | Centering option; collinearity noted | None | T analytics |
| pls_sem | Phase 2 | Measurement and structural model to path weights, bootstrap, HTMT | Match SmartPLS on a reference dataset | Planned | Planned | Planned |
| segmentation | MVP | Variables plus objective and rationale to k-means segments, stability, profiles, personas | Objective and rationale required; stability (ARI) reported | Too few cases per segment; unstable solutions warned | Segment insights need approval | T analytics |
| text_analytics | MVP | Open text to themes, keywords, examples (EN and ID) | Themes with prevalence and verbatim examples | Short or empty texts skipped; stopwords in both languages | Theme insights need approval | T analytics |
| sentiment | MVP | Text to bilingual lexicon sentiment with negation and intensifiers | Validated on labeled sentences; agreement with star ratings reported | Negation, contrast words, Indonesian post-intensifiers handled | None | T analytics, journey |
| interview_coding | Partial | Interview guide generated; transcripts can be analyzed as text (themes, sentiment) | Guide lists 8 to 12 questions linked to hypotheses | Not a substitute for manual coding (stated) | Adoption | T agents. Codebook-based coding: Phase 2 |
| conjoint | Phase 2 | Attributes and levels to choice design and part-worths | Planned | Planned | Planned | Planned |
| price_sensitivity | MVP | Price questions to Van Westendorp, Gabor-Granger, WTP at a price, by group | Acceptable range, optimal price, revenue index, elasticities | Inconsistent price answers flagged; hypothetical bias noted | Price insights need approval | T analytics |
| insights | MVP | Evidence to insights with implication, confidence, uncertainty | Must cite evidence; causal wording blocked without an experiment | Model-drafted wording labeled; numbers grounded | Approval required | T research flow, agents, E2E |
| evidence | MVP | Analyses, experiments, external sources to evidence records E1..n with origin, design, strength | Evidence values equal analysis values; lineage graph complete | Evidence in use cannot be deleted | Saving evidence is a person's or agent's act, logged | T research flow, E2E |
| reports | MVP | Evidence and insights to research report, executive summary, decision memo, methods appendix, experiment brief; Markdown and HTML | Every statement cites evidence; drafts and model text labeled | Synthetic data banner; escaped HTML | Finalize locks the report | T research flow |

## Strategy Simulator (8 topics)

| Topic | Status | Inputs to outputs | Acceptance criteria | Failure modes handled | Human approval | Tests |
|---|---|---|---|---|---|---|
| strategy_market | MVP | Research evidence and labeled assumptions to a market model | Every number has a source and confidence; placeholders flagged | Invalid shares, negative budgets rejected by the schema | Model edits by people; decisions approved | T strategy |
| strategy_segment | MVP | Segment shares, WTP multipliers, affinities to per-segment customers and CLV | Shares sum to 100%; WTP from research by group | Share lever renormalizes other segments | Decision log | T strategy |
| strategy_positioning | MVP | Offer and competitor attributes to a positioning map | Research scores used when available | Missing attributes omitted, not invented | None | E2E |
| strategy_pricing | MVP | Price response curve to price levers, price curve, break-even price | Optimum searched inside the tested price range | Extrapolation labeled; profit-max above acceptable range warned | Decision log | T strategy |
| strategy_media | MVP | Channel budgets, CPM, rates to reach and customers; greedy optimizer | Budget-neutral reallocation; saturation curves | Zero budgets and commissions handled | Optimized mix saved as a scenario, then decided | T strategy |
| strategy_channel | MVP | Channel funnel rates and commissions (for example online travel agents) | Per-channel CAC and ROMI | Commission above 100% rejected | Decision log | T strategy |
| strategy_forecast | Partial | Assumption uncertainty to Monte Carlo ranges (P10, P50, P90) and probability of profit | Seeded, reproducible simulation | Ranges follow confidence levels | None | T strategy. Time-series forecasting: Phase 2 |
| strategy_scenarios | MVP | Levers to scenarios with comparison, waterfall, sensitivity | The four Graph1 what-ifs run on the demo | Unknown lever types and keys rejected | Decisions need approval | T strategy, E2E |

## Journey Designer (9 topics)

The generic template's stages are Awareness, Discovery, Consideration, Comparison, Purchase, Onboarding, Usage,
Support, Advocacy and Retention; the tourism template (Graph1) uses Discover, Search, Compare, Book, Arrive,
Experience, Share, Return and Recommend. Every stage topic below shares the same machinery.

| Topic | Status | Inputs to outputs | Acceptance criteria | Failure modes handled | Human approval | Tests |
|---|---|---|---|---|---|---|
| journey_awareness | MVP | Stage in both templates: touchpoints, continue rate, emotion, pain points | Reviews mapped by bilingual keywords; emotion and friction shown | Unmapped texts reported as coverage | Journey adoption | T journey |
| journey_discovery | MVP | As above (Search in tourism) | Missing information detected as a pain point | As above | As above | T journey, E2E |
| journey_consideration | MVP | As above (Compare) | Comparative sentiment captured | As above | As above | T journey |
| journey_purchase | MVP | As above (Book); step-reduction interventions | Five-to-two booking steps simulated with low, mid, high cases | Step counts validated | Intervention status by people | T journey |
| journey_usage | MVP | As above (Arrive, Experience); satisfaction interventions | Storytelling redesign simulated | Uplift ranges must be ordered | As above | T journey |
| journey_support | MVP | Outcome stage (generic) | Outcome rates editable | Rates bounded 0 to 100% | As above | T journey |
| journey_advocacy | MVP | Share and Recommend outcomes feed word of mouth | Referral effect in the simulation | Word-of-mouth parameters labeled as assumptions | As above | T journey |
| journey_retention | MVP | Return outcome; repeat revenue | Returners and repeat revenue shown | As above | As above | T journey |
| experiments | MVP | Intervention to A/B test (hypothesis, metric, sample size, duration) to results to experimental evidence | Two-proportion test; result becomes evidence that permits causal wording | Underpowered tests warned; tests over 90 days flagged; conversions above visitors rejected | Launch approval | T journey, E2E |

## Platform (10 topics)

| Topic | Status | What exists | Acceptance criteria | Tests |
|---|---|---|---|---|
| security | MVP | Argon2id, JWT, tenancy helpers, roles, rate limits, upload limits, security headers, allowed hosts, prompt-injection guards | See [`12-security-threat-model.md`](12-security-threat-model.md) | T auth and tenancy |
| privacy | MVP | Personal data detection, pseudonymization, desktop mode, synthetic data labels, project deletion removes files | Personal data flagged as high severity | T analytics |
| observability | Partial | Health check, audit log, workflow and agent run logs, model call metadata | See [`14-observability.md`](14-observability.md) | T agents |
| ux | MVP | Three modules, next-step guidance, approvals inbox, light and dark themes | See [`09-design-system.md`](09-design-system.md) | E2E |
| accessibility | MVP | Keyboard access, table view for every chart, status with icon and text, contrast | No information only in color or hover | E2E, manual review |
| integrations | Partial | CSV/XLSX in, XLSForm, Markdown, HTML, CSV out; Claude API | Exports open in KoboToolbox and spreadsheet tools | T exports. API connectors: Phase 2 |
| billing | Phase 2 | Pricing hypotheses only | See [`15-pricing-gtm-hypotheses.md`](15-pricing-gtm-hypotheses.md) | Planned |
| deployment | MVP | Desktop executable, Docker image, docker-compose, migrations | See [`13-deployment.md`](13-deployment.md) | CI Docker smoke test, desktop build smoke test |
| testing | MVP | 61 backend tests (SQLite and PostgreSQL), frontend unit tests, 9 E2E tests, CI | See [`11-test-strategy.md`](11-test-strategy.md) | CI |
| documentation | MVP | README, docs 00 to 17, AGENTS.md, CLAUDE.md, CHANGELOG | Every module and decision documented | Review |
