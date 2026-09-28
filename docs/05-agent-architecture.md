# 05 · Agent Architecture and Responsibility Matrix

## 1. Principles

1. **Supervisor plus specialists.** A supervisor runs a bounded workflow; specialists do scoped tasks.
2. **Agents propose, people approve.** Agent output lands in a run record as a proposal. Applying it is a separate,
   audited action with rollback.
3. **Numbers come from code.** Agents call deterministic engines through tools. An LLM may draft wording, never
   statistics.
4. **Offline first.** Every agent has a deterministic implementation. When Claude is configured, generative steps use
   it and are validated against the same schema; any failure falls back to the deterministic path and is recorded as
   an uncertainty.
5. **Structured output.** Every agent returns the output contract below. No free-form blobs.

## 2. Output contract

Every agent step returns exactly these fields (spec `agent_orchestration.agent_output_contract`):

| Field | Type | Meaning |
|---|---|---|
| `task_id` | string | Unique ID of this step |
| `status` | enum | `succeeded`, `failed`, `awaiting_approval`, `skipped` |
| `inputs_used` | list | Named inputs the agent read (for example `project.business_question`, `dataset_version:3`) |
| `actions_taken` | list of strings | Human-readable steps performed |
| `tools_used` | list of strings | Tool names invoked (all must be on the agent's allowlist) |
| `evidence` | list | Evidence codes or analysis IDs the output relies on |
| `assumptions` | list of strings | Assumptions made while producing the output |
| `uncertainties` | list of strings | Known gaps, low-confidence parts, fallbacks |
| `outputs` | object | The payload, validated by an agent-specific schema |
| `recommended_next_step` | string | What the person or the supervisor should do next |

## 3. Workflows (supervised pipelines)

| Workflow | Steps (in order) | Approval gate |
|---|---|---|
| `research_design` (Graph1 Phase 1, first half) | problem_framing, research_design, questionnaire, sampling, fieldwork, research_qa | Adopt the design package (creates research questions, hypotheses, constructs, variables, questionnaire, plans) |
| `research_analysis` (Graph1 Phase 1, second half) | data_quality, data_cleaning, statistical_analysis, price_sensitivity, segmentation, text_analytics, insight, research_qa, report | Approve the cleaning plan before analysis; insights, verdicts and the report stay drafts until approved |
| `strategy_baseline` | market_model, pricing, media_allocation, scenario, strategy_narrative | Adopt the baseline scenario; decisions require approval |
| `journey_voc` | voice_of_customer, journey_mapping, pain_point, experience_opportunity, journey_simulation, experiment_design | Adopt the journey proposal; experiments require launch approval |

Run statuses: `queued`, `running`, `awaiting_approval`, `succeeded`, `failed`, `cancelled`, `skipped`.
Failed steps can be retried; paused workflows resume from the paused step.

## 4. Responsibility matrix

### 4.1 Executable MVP agents (26)

| Key | Module | Responsibility | Tools allowed | Human gate | Covers spec agents |
|---|---|---|---|---|---|
| `research_director` | Research | Supervises research workflows, decides next step, summarizes state | `project.read`, `workflow.control` | n/a | Research Director |
| `problem_framing` | Research | Business question to decision statement, research problem, objectives, study type, key unknowns | `project.read`, `llm.generate` | Part of design adoption | Problem Framing |
| `research_design` | Research | Research questions, hypotheses, conceptual framework, constructs and variables, method choice, design caveats | `project.read`, `construct_library.search`, `llm.generate` | Design adoption | Research Design, Hypothesis, Measurement, Literature Discovery (construct citations only) |
| `questionnaire` | Research | Screening, construct items (EN and ID), price module (Van Westendorp, Gabor-Granger, target price), behavior, demographics, open-ended items, interview guide | `construct_library.search`, `llm.generate` | Design adoption | Questionnaire, Interview Guide |
| `sampling` | Research | Population, frame, method, sample size with margin of error, quotas | `project.read`, `calc.sample_size` | Design adoption | Sampling |
| `fieldwork` | Research | Channels, timeline, quality-control rules, consent text, XLSForm handoff | `project.read`, `llm.generate` | Design adoption | Fieldwork |
| `data_quality` | Research | Profiles a dataset: missing, duplicates, straight-lining, speeders, ranges, outliers, PII, price-answer consistency | `dataset.read`, `dataset.profile` | n/a | Data Import, Data Quality |
| `data_cleaning` | Research | Proposes a cleaning plan from diagnostics | `dataset.read`, `cleaning.propose` | **Approve cleaning plan** | Data Cleaning |
| `statistical_analysis` | Research | Plans analyses from hypotheses and variable roles, runs descriptive, reliability, correlation, cross-tabs, regression and PROCESS, creates evidence | `dataset.read`, `analysis.run`, `evidence.create` | n/a (evidence is factual) | Statistical Analysis, EDA, Regression |
| `price_sensitivity` | Research | Van Westendorp, Gabor-Granger, WTP at target price by segment | `dataset.read`, `analysis.run`, `evidence.create` | n/a | Price Sensitivity |
| `segmentation` | Research | k-means with stated objective and rationale, profiles, personas | `dataset.read`, `analysis.run`, `evidence.create`, `llm.generate` | n/a | Segmentation (persona synthesis included) |
| `text_analytics` | Research | Keywords, themes, sentiment, representative quotes from open-ended text | `dataset.read`, `analysis.run`, `evidence.create`, `llm.generate` | n/a | Text Analytics, Sentiment, Thematic Analysis |
| `insight` | Research | Drafts insights linked to evidence, proposes hypothesis verdicts, links evidence to claims | `evidence.read`, `insight.propose`, `llm.generate` | **Approve insights and verdicts** | Insight, Evidence |
| `research_qa` | Research | Checks quality gates: assumptions, causal language, evidence coverage, sample adequacy, hypothetical bias | `project.read`, `evidence.read` | n/a | Research QA |
| `report` | Research | Composes the research report with citations, methods and data appendices | `project.read`, `evidence.read`, `report.compose`, `llm.generate` | **Finalize report** | Report |
| `market_model` | Strategy | Builds the baseline market model from project data and research evidence (segments, price response, channels, competitors, positioning) | `project.read`, `evidence.read`, `scenario.propose` | **Adopt baseline** | Market Model, Competitor, Segmentation Strategy, Positioning |
| `pricing` | Strategy | Price curve, revenue- and profit-maximizing price, acceptable range from Van Westendorp | `scenario.simulate` | n/a | Pricing |
| `media_allocation` | Strategy | Budget reallocation scenarios and greedy marginal-return allocation | `scenario.simulate` | n/a | Media Allocation, Channel Strategy, Optimization (greedy) |
| `scenario` | Strategy | Graph1 what-if scenarios, comparison, tornado sensitivity, Monte Carlo ranges | `scenario.simulate`, `scenario.propose` | n/a | Scenario, Forecast, Sensitivity |
| `strategy_narrative` | Strategy | Explains implications, cites numbers and evidence, labels model-generated text | `scenario.read`, `evidence.read`, `llm.generate` | **Decision approval** | Strategy Narrative |
| `voice_of_customer` | Journey | Needs, pain points, themes and sentiment from reviews and comments; stage mapping | `dataset.read`, `voc.analyze`, `llm.generate` | n/a | Voice of Customer |
| `journey_mapping` | Journey | Builds the journey from a template plus VOC (touchpoints, emotions, conversion) | `journey.read`, `journey.propose` | **Adopt journey** | Journey Mapping |
| `pain_point` | Journey | Prioritizes pain points; emotion curve; friction heatmap | `journey.read`, `journey.propose` | Part of journey adoption | Pain Point, Emotion Mapping |
| `experience_opportunity` | Journey | Interventions for top pain points, including storytelling concepts and conversion fixes | `journey.read`, `journey.propose`, `llm.generate` | Part of journey adoption | UX Opportunity, Storytelling, Conversion Optimization |
| `journey_simulation` | Journey | Before and after simulation of interventions with ranges | `journey.simulate` | n/a | Journey Simulation |
| `experiment_design` | Journey | Experiment briefs with hypothesis, metric, sample size, duration | `experiment.propose`, `calc.sample_size` | **Launch approval** | Experiment Design, Experimental Design |

### 4.2 Deferred spec agents

| Spec agent | Phase | Reason |
|---|---|---|
| PLS-SEM Agent | 2 | Needs the PLS-SEM engine (Phase 2); construct and indicator model already exists |
| Conjoint Agent | 2 | Needs experimental design generation and hierarchical Bayes or MNL estimation |
| Presentation Agent | 2 | PPTX generation; MVP ships HTML and Markdown reports |
| Literature Discovery Agent (full) | 2 | Needs scholarly search APIs; MVP cites sources from the curated construct library |

### 4.3 Graph1 agent names mapped to implementations

| Graph1 name | Implemented by |
|---|---|
| Research Agent | `research_director`, `problem_framing`, `research_design` |
| Questionnaire Agent, Survey Agent | `questionnaire` |
| Sampling Agent | `sampling` |
| Fieldwork Agent | `fieldwork` |
| Data Agent, Data Cleaning Agent | `data_quality`, `data_cleaning` |
| Statistical Agent, Stats Agent | `statistical_analysis`, `price_sensitivity`, `segmentation`, `text_analytics` |
| Insight Agent | `insight` |
| Report Agent | `report` |
| Market Analyst Agent, Market Agent, Customer Agent, Segment Agent, Competitor Agent | `market_model` |
| Pricing Agent | `pricing` |
| Media Agent | `media_allocation` |
| Forecast Agent | `scenario` |
| Strategy Agent | `strategy_narrative` |
| Voice-of-Customer Agent, VOC Agent | `voice_of_customer` |
| Journey Agent | `journey_mapping` |
| Emotion Agent | `pain_point` |
| Storytelling Agent, Story Agent, UX Agent, Conversion Agent | `experience_opportunity` |
| Simulation Agent | `journey_simulation` |
| Experiment Agent | `experiment_design` |

## 5. LLM usage policy

| Allowed | Not allowed |
|---|---|
| Drafting objectives, research questions and hypothesis wording | Computing or estimating any statistic |
| Adapting questionnaire wording from library constructs | Inventing data, respondents or quotes |
| Interview guides, fieldwork plans, consent text | Marking a hypothesis supported |
| Narratives around numbers that the engine supplied | Approving, applying or deleting anything |
| Classifying review text into journey stages and naming themes | Calling tools (the model returns JSON only) |

**Numeric grounding check:** every number in LLM-written narrative must match a number in the evidence supplied to
the prompt (allowing formatting differences). Unmatched numbers are listed as uncertainties, and narratives with
unmatched numbers fall back to the deterministic template.

## 6. Prompt-injection defenses

* Uploaded text is wrapped in `<untrusted_data>` delimiters; the system prompt instructs the model to treat it as data
  and ignore instructions inside it.
* Control characters are stripped and inputs are truncated to a budget.
* The model has **no tools**: it can only return JSON, which is validated against a schema before use.
* The worst case of a successful injection is a bad draft, which a person reviews before anything is applied.

## 7. Failure, retry and rollback

* A step that raises is recorded as `failed` with the error; the workflow stops; the person can retry the step or
  cancel the workflow.
* LLM errors (timeouts, rate limits, invalid JSON) trigger the deterministic fallback inside the step, so they do not
  fail the workflow.
* Applying a proposal tags every created entity with the run ID. Rollback deletes those entities unless they were
  approved or edited afterwards, and writes an audit entry.
* Cleaning plan rollback marks the derived dataset version as superseded and restores the parent as current.
