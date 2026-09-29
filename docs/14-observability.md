# 14. Observability plan

Goal: know when MDOS is down or slow, why an agent or analysis failed, what the model did and cost, and whether
people get value from the product.

## 1. What exists today

| Signal | Where | Contents |
|---|---|---|
| Health check | `GET /api/health` | Status, version, mode; used by the Docker health check and the desktop launcher |
| Server logs | stdout (uvicorn and the `mdos` loggers) | Requests, warnings, agent failures with stack traces (`mdos.supervisor`) |
| Audit log | `audit_log` table, Settings page, `GET /projects/{id}/audit` | Every mutation by people and agents: who, what, which entity, details |
| Workflow runs | `workflow_runs` table, Agents page | Status per step, errors, retries, rollbacks, approval waits |
| Agent runs | `agent_runs` table, run log and run modal | The 10-field output contract, provider, model, attempt, start and finish times |
| Model calls | `agent_runs.result.llm_calls` | Latency, stop reason, served model (shows server-side fallbacks), input and output tokens, request ID, schema, error |
| Analyses | `analyses` table | Method, parameters, data version, assumption checks, warnings, errors |
| Approvals | `approvals` table, Approvals page | Requested and decided times, decision, rationale |

## 2. Next steps (in order)

1. **Structured JSON logs with a request ID** (middleware that sets `X-Request-ID` and logs method, path, status,
   duration, user and project IDs; never request bodies or dataset contents).
2. **Error tracking** (Sentry or the platform's error reporting) for unhandled exceptions in the API and the browser,
   with personal data scrubbing on.
3. **Metrics** (Prometheus format or the platform's metrics):
   * HTTP request rate, error rate and p50/p95 latency by route group.
   * Workflow runs started, succeeded, failed and awaiting approval; step duration by agent.
   * Model calls: count, errors by class (refusal, truncation, timeout, API error), tokens in and out, latency,
     fallback rate (served model differs from the configured one).
   * Analyses by method and failure rate; upload sizes and rejection reasons.
4. **Tracing** (OpenTelemetry) around workflows: one trace per workflow run with a span per agent and per tool call.
5. **Dashboards and alerts**: availability below 99.5% over an hour, error rate above 2%, p95 latency above 2 seconds
   (excluding agent runs), any workflow stuck in "running" for more than 15 minutes, model error rate above 10%.

## 3. Product and quality metrics

From the specification's evaluation section, computed from the tables above (a weekly SQL report first, a dashboard
later):

| Metric | Definition |
|---|---|
| Time to research design | Project created to design package adopted |
| Time to first evidence | Dataset uploaded to first evidence record |
| Evidence coverage | Share of insights and recommendations citing at least two evidence records |
| Approval rate and latency | Approved share and median time from request to decision, by gate |
| Gate interventions | Causal-language and evidence gate rejections per 100 insight attempts |
| Model edit rate | Share of model-drafted insights a person edited before approving |
| Loop completion | Projects that reach an experiment result recorded as evidence |
| Weekly active projects | Projects with at least one mutation in the week |

## 4. Privacy rules for telemetry

* Never log dataset rows, open-text answers, prompts or model outputs to external services.
* Aggregate product metrics per organization; no cross-organization data leaves the database.
* The desktop build sends no telemetry.
