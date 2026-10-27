import { useState, type FormEvent } from "react";
import { api, errorMessage } from "../api/client";
import { useEvidence, useExperiments, useProjectMutation } from "../api/hooks";
import type { Experiment } from "../api/types";
import { AGENT_LABELS, EvidenceModal } from "../components/domain";
import { Badge, Callout, Card, Empty, Icon, PageHeader, Stat, StatusBadge, useToast } from "../components/ui";
import { dateTime, num, pct, pValue } from "../lib/format";

const STATUS_LABELS: Record<string, string> = { draft: "Awaiting launch approval", running: "Running", completed: "Completed", cancelled: "Cancelled" };

export default function Experiments({ pid }: { pid: string }) {
  const { data: experiments } = useExperiments(pid);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const order = ["running", "draft", "completed", "cancelled"];
  const sorted = [...(experiments ?? [])].sort((a, b) => order.indexOf(a.status) - order.indexOf(b.status));
  return (
    <div className="stack">
      <PageHeader eyebrow="Experimentation" title="Test before you roll out"
        description="Experiments are sized for statistical power, launched only after approval, and their results return to the research lab as experimental evidence." />
      <Callout icon="flag">
        Experimental evidence is the only kind that allows causal wording ("increases", "causes") in insights and reports. Everything else stays associational.
      </Callout>
      {!sorted.length ? <Empty title="No experiments yet">Design one from a journey intervention, or create one below.</Empty> : (
        sorted.map((x) => <ExperimentCard key={x.id} pid={pid} x={x} onEvidence={setEvidenceId} />)
      )}
      <NewExperiment pid={pid} />
      <EvidenceModal pid={pid} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />
    </div>
  );
}

function ExperimentCard({ pid, x, onEvidence }: { pid: string; x: Experiment; onEvidence: (id: string) => void }) {
  const toast = useToast();
  const { data: evidence } = useEvidence(pid);
  const decide = useProjectMutation(pid, (approve: boolean) => api.post(`/projects/${pid}/experiments/${x.id}/decide`, { approve }));
  const remove = useProjectMutation(pid, () => api.del(`/projects/${pid}/experiments/${x.id}`));
  const code = evidence?.find((e) => e.id === x.evidence_id)?.code;
  const createdBy = x.created_by ?? "";
  const res = x.results as Record<string, unknown> & { summary?: string; notes?: string[] };
  return (
    <Card title={x.name}
      subtitle={`${createdBy.startsWith("agent:") ? `Designed by the ${AGENT_LABELS[createdBy.slice(6)] ?? "Experiment Design"} agent` : "Created by a person"} · ${dateTime(x.created_at)}`}
      actions={<>
        <StatusBadge status={x.status === "draft" ? "pending" : x.status === "running" ? "running" : x.status} label={STATUS_LABELS[x.status]} />
        {x.status !== "running" && <button className="btn ghost icon sm" aria-label="Delete experiment" onClick={() => window.confirm(`Delete "${x.name}"?`)
          && remove.mutate(undefined, { onError: (e) => toast(errorMessage(e), "error") })}><Icon name="trash" size={14} /></button>}
      </>}>
      <div className="stack">
        <div><span className="small muted">Hypothesis: </span>{x.hypothesis}</div>
        <div className="stats inline">
          <Stat label="Primary metric" value={<span style={{ fontSize: 15 }}>{x.primary_metric}</span>} delta={`baseline ${pct(x.baseline_rate, 1)}`} />
          <Stat label="Smallest effect to detect" value={`${pct(x.mde)} relative`} delta={`${pct(x.baseline_rate, 1)} to ${pct(x.baseline_rate * (1 + x.mde), 1)}`} />
          <Stat label="Sample per variant" value={num(x.sample_size_per_arm)} delta={`alpha ${x.alpha}, power ${pct(x.power)}`} />
          <Stat label="Duration" value={x.duration_days ? `${x.duration_days} days` : "Set traffic"} delta={x.expected_daily_traffic ? `${num(x.expected_daily_traffic)} visitors per day` : undefined}
            deltaTone={x.duration_days && x.duration_days > 90 ? "down" : undefined} />
        </div>
        {x.duration_days !== null && x.duration_days > 90 && (
          <Callout tone="warning">This test would run longer than 90 days. Test a bigger change, use a higher-traffic stage or accept a larger detectable effect.</Callout>
        )}
        <div className="row" style={{ gap: 6 }}>
          <span className="small muted">Variants</span>
          {x.variants.map((v) => <span key={v.name} className="chip" title={v.description}>{v.name}</span>)}
        </div>
        {x.status === "draft" && (
          <div className="row">
            <button className="btn sm good" disabled={decide.isPending} onClick={() => decide.mutate(true, { onSuccess: () => toast("Launch approved. The experiment is running."), onError: (e) => toast(errorMessage(e), "error") })}>
              <Icon name="check" size={12} />Approve launch</button>
            <button className="btn sm danger" disabled={decide.isPending} onClick={() => decide.mutate(false, { onSuccess: () => toast("Experiment cancelled."), onError: (e) => toast(errorMessage(e), "error") })}>
              <Icon name="x" size={12} />Reject</button>
            <SizingEditor pid={pid} x={x} />
          </div>
        )}
        {x.status === "running" && <ResultsForm pid={pid} x={x} />}
        {x.status === "completed" && res.summary && (
          <div className="stack-sm">
            <Callout tone={res.significant ? "good" : "warning"}>{res.summary}</Callout>
            <div className="row" style={{ gap: 6 }}>
              {code && x.evidence_id && <button className="chip strength-strong" onClick={() => onEvidence(x.evidence_id as string)}>Saved as evidence {code}</button>}
              {typeof res.p_value === "number" && <Badge>{pValue(res.p_value)}</Badge>}
            </div>
            {res.notes && res.notes.length > 0 && <ul className="small secondary" style={{ margin: 0, paddingLeft: 18 }}>{res.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
          </div>
        )}
      </div>
    </Card>
  );
}

function SizingEditor({ pid, x }: { pid: string; x: Experiment }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ baseline: +(x.baseline_rate * 100).toFixed(2), mde: +(x.mde * 100).toFixed(1), traffic: x.expected_daily_traffic });
  const save = useProjectMutation(pid, () => api.patch(`/projects/${pid}/experiments/${x.id}`, {
    baseline_rate: form.baseline / 100, mde: form.mde / 100, expected_daily_traffic: form.traffic,
  }));
  if (!open) return <button className="btn sm ghost" onClick={() => setOpen(true)}>Adjust sizing</button>;
  return (
    <form className="row" onSubmit={(e) => { e.preventDefault(); save.mutate(undefined, { onSuccess: () => { toast("Sample size recalculated."); setOpen(false); }, onError: (er) => toast(errorMessage(er), "error") }); }}>
      <label className="small row" style={{ gap: 4 }}>Baseline %<input className="input sm" type="number" step="any" style={{ width: 80 }} value={form.baseline} onChange={(e) => setForm({ ...form, baseline: Number(e.target.value) })} /></label>
      <label className="small row" style={{ gap: 4 }}>Effect %<input className="input sm" type="number" step="any" style={{ width: 70 }} value={form.mde} onChange={(e) => setForm({ ...form, mde: Number(e.target.value) })} /></label>
      <label className="small row" style={{ gap: 4 }}>Visitors/day<input className="input sm" type="number" style={{ width: 90 }} value={form.traffic} onChange={(e) => setForm({ ...form, traffic: Number(e.target.value) })} /></label>
      <button className="btn sm primary" disabled={save.isPending}>Recalculate</button>
    </form>
  );
}

function ResultsForm({ pid, x }: { pid: string; x: Experiment }) {
  const toast = useToast();
  const [form, setForm] = useState({ control_visitors: "", control_conversions: "", treatment_visitors: "", treatment_conversions: "" });
  const [error, setError] = useState("");
  const submit = useProjectMutation(pid, () => api.post(`/projects/${pid}/experiments/${x.id}/results`, Object.fromEntries(Object.entries(form).map(([k, v]) => [k, Number(v)]))));
  const cv = Number(form.control_visitors);
  const tv = Number(form.treatment_visitors);
  const short = cv > 0 && tv > 0 && Math.min(cv, tv) < x.sample_size_per_arm;
  return (
    <form className="stack-sm" onSubmit={(e: FormEvent) => { e.preventDefault(); submit.mutate(undefined, {
      onSuccess: () => { toast("Results analyzed and saved as experimental evidence."); setError(""); }, onError: (er) => setError(errorMessage(er)),
    }); }}>
      <div className="small" style={{ fontWeight: 600 }}>Enter results</div>
      <div className="grid grid-4">
        {([["control_visitors", "Control visitors"], ["control_conversions", "Control conversions"], ["treatment_visitors", "Treatment visitors"], ["treatment_conversions", "Treatment conversions"]] as const).map(([k, label]) => (
          <div key={k} className="field"><label htmlFor={`${x.id}-${k}`}>{label}</label>
            <input id={`${x.id}-${k}`} className="input" type="number" min={0} required value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })} /></div>
        ))}
      </div>
      {short && <Callout tone="warning">Fewer visitors than the planned {num(x.sample_size_per_arm)} per variant. The test may be underpowered; a non-significant result would be inconclusive, not proof of no effect.</Callout>}
      {error && <Callout tone="critical">{error}</Callout>}
      <div><button className="btn primary" disabled={submit.isPending}>Analyze results</button></div>
    </form>
  );
}

function NewExperiment({ pid }: { pid: string }) {
  const toast = useToast();
  const empty = { name: "", hypothesis: "", primary_metric: "Booking conversion rate", baseline: 5, mde: 20, alpha: 0.05, power: 0.8, traffic: 200 };
  const [form, setForm] = useState(empty);
  const create = useProjectMutation(pid, () => api.post(`/projects/${pid}/experiments`, {
    name: form.name, hypothesis: form.hypothesis, primary_metric: form.primary_metric, baseline_rate: form.baseline / 100, mde: form.mde / 100,
    alpha: form.alpha, power: form.power, expected_daily_traffic: form.traffic,
  }));
  return (
    <details className="disclosure card" style={{ padding: 16 }}>
      <summary><Icon name="plus" size={12} />Create an experiment</summary>
      <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); create.mutate(undefined, {
        onSuccess: () => { toast("Experiment drafted. Approve the launch when ready."); setForm(empty); }, onError: (er) => toast(errorMessage(er), "error"),
      }); }}>
        <div className="grid grid-2">
          <div className="field"><label htmlFor="ex-n">Name</label>
            <input id="ex-n" className="input" required minLength={3} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="field"><label htmlFor="ex-m">Primary metric</label>
            <input id="ex-m" className="input" required value={form.primary_metric} onChange={(e) => setForm({ ...form, primary_metric: e.target.value })} /></div>
        </div>
        <div className="field"><label htmlFor="ex-h">Hypothesis</label>
          <textarea id="ex-h" className="textarea" required minLength={5} placeholder="If we show the total price upfront, more visitors who start booking will finish."
            value={form.hypothesis} onChange={(e) => setForm({ ...form, hypothesis: e.target.value })} /></div>
        <div className="grid grid-4">
          <div className="field"><label htmlFor="ex-b">Current rate (%)</label>
            <input id="ex-b" className="input" type="number" step="any" min={0.01} max={99} value={form.baseline} onChange={(e) => setForm({ ...form, baseline: Number(e.target.value) })} /></div>
          <div className="field"><label htmlFor="ex-e">Smallest relative effect (%)</label>
            <input id="ex-e" className="input" type="number" step="any" min={1} value={form.mde} onChange={(e) => setForm({ ...form, mde: Number(e.target.value) })} /></div>
          <div className="field"><label htmlFor="ex-t">Visitors per day</label>
            <input id="ex-t" className="input" type="number" min={0} value={form.traffic} onChange={(e) => setForm({ ...form, traffic: Number(e.target.value) })} /></div>
          <div className="field"><label htmlFor="ex-p">Power</label>
            <select id="ex-p" className="select" value={form.power} onChange={(e) => setForm({ ...form, power: Number(e.target.value) })}>
              <option value={0.8}>80%</option><option value={0.9}>90%</option>
            </select></div>
        </div>
        <span className="hint">The sample size is computed for a two-sided test of two proportions at alpha {form.alpha}. Variants default to control and treatment.</span>
        <div><button className="btn primary" disabled={create.isPending}>Create experiment</button></div>
      </form>
    </details>
  );
}
