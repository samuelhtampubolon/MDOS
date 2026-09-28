# 01 · Pre-Build Interview (12 Questions)

The specification requires 12 questions before coding. The founder vision notes (Graph1) already answer most of
them. Each answer below states its source and confidence. **Rows marked "Confirm" are defaults chosen so the build
could proceed; please confirm or correct them.** All of them are reversible.

Line references such as `G:30` point to [`source/graph1-founder-vision.txt`](source/graph1-founder-vision.txt).

| ID | Topic | Question | Answer used for this build | Source | Confidence | Status |
|---|---|---|---|---|---|---|
| Q01 | Target customer | Who is the first paying customer segment? | **Indonesian university researchers and independent marketing research consultants** (lecturers, postgraduate researchers, small agencies). They already pay for SPSS, SmartPLS and survey tools, the Research Lab serves them directly, and consultants carry the product into SMEs and tourism organizations. Tourism organizations are the showcase and the second segment. | G:30, G:3, G:166 plus judgment | Medium | Confirm |
| Q02 | Geography | Which countries or regions first? | **Indonesia first**, then Southeast Asia and other emerging markets. Rupiah is the default currency; any ISO currency can be set per project. UI is English in v1; instruments and text analytics are bilingual (EN and ID). | G:30, G:5, G:59 | High (Indonesia) | Answered |
| Q03 | Research type | Which workflows matter most at launch? | **Survey-first mixed methods**: quantitative surveys plus qualitative text (open-ended answers, reviews, interview transcripts through text analytics). Experiments enter through the closed loop. | G:7 to G:28 | High | Answered |
| Q04 | Data | Which data sources in v1? | **CSV and XLSX files**: survey exports (Google Forms, KoboToolbox, ODK, Qualtrics, SurveyMonkey), reviews and social comments with a text column, and manual market inputs for the simulator. API connectors are Phase 2. | G:112 to G:120 | High | Answered |
| Q05 | Analytics depth | How advanced at launch? | **MVP:** descriptive statistics, cross-tabs with chi-square, correlation, OLS and logistic regression with assumption checks, Cronbach's alpha, PROCESS Model 4 (mediation) and Model 1 (moderation), Van Westendorp, Gabor-Granger, WTP at a target price, k-means segmentation with personas, text analytics, bilingual sentiment. **Phase 2:** PLS-SEM, choice-based conjoint, MaxDiff, EFA and CFA, forecasting, latent class segmentation. | Spec `analytics`, G:16 to G:28 | Medium-high | Answered |
| Q06 | Strategy | Which decisions does the simulator model first? | **Pricing, media and channel allocation, segment mix, competitor shocks**: exactly the four Graph1 what-if questions. Break-even, CLV and sensitivity come with them. | G:59 to G:62 | High | Answered |
| Q07 | Experience | Which journey is the showcase? | **Tourism: a Lake Toba cultural experience** with stages Discover, Search, Compare, Book, Arrive, Experience, Share, Return, Recommend. Showcase interventions: booking friction from 5 steps to 2, and a storytelling-led first 15 minutes. | G:92 to G:142 | High | Answered |
| Q08 | Integration | Which external systems first? | **File-based in v1**: CSV/XLSX import; XLSForm export (KoboToolbox, ODK, SurveyCTO); Markdown and HTML reports; optional Anthropic Claude API for generative steps. **Proposed first API integrations (Phase 2):** Google Sheets and Forms, KoboToolbox, Google Business Profile reviews, Instagram and TikTok insights, GA4. | Assumption | Low | Confirm |
| Q09 | Business model | Which monetization model is tested first? | **Free tier plus Professional subscription plus University plan**, with usage-based AI credits for LLM-heavy steps and a desktop licence for the local executable. Price points are hypotheses to be tested with the product's own Van Westendorp module ([`15-pricing-gtm-hypotheses.md`](15-pricing-gtm-hypotheses.md)). | Spec `business_model` plus assumption | Low | Confirm |
| Q10 | Deployment | Cloud SaaS, local application, or hybrid? | **Hybrid from one codebase**: cloud web app (Docker, PostgreSQL) and a local desktop executable (SQLite, offline, runs on `127.0.0.1`). | G:6 | High | Answered |
| Q11 | Brand | Name, visual identity, tone, references? | **Working name "Marketing Decision OS (MDOS)"**. Tone: rigorous, calm, evidence-first. Visual: research-grade, information-dense but uncluttered, accessible, light and dark themes, deep lake-blue primary with a warm accent. | Assumption | Low | Confirm |
| Q12 | Success | What measurable outcome makes v1 a success? | **Proposed:** (1) a researcher goes from business question to an evidence-cited report in under one working day; (2) at least 70% of AI-drafted insights are accepted after human review; (3) zero statistically incorrect results in the validation suite; (4) five pilot users (for example three researchers and two tourism businesses) complete a real project and two convert to paid. | Spec `evaluation` plus assumption | Low | Confirm |

## Summary of the answers

The first release is a **hybrid web and desktop research decision engine for Indonesian researchers, consultants and
tourism businesses**. It is survey-first with qualitative text, file-based for data, deep in interpretable statistics
and price research, and it carries evidence forward into a transparent market simulator and a tourism journey model
whose interventions become experiments.

## What changes if a "Confirm" answer is different

| If you answer... | ...then the build changes like this |
|---|---|
| Q01: SMEs or tourism operators are the first paying segment | Simplify the Research Lab UI (hide PLS-SEM and methods detail by default), put the Strategy Simulator on the home screen, and add template projects by industry. |
| Q08: a specific integration is mandatory (for example Google Forms) | Add a connector module; data model and lineage already support external sources. |
| Q09: one-time desktop licence first | Add licence-key verification to the desktop launcher; cloud billing stays deferred. |
| Q11: a real brand and palette | Replace tokens in `frontend/src/styles/tokens.css`; components use tokens only. |
| Q12: different success metric | Update `docs/14-observability.md` product events so the metric is measured from day one. |
