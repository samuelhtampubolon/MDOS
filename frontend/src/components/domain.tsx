/* Domain components shared by pages: workflows, agent runs, evidence, approvals. */

import { useState } from "react";
import { api, errorMessage } from "../api/client";
import { useApi, useProjectMutation, useWorkflow } from "../api/hooks";
import type { AgentRun, Approval, Evidence, WorkflowRun } from "../api/types";
import { dateTime, num, pValue, sentence } from "../lib/format";
import { Badge, Callout, ChecksList, Icon, Modal, OriginBadge, StatusBadge, useToast } from "./ui";

export const WORKFLOW_LABELS: Record<string, string> = {
  research_design: "Research design",
  research_analysis: "Research analysis",
  strategy_baseline: "Strategy simulation",
  journey_voc: "Journey design",
};

export const AGENT_LABELS: Record<string, string> = {
  research_director: "Research Director", problem_framing: "Problem Framing", research_design: "Research Design",
  questionnaire: "Questionnaire", sampling: "Sampling", fieldwork: "Fieldwork", research_qa: "Research QA",
  data_quality: "Data Quality", data_cleaning: "Data Cleaning", statistical_analysis: "Statistical Analysis",
  price_sensitivity: "Price Sensitivity", segmentation: "Segmentation", text_analytics: "Text Analytics", insight: "Insight",
  report: "Report", market_model: "Market Model", pricing: "Pricing", media_allocation: "Media Allocation", scenario: "Scenario",
  strategy_narrative: "Strategy Narrative", voice_of_customer: "Voice of Customer", journey_mapping: "Journey Mapping",
  pain_point: "Pain Point", experience_opportunity: "Experience Opportunity", journey_simulation: "Journey Simulation",
  experiment_design: "Experiment Design",
};

const ACTION_LABELS: Record<string, string> = {
  adopt_design: "Adopt research design", apply_cleaning: "Apply cleaning plan", approve_insight: "Approve insight",
  approve_recommendation: "Approve recommendation", approve_verdict: "Approve hypothesis verdict", finalize_report: "Finalize report",
  approve_decision: "Approve strategy decision", launch_experiment: "Launch experiment",
};

export function AgentRunModal({ pid, runId, onClose }: { pid: string; runId: string | null; onClose: () => void }) {
  const { data: run } = useApi<AgentRun>([pid, "agent-run", runId], runId ? `/projects/${pid}/agent-runs/${runId}` : null);
  const r = run?.result;
  return (
    <Modal title={run ? `${AGENT_LABELS[run.agent] ?? run.agent} agent` : "Agent run"} open={Boolean(runId)} onClose={onClose} wide>
      {!run || !r ? (
        <span className="muted">Loading</span>
      ) : (
        <div className="stack">
          <div className="row">
            <StatusBadge status={run.status} />
            <Badge>{run.provider === "offline" ? "Offline (deterministic)" : `${run.provider} ${run.model}`}</Badge>
            <span className="small muted">Attempt {run.attempt} · {dateTime(run.finished_at ?? run.created_at)}</span>
          </div>
          {run.error && <Callout tone="critical">{run.error}</Callout>}
          <p className="small muted">Every agent returns the same ten-field output contract from the specification.</p>
          <div className="grid grid-2">
            <ContractList title="Actions taken" items={r.actions_taken} />
            <ContractList title="Inputs used" items={r.inputs_used} />
            <ContractList title="Tools used" items={r.tools_used} mono />
            <ContractList title="Evidence cited" items={r.evidence} mono />
            <ContractList title="Assumptions" items={r.assumptions} />
            <ContractList title="Uncertainties" items={r.uncertainties} tone="warning" />
          </div>
          <div>
            <div className="small" style={{ fontWeight: 600, marginBottom: 4 }}>Recommended next step</div>
            <Callout>{r.recommended_next_step || "None"}</Callout>
          </div>
          <details className="disclosure">
            <summary><Icon name="chevronDown" size={12} />Outputs (JSON) and task ID {r.task_id.slice(0, 8)}</summary>
            <pre className="pre">{JSON.stringify(r.outputs, null, 2)}</pre>
            {r.llm_calls && r.llm_calls.length > 0 && <pre className="pre">{JSON.stringify(r.llm_calls, null, 2)}</pre>}
          </details>
        </div>
      )}
    </Modal>
  );
}

function ContractList({ title, items, mono = false, tone }: { title: string; items: string[]; mono?: boolean; tone?: string }) {
  return (
    <div>
      <div className="small" style={{ fontWeight: 600, marginBottom: 4 }}>{title}</div>
      {items.length ? (
        <ul style={{ margin: 0, paddingLeft: 18 }} className="small">
          {items.map((it, i) => <li key={i} className={tone === "warning" ? "" : "secondary"}>{mono ? <code>{it}</code> : it}</li>)}
        </ul>
      ) : (
        <span className="small muted">None</span>
      )}
    </div>
  );
}

export function WorkflowPanel({ pid, runId, onOpenRun }: { pid: string; runId: string; onOpenRun: (id: string) => void }) {
  const { data: wf } = useWorkflow(pid, runId);
  const toast = useToast();
  const control = useProjectMutation(pid, (action: string) => api.post<WorkflowRun>(`/projects/${pid}/workflows/${runId}/${action}`));
  if (!wf) return null;
  const act = (action: string) => control.mutate(action, {
    onSuccess: () => toast(`Workflow ${action === "rollback" ? "rolled back" : action + "d"}.`),
    onError: (e) => toast(errorMessage(e), "error"),
  });
  return (
    <div className="stack-sm">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div className="row">
          <strong>{WORKFLOW_LABELS[wf.workflow] ?? wf.workflow}</strong>
          <StatusBadge status={wf.status} />
          <span className="small muted">{dateTime(wf.created_at)}</span>
        </div>
        <div className="actions">
          {wf.status === "failed" && <button className="btn sm" onClick={() => act("retry")}><Icon name="refresh" size={14} />Retry step</button>}
          {["queued", "running", "awaiting_approval", "failed"].includes(wf.status) && (
            <button className="btn sm ghost" onClick={() => act("cancel")}>Cancel</button>
          )}
          {["succeeded", "awaiting_approval", "failed"].includes(wf.status) && (
            <button className="btn sm ghost danger" onClick={() => window.confirm("Remove the drafts this workflow created? Approved items are kept.") && act("rollback")}>
              <Icon name="undo" size={14} />Roll back drafts
            </button>
          )}
        </div>
      </div>
      {wf.error && <Callout tone="critical">{wf.error}</Callout>}
      <details className="disclosure" open={wf.status !== "succeeded"}>
        <summary><Icon name="chevronDown" size={12} />{(wf.step_runs ?? []).length} agent steps</summary>
      <div className="timeline">
        {(wf.step_runs ?? []).map((s) => (
          <div key={s.index} className="timeline-step">
            <span className={`timeline-dot ${s.status}`}>
              {s.status === "succeeded" ? <Icon name="check" size={12} /> : s.status === "failed" ? <Icon name="x" size={12} />
                : s.status === "awaiting_approval" ? <Icon name="approvals" size={12} /> : s.status === "running" ? <span className="spinner" style={{ width: 10, height: 10 }} /> : null}
            </span>
            <div>
              <div className="row" style={{ gap: 8 }}>
                {s.agent_run_id ? (
                  <button className="btn ghost sm" style={{ padding: 0, height: "auto" }} onClick={() => onOpenRun(s.agent_run_id as string)}>
                    {AGENT_LABELS[s.agent] ?? s.agent}
                  </button>
                ) : (
                  <span style={{ fontWeight: 600, color: "var(--text-muted)" }}>{AGENT_LABELS[s.agent] ?? s.agent}</span>
                )}
                {!["pending", "skipped", "succeeded"].includes(s.status) && <StatusBadge status={s.status} />}
              </div>
              {s.summary[0] && <div className="small secondary">{s.summary[0]}</div>}
              {s.error && <div className="small" style={{ color: "var(--critical-text)" }}>{s.error}</div>}
            </div>
          </div>
        ))}
      </div>
      </details>
      {wf.package_preview && (
        <details className="disclosure" open={wf.status === "awaiting_approval"}>
          <summary><Icon name="chevronDown" size={12} />Design package preview</summary>
          <div className="grid grid-2">
            <div>
              <div className="small" style={{ fontWeight: 600 }}>Hypotheses</div>
              <ol className="small secondary" style={{ paddingLeft: 18 }}>{wf.package_preview.hypotheses.map((h, i) => <li key={i}>{h}</li>)}</ol>
              <div className="small muted">{wf.package_preview.constructs.join(", ")} · {wf.package_preview.question_count} questions · n = {wf.package_preview.sample_size}</div>
            </div>
            <div>
              <div className="small" style={{ fontWeight: 600 }}>Quality checks</div>
              <ChecksList checks={wf.package_preview.qa} />
            </div>
          </div>
        </details>
      )}
    </div>
  );
}

export function EvidenceModal({ pid, evidenceId, onClose }: { pid: string; evidenceId: string | null; onClose: () => void }) {
  const { data: list } = useApi<Evidence[]>([pid, "evidence"], `/projects/${pid}/evidence`);
  const ev = list?.find((e) => e.id === evidenceId);
  return (
    <Modal title={ev ? `${ev.code}: ${ev.title}` : "Evidence"} open={Boolean(evidenceId)} onClose={onClose}>
      {ev && (
        <div className="stack-sm">
          <p>{ev.statement}</p>
          <div className="row">
            <OriginBadge origin={ev.origin} />
            <Badge>{sentence(ev.design)}</Badge>
            <span className={`chip strength-${ev.strength}`}>{ev.strength}</span>
          </div>
          <dl className="kv">
            <dt>Sample size</dt><dd>{ev.n ?? "n/a"}</dd>
            <dt>p-value</dt><dd>{pValue(ev.p_value)}</dd>
            <dt>Effect</dt><dd>{ev.effect_size !== null ? `${num(ev.effect_size, 3)} ${ev.effect_label}` : "n/a"}</dd>
            <dt>Interval</dt><dd>{ev.ci_low !== null ? `${num(ev.ci_low, 3)} to ${num(ev.ci_high, 3)}` : "n/a"}</dd>
            <dt>Source</dt><dd>{String(ev.source_ref?.method ?? ev.source_ref?.citation ?? ev.kind)} {ev.source_ref?.dataset ? `· ${String(ev.source_ref.dataset)} v${String(ev.source_ref.version)}` : ""}</dd>
          </dl>
        </div>
      )}
    </Modal>
  );
}

export function ApprovalCard({ pid, approval }: { pid: string; approval: Approval }) {
  const [rationale, setRationale] = useState("");
  const toast = useToast();
  const decide = useProjectMutation(pid, (decision: string) =>
    api.post(`/projects/${pid}/approvals/${approval.id}/decide`, { decision, rationale }));
  const run = (decision: string) => decide.mutate(decision, {
    onSuccess: () => toast(decision === "approved" ? "Approved." : "Rejected."),
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const ops = (approval.payload?.operations as { op: string; reason?: string; rows?: number[]; columns?: string[]; column?: string }[] | undefined) ?? [];
  return (
    <div className="list-item">
      <span style={{ color: "var(--warning-text)", marginTop: 2 }}><Icon name="approvals" /></span>
      <div className="grow stack-sm">
        <div className="row" style={{ gap: 8 }}>
          <strong>{ACTION_LABELS[approval.action] ?? sentence(approval.action)}</strong>
          <Badge>{approval.requested_by.startsWith("agent:") ? `Requested by ${AGENT_LABELS[approval.requested_by.slice(6)] ?? approval.requested_by} agent` : "Requested by a person"}</Badge>
          <span className="small muted">{dateTime(approval.requested_at)}</span>
        </div>
        <div className="secondary">{approval.summary}</div>
        {ops.length > 0 && (
          <ul className="small secondary" style={{ margin: 0, paddingLeft: 18 }}>
            {ops.map((o, i) => (
              <li key={i}><code>{o.op}</code>{o.rows ? ` ${o.rows.length} rows` : ""}{o.columns ? ` ${o.columns.join(", ")}` : ""}{o.column ? ` ${o.column}` : ""}{o.reason ? `: ${o.reason}` : ""}</li>
            ))}
          </ul>
        )}
        <div className="row">
          <input className="input sm" style={{ width: 360 }} placeholder="Rationale (optional, stored in the audit log)" value={rationale}
            onChange={(e) => setRationale(e.target.value)} aria-label="Rationale" />
          <button className="btn sm good" disabled={decide.isPending} onClick={() => run("approved")}><Icon name="check" size={14} />Approve</button>
          <button className="btn sm danger" disabled={decide.isPending} onClick={() => run("rejected")}><Icon name="x" size={14} />Reject</button>
        </div>
      </div>
    </div>
  );
}

export function StartWorkflow({ pid, workflow, inputs, label, primary = true, disabled = false, onStarted }: {
  pid: string; workflow: string; inputs?: Record<string, unknown>; label: string; primary?: boolean; disabled?: boolean;
  onStarted?: (run: WorkflowRun) => void;
}) {
  const toast = useToast();
  const start = useProjectMutation(pid, () => api.post<WorkflowRun>(`/projects/${pid}/workflows`, { workflow, inputs: inputs ?? {} }));
  return (
    <button className={`btn ${primary ? "primary" : ""}`} disabled={disabled || start.isPending}
      onClick={() => start.mutate(undefined, {
        onSuccess: (run) => {
          toast(run.status === "failed" ? `The workflow stopped: ${run.error}` : `${WORKFLOW_LABELS[workflow]} workflow started.`, run.status === "failed" ? "error" : "info");
          onStarted?.(run);
        },
        onError: (e) => toast(errorMessage(e), "error"),
      })}>
      <Icon name="play" size={14} />
      {start.isPending ? "Running agents" : label}
    </button>
  );
}
