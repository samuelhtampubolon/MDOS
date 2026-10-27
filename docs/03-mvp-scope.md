# 03. MVP scope and deferred scope

## Scope principle

Build **Phase 1 (Research Lab) completely** and build **thin, working slices of the Strategy Simulator and the Journey
Designer** that consume research evidence. This follows the specification's MVP roadmap and Graph1's phasing at the
same time, and it makes the closed loop (research to strategy to journey to experiment and back to research)
demonstrable from the first release.

## MVP: in scope

### Module 1: Marketing Research Lab (target at least 42% of scope)

| Area | MVP capability | Acceptance test (abbreviated) |
|---|---|---|
| Workspace | Projects with business question, decision to inform, context, currency | Create project from a business question; appears on Home |
| Research Director pipeline | Problem framing, research design, questionnaire, sampling and fieldwork agents run as one supervised workflow | The Lake Toba question produces objectives, research questions, hypotheses, constructs, a questionnaire with a price module, a sampling plan and a fieldwork plan |
| Human approval | AI output is a proposal until a person adopts it; adoption can be rolled back | Adopting creates entities tagged with the run; rollback removes them |
| Construct library | Curated marketing constructs with definitions, adapted EN and ID items and source citations | Library returns constructs; questionnaire items reference them |
| Hypothesis canvas and variable dictionary | Research questions, hypotheses (IV, DV, mediator, moderator), constructs, variables with roles and scales | Edit and save; verdicts require evidence and approval |
| Questionnaire builder | Sections, question types (single, multi, Likert, numeric, text, price), screening logic | Export to XLSForm, Markdown and codebook CSV |
| Sampling calculator | Sample size for proportions and means with finite population correction; A/B test sample size | Values match closed-form formulas |
| Data import | CSV and XLSX upload, type inference, preview, column-to-variable mapping | Upload the sample survey; 300 rows and all columns inferred |
| Data quality | Missing data, duplicates, straight-lining, speeders, out-of-range values, outliers, PII columns, inconsistent price answers | Diagnostics flag the planted issues in the sample data |
| Cleaning and lineage | Proposed cleaning plan, approval, new dataset version with recorded operations and checksum | Version 2 exists with parent link and operations log |
| Analysis studio | Descriptive, cross-tab and chi-square, correlation, OLS and logistic regression, reliability, PROCESS 1 and 4, Van Westendorp, Gabor-Granger, WTP at target price, k-means segmentation with personas, text analytics and sentiment | Each method validated against library or hand-computed results; each result shows method, n, assumptions and limitations |
| Evidence | Evidence records (E1, E2 and so on) created from analyses, quotes, experiments or external sources, with data origin labels | Evidence values equal the analysis values |
| Insights and recommendations | Insight drafts linked to evidence, confidence and uncertainty, approval workflow; recommendations must cite evidence | A recommendation without evidence is rejected; causal language on survey-only evidence is rejected |
| Evidence graph | Sources to datasets to analyses to evidence to insights to recommendations to decisions | Graph returns nodes and edges for the demo project |
| Research QA | Checks quality gates: assumptions, causal language, evidence coverage, sample adequacy, hypothetical bias | QA flags hypothetical bias for stated WTP |
| Reports | Research report, executive summary, decision memo, methods appendix, data appendix; Markdown and HTML export | Report cites evidence codes and labels model-generated text |

### Module 2: Marketing Strategy Simulator (target about 31%)

| Area | MVP capability |
|---|---|
| Market model canvas | Market, segments (share, price response, channel affinity), competitors, offer (price, unit cost, fixed cost), channels (budget, CPM, audience, engagement, lead, conversion rates) |
| Simulation | Budget to Reach to Engagement to Leads to Conversion to Revenue to Profit, per channel and per segment |
| Evidence-backed assumptions | Each assumption has a source (evidence, benchmark, expert judgment, guess) and a confidence; the price response can be imported from Gabor-Granger or Van Westendorp evidence |
| Scenarios | Price change, budget reallocation between channels, segment-mix shift, competitor price shock; comparison against baseline |
| Analytics | Break-even, CLV, CAC, ROMI, revenue and profit waterfall, tornado sensitivity, Monte Carlo ranges (P10, P50, P90), price curve, greedy media optimizer |
| Positioning map | Competitors on two chosen attributes |
| Decision log | Decisions linked to scenarios and evidence, with approval |

### Module 3: Customer Journey and Experience Designer (target about 27%)

| Area | MVP capability |
|---|---|
| Journey canvas | Stage templates (Tourism from Graph1, Generic from the spec), touchpoints, emotions, pain points, stage conversion |
| Voice of customer | Import reviews or comments, map them to stages (bilingual keywords), sentiment, themes, representative quotes |
| Emotion map and friction heatmap | Mean sentiment by stage, stage by theme negativity matrix |
| Pain-point prioritization | Frequency, severity and reach scoring, editable |
| Opportunity backlog | Interventions linked to pain points with expected uplift range, effort and confidence |
| Journey simulation | Before and after funnel for step reduction, conversion uplift and satisfaction-to-referral effects |
| Experiments | Experiment brief from an intervention, sample size, launch approval, results analysis (two-proportion test) that becomes research evidence |

### Shared platform

* Organizations, users, project membership roles (owner, editor, viewer), tenant isolation.
* Local mode (desktop, single user, no password) and cloud mode (email and password, JWT).
* Audit log of all mutations; approvals inbox; agent run log with the 10-field output contract.
* Optional Claude integration for generative steps, deterministic offline mode otherwise.
* Rate limiting on authentication and agent endpoints; upload limits; CSV formula-injection protection on export.
* Docker deployment and a desktop executable build.

## Deferred scope

### Phase 2 (after MVP validation)

* PLS-SEM (path weighting, bootstrapping, HTMT, Fornell-Larcker), choice-based conjoint, MaxDiff, EFA and CFA,
  forecasting, latent class segmentation, experiment analysis for continuous metrics.
* Native survey hosting (public survey links, quotas, live fieldwork tracker).
* Scenario optimization beyond the greedy allocator; media mix calibration from historical data; logit choice model.
* Journey simulation with feedback loops over time; multiple personas per journey.
* External integrations: Google Sheets and Forms, KoboToolbox, Google Business Profile, Instagram, TikTok, GA4.
* Background job queue (Redis and worker), object storage for files, SSO.
* Slide deck export (PPTX), DOCX report export.
* Full Bahasa Indonesia UI.

### Phase 3

* Agentic recurring research and continuous market monitoring, automated insight feeds.
* Cross-project learning (benchmarks from anonymized, consented projects).
* Enterprise controls (SCIM, data residency, custom retention), marketplace, partner ecosystem.

## Explicitly out of scope

* Generating campaign content at scale ("AI writes 50 Facebook posts"). Graph1 rules this out on purpose.
* Autonomous decisions without human approval.
* Presenting AI-generated numbers as data.
