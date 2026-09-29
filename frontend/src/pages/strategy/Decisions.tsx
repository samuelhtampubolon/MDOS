import { useState, type FormEvent } from "react";
import { api, errorMessage } from "../../api/client";
import { useDecisions, useEvidence, useProjectMutation } from "../../api/hooks";
import type { Decision, Scenario } from "../../api/types";
import { AGENT_LABELS, EvidenceModal } from "../../components/domain";
import { Callout, Card, Empty, Icon, StatusBadge, useToast } from "../../components/ui";
import { dateTime, money } from "../../lib/format";

export default function Decisions({ pid, scenarios, currency }: { pid: string; scenarios: Scenario[]; currency: string }) {
  const { data: decisions } = useDecisions(pid);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  return (
    <div className="stack">
      <Callout icon="lock">Decisions proposed by agents or teammates take effect only after a person approves them. Every decision keeps its scenario and evidence.</Callout>
      {!decisions?.length ? <Empty title="No decisions logged yet">Log a decision below, or run the strategy agents to get a proposal.</Empty> : (
        decisions.map((d) => <DecisionCard key={d.id} pid={pid} d={d} scenarios={scenarios} currency={currency} onEvidence={setEvidenceId} />)
      )}
      <NewDecision pid={pid} scenarios={scenarios} />
      <EvidenceModal pid={pid} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />
    </div>
  );
}

function DecisionCard({ pid, d, scenarios, currency, onEvidence }: { pid: string; d: Decision; scenarios: Scenario[]; currency: string; onEvidence: (id: string) => void }) {
  const toast = useToast();
  const { data: evidence } = useEvidence(pid);
  const [rationale, setRationale] = useState("");
  const decide = useProjectMutation(pid, (approve: boolean) => api.post(`/projects/${pid}/decisions/${d.id}/decide`, { approve, rationale }));
  const scenario = scenarios.find((s) => s.id === d.scenario_id);
  const byId = new Map((evidence ?? []).map((e) => [e.id, e]));
  const createdBy = d.created_by ?? "";
  return (
    <Card title={d.title} subtitle={`${createdBy.startsWith("agent:") ? `Proposed by the ${AGENT_LABELS[createdBy.slice(6)] ?? "strategy"} agent` : "Logged by a person"} · ${dateTime(d.created_at)}`}
      actions={<StatusBadge status={d.status === "proposed" ? "pending" : d.status} label={d.status === "proposed" ? "Proposed" : undefined} />}>
      <div className="stack-sm">
        <p style={{ margin: 0, fontWeight: 500 }}>{d.decision}</p>
        {d.rationale && <div className="small secondary">{d.rationale}</div>}
        {scenario && (
          <div className="small">Scenario: <strong>{scenario.name}</strong> · simulated profit {money(scenario.results.kpis.profit, currency)} per month
            with {Math.round(scenario.results.kpis.customers)} customers</div>
        )}
        <div className="row" style={{ gap: 4 }}>
          <span className="small muted">Evidence</span>
          {d.evidence_ids.length ? d.evidence_ids.map((id) => {
            const e = byId.get(id);
            return <button key={id} className={`chip strength-${e?.strength ?? ""}`} title={e?.title} onClick={() => onEvidence(id)}>{e?.code ?? "view"}</button>;
          }) : <span className="small muted">None linked</span>}
        </div>
        {d.status === "proposed" && (
          <div className="row">
            <input className="input sm" style={{ maxWidth: 360 }} placeholder="Rationale (optional)" aria-label="Decision rationale" value={rationale} onChange={(e) => setRationale(e.target.value)} />
            <button className="btn sm good" disabled={decide.isPending} onClick={() => decide.mutate(true, { onSuccess: () => toast("Decision approved."), onError: (e) => toast(errorMessage(e), "error") })}>
              <Icon name="check" size={12} />Approve</button>
            <button className="btn sm danger" disabled={decide.isPending} onClick={() => decide.mutate(false, { onSuccess: () => toast("Decision rejected."), onError: (e) => toast(errorMessage(e), "error") })}>
              <Icon name="x" size={12} />Reject</button>
          </div>
        )}
      </div>
    </Card>
  );
}

function NewDecision({ pid, scenarios }: { pid: string; scenarios: Scenario[] }) {
  const toast = useToast();
  const { data: evidence } = useEvidence(pid);
  const empty = { title: "", decision: "", rationale: "", scenario_id: "", evidence_ids: [] as string[] };
  const [form, setForm] = useState(empty);
  const create = useProjectMutation(pid, (body: typeof empty) => api.post(`/projects/${pid}/decisions`, { ...body, scenario_id: body.scenario_id || null }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(form, { onSuccess: () => { toast("Decision logged and sent for approval."); setForm(empty); }, onError: (err) => toast(errorMessage(err), "error") });
  };
  return (
    <details className="disclosure card" style={{ padding: 16 }}>
      <summary><Icon name="plus" size={12} />Log a decision</summary>
      <form className="stack-sm" onSubmit={submit}>
        <div className="field"><label htmlFor="dc-t">Title</label>
          <input id="dc-t" className="input" required minLength={3} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
        <div className="field"><label htmlFor="dc-d">Decision</label>
          <textarea id="dc-d" className="textarea" required minLength={3} value={form.decision} onChange={(e) => setForm({ ...form, decision: e.target.value })} /></div>
        <div className="grid grid-2">
          <div className="field"><label htmlFor="dc-r">Rationale</label>
            <input id="dc-r" className="input" value={form.rationale} onChange={(e) => setForm({ ...form, rationale: e.target.value })} /></div>
          <div className="field"><label htmlFor="dc-s">Scenario</label>
            <select id="dc-s" className="select" value={form.scenario_id} onChange={(e) => setForm({ ...form, scenario_id: e.target.value })}>
              <option value="">None</option>{scenarios.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </select></div>
        </div>
        <div className="field">
          <label htmlFor="dc-e">Evidence</label>
          <select id="dc-e" className="select" multiple size={6} value={form.evidence_ids}
            onChange={(e) => setForm({ ...form, evidence_ids: Array.from(e.target.selectedOptions).map((o) => o.value) })}>
            {(evidence ?? []).map((ev) => <option key={ev.id} value={ev.id}>{ev.code} {ev.title}</option>)}
          </select>
          <span className="hint">Hold Ctrl or Cmd to choose several.</span>
        </div>
        <div><button className="btn primary" disabled={create.isPending}>Log decision</button></div>
      </form>
    </details>
  );
}
