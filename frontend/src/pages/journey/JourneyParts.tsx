import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useEvidence, useProjectMutation } from "../../api/hooks";
import type { Intervention, Journey, PainPoint } from "../../api/types";
import { BarChart } from "../../components/charts/basic";
import { EvidenceModal } from "../../components/domain";
import { Badge, Callout, Card, Empty, Icon, StatusBadge, useToast } from "../../components/ui";
import { money, num, pct, sentence, signedPct } from "../../lib/format";

const KIND_LABELS: Record<string, string> = {
  conversion_uplift: "Raise the continue rate", reduce_steps: "Remove steps", satisfaction_uplift: "Improve satisfaction",
};

export function PainPoints({ pid, journey }: { pid: string; journey: Journey }) {
  const toast = useToast();
  const { data: evidence } = useEvidence(pid);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const propose = useProjectMutation(pid, () => api.post<Intervention[]>(`/projects/${pid}/journeys/${journey.id}/interventions/propose`));
  const stageName = new Map(journey.stages.map((s) => [s.key, s.name]));
  const codes = new Map((evidence ?? []).map((e) => [e.id, e.code]));
  return (
    <div className="stack">
      <Card title="Pain points ranked by priority" subtitle="Priority combines how often a problem is mentioned, how negative the mentions are and how many customers reach that stage."
        actions={<button className="btn primary" disabled={propose.isPending || !journey.pain_points.length} onClick={() => propose.mutate(undefined, {
          onSuccess: (list) => toast(list.length ? `${list.length} intervention idea(s) added.` : "Every open pain point already has an intervention."),
          onError: (e) => toast(errorMessage(e), "error"),
        })}><Icon name="play" size={14} />Propose interventions</button>}>
        {!journey.pain_points.length ? <Empty title="No pain points yet">Analyze reviews to find friction, or add one below from your own observations.</Empty> : (
          <div className="stack-sm">
            {journey.pain_points.map((p, i) => (
              <PainPointRow key={p.id} pid={pid} journey={journey} p={p} rank={i + 1} stage={stageName.get(p.stage_key) ?? p.stage_key} codes={codes} onEvidence={setEvidenceId} />
            ))}
          </div>
        )}
      </Card>
      <NewPainPoint pid={pid} journey={journey} />
      <EvidenceModal pid={pid} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />
    </div>
  );
}

function PainPointRow({ pid, journey, p, rank, stage, codes, onEvidence }: {
  pid: string; journey: Journey; p: PainPoint; rank: number; stage: string; codes: Map<string, string>; onEvidence: (id: string) => void;
}) {
  const toast = useToast();
  const setStatus = useProjectMutation(pid, (status: string) => api.patch(`/projects/${pid}/journeys/${journey.id}/pain-points/${p.id}`, { status }));
  const quotes = Array.from(new Set(p.quotes));
  return (
    <div className="list-item" style={{ alignItems: "flex-start", opacity: p.status === "dismissed" ? 0.6 : 1 }}>
      <span className="chip" style={{ minWidth: 30, justifyContent: "center" }}>{rank}</span>
      <div className="grow stack-sm">
        <div className="row" style={{ gap: 8 }}>
          <strong>{p.theme || p.title}</strong>
          <Badge>{stage}</Badge>
          {p.evidence_ids.map((id) => <button key={id} className="chip code" onClick={() => onEvidence(id)}>{codes.get(id) ?? "evidence"}</button>)}
        </div>
        <div className="small muted">
          {p.mentions} mentions ({pct(p.frequency, 1)} of texts) · severity {pct(p.severity)} · reach {pct(p.reach)} · priority score {num(p.score, 1)}
        </div>
        {p.description && <div className="small secondary">{p.description}</div>}
        {quotes.slice(0, 2).map((q) => (
          <blockquote key={q} className="small secondary" style={{ margin: 0, paddingLeft: 8, borderLeft: "2px solid var(--div-neg)" }}>"{q}"</blockquote>
        ))}
      </div>
      <select className="select sm" aria-label={`Status of ${p.title}`} value={p.status}
        onChange={(e) => setStatus.mutate(e.target.value, { onError: (er) => toast(errorMessage(er), "error") })}>
        <option value="open">Open</option><option value="addressed">Addressed</option><option value="dismissed">Dismissed</option>
      </select>
    </div>
  );
}

function NewPainPoint({ pid, journey }: { pid: string; journey: Journey }) {
  const toast = useToast();
  const empty = { stage_key: journey.stages[0]?.key ?? "", title: "", description: "", frequency: 10, severity: 50, reach: 100 };
  const [form, setForm] = useState(empty);
  const create = useProjectMutation(pid, () => api.post(`/projects/${pid}/journeys/${journey.id}/pain-points`, {
    stage_key: form.stage_key, title: form.title, description: form.description,
    frequency: form.frequency / 100, severity: form.severity / 100, reach: form.reach / 100,
  }));
  return (
    <details className="disclosure card" style={{ padding: 16 }}>
      <summary><Icon name="plus" size={12} />Add a pain point from observation or interviews</summary>
      <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); create.mutate(undefined, {
        onSuccess: () => { toast("Pain point added."); setForm(empty); }, onError: (er) => toast(errorMessage(er), "error"),
      }); }}>
        <div className="grid grid-2">
          <div className="field"><label htmlFor="pp-s">Stage</label>
            <select id="pp-s" className="select" value={form.stage_key} onChange={(e) => setForm({ ...form, stage_key: e.target.value })}>
              {journey.stages.map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
            </select></div>
          <div className="field"><label htmlFor="pp-t">Problem</label>
            <input id="pp-t" className="input" required minLength={3} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
        </div>
        <div className="field"><label htmlFor="pp-d">Description</label>
          <input id="pp-d" className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
        <div className="grid grid-3">
          {(["frequency", "severity", "reach"] as const).map((k) => (
            <div key={k} className="field"><label htmlFor={`pp-${k}`}>{sentence(k)}: {form[k]}%</label>
              <input id={`pp-${k}`} type="range" min={0} max={100} value={form[k]} onChange={(e) => setForm({ ...form, [k]: Number(e.target.value) })} /></div>
          ))}
        </div>
        <div><button className="btn primary" disabled={create.isPending}>Add pain point</button></div>
      </form>
    </details>
  );
}

export function Interventions({ pid, journey, currency }: { pid: string; journey: Journey; currency: string }) {
  const simulated = journey.interventions.filter((iv) => iv.simulation?.levels);
  const ranking = simulated
    .map((iv) => ({ label: iv.title, value: iv.simulation.levels?.mid.delta_customers ?? 0, low: iv.simulation.levels?.low.delta_customers, high: iv.simulation.levels?.high.delta_customers }))
    .sort((a, b) => b.value - a.value);
  return (
    <div className="stack">
      <Callout icon="info">
        Uplifts are estimates with a low, mid and high case, not measured effects. Test the most promising interventions before rolling them out:
        a completed A/B test becomes experimental evidence in the research lab.
      </Callout>
      {ranking.length > 0 && (
        <Card><BarChart title="Extra customers per month by intervention" subtitle="Mid estimate, with the low to high range as a whisker" data={ranking} fmt="number" /></Card>
      )}
      {!journey.interventions.length ? <Empty title="No interventions yet">Propose interventions from the pain points, or add one below.</Empty> : (
        journey.interventions.map((iv) => <InterventionCard key={iv.id} pid={pid} journey={journey} iv={iv} currency={currency} />)
      )}
      <NewIntervention pid={pid} journey={journey} />
    </div>
  );
}

function InterventionCard({ pid, journey, iv, currency }: { pid: string; journey: Journey; iv: Intervention; currency: string }) {
  const toast = useToast();
  const navigate = useNavigate();
  const update = useProjectMutation(pid, (body: Record<string, unknown>) => api.patch(`/projects/${pid}/journeys/${journey.id}/interventions/${iv.id}`, body));
  const experiment = useProjectMutation(pid, () => api.post(`/projects/${pid}/journeys/${journey.id}/interventions/${iv.id}/experiment`));
  const remove = useProjectMutation(pid, () => api.del(`/projects/${pid}/journeys/${journey.id}/interventions/${iv.id}`));
  const stage = journey.stages.find((s) => s.key === iv.stage_key)?.name ?? iv.stage_key;
  const pain = journey.pain_points.find((p) => p.id === iv.pain_point_id);
  const levels = iv.simulation?.levels;
  const steps = iv.kind === "reduce_steps" ? (iv.params as { steps_from?: number; steps_to?: number }) : null;
  const assumed = (lvl: "low" | "mid" | "high") => steps
    ? `${{ low: "25%", mid: "50%", high: "100%" }[lvl]} of the gain`
    : pct(lvl === "low" ? iv.uplift_low : lvl === "mid" ? iv.uplift_mid : iv.uplift_high, 1);
  return (
    <Card title={iv.title} subtitle={`${stage} · ${KIND_LABELS[iv.kind] ?? sentence(iv.kind)}${pain ? ` · addresses "${pain.theme || pain.title}"` : ""}`}
      actions={<>
        <StatusBadge status={iv.confidence} label={`${sentence(iv.confidence)} confidence`} />
        <Badge>Effort {iv.effort}</Badge>
        <select className="select sm" aria-label={`Status of ${iv.title}`} value={iv.status}
          onChange={(e) => update.mutate({ status: e.target.value }, { onError: (er) => toast(errorMessage(er), "error") })}>
          {["idea", "planned", "testing", "done", "dropped"].map((s) => <option key={s} value={s}>{sentence(s)}</option>)}
        </select>
      </>}>
      <div className="stack-sm">
        {iv.description && <div className="secondary">{iv.description}</div>}
        {steps?.steps_to !== undefined && <div className="small">Steps at this stage: {steps.steps_from ?? "current"} to {steps.steps_to}</div>}
        {levels && (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Case</th><th className="num">Uplift assumed</th><th className="num">Extra customers per month</th><th className="num">Extra revenue per month</th><th className="num">Change</th></tr></thead>
              <tbody>
                {(["low", "mid", "high"] as const).map((lvl) => (
                  <tr key={lvl}>
                    <td>{sentence(lvl)}</td>
                    <td className="num">{assumed(lvl)}</td>
                    <td className="num">{num(levels[lvl].delta_customers, 1)}</td>
                    <td className="num">{money(levels[lvl].delta_revenue, currency, { compact: true })}</td>
                    <td className="num">{signedPct(levels[lvl].pct_customers, 1)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {iv.simulation?.assumptions && iv.simulation.assumptions.length > 0 && (
          <ul className="small muted" style={{ margin: 0, paddingLeft: 18 }}>{iv.simulation.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
        )}
        <div className="row">
          <button className="btn sm primary" disabled={experiment.isPending} onClick={() => experiment.mutate(undefined, {
            onSuccess: () => { toast("A/B test drafted and sent for launch approval."); navigate(`/p/${pid}/experiments`); },
            onError: (e) => toast(errorMessage(e), "error"),
          })}><Icon name="experiments" size={14} />Design an A/B test</button>
          <button className="btn sm ghost" onClick={() => window.confirm("Delete this intervention?") && remove.mutate(undefined, { onError: (e) => toast(errorMessage(e), "error") })}>
            <Icon name="trash" size={14} />Delete</button>
        </div>
      </div>
    </Card>
  );
}

function NewIntervention({ pid, journey }: { pid: string; journey: Journey }) {
  const toast = useToast();
  const empty = { pain_point_id: "", stage_key: journey.stages[0]?.key ?? "", title: "", description: "", kind: "conversion_uplift",
    low: 5, mid: 10, high: 20, effort: "M", confidence: "low" };
  const [form, setForm] = useState(empty);
  const create = useProjectMutation(pid, () => api.post(`/projects/${pid}/journeys/${journey.id}/interventions`, {
    pain_point_id: form.pain_point_id || null, stage_key: form.pain_point_id ? null : form.stage_key, title: form.title, description: form.description,
    kind: form.kind, uplift_low: form.low / 100, uplift_mid: form.mid / 100, uplift_high: form.high / 100, effort: form.effort, confidence: form.confidence,
  }));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!(form.low <= form.mid && form.mid <= form.high)) return toast("Uplifts must satisfy low ≤ mid ≤ high.", "error");
    create.mutate(undefined, { onSuccess: () => { toast("Intervention added and simulated."); setForm(empty); }, onError: (er) => toast(errorMessage(er), "error") });
  };
  return (
    <details className="disclosure card" style={{ padding: 16 }}>
      <summary><Icon name="plus" size={12} />Add an intervention</summary>
      <form className="stack-sm" onSubmit={submit}>
        <div className="grid grid-2">
          <div className="field"><label htmlFor="iv-p">Pain point (optional)</label>
            <select id="iv-p" className="select" value={form.pain_point_id} onChange={(e) => setForm({ ...form, pain_point_id: e.target.value })}>
              <option value="">None, choose a stage</option>
              {journey.pain_points.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
            </select></div>
          <div className="field"><label htmlFor="iv-s">Stage</label>
            <select id="iv-s" className="select" disabled={Boolean(form.pain_point_id)} value={form.stage_key} onChange={(e) => setForm({ ...form, stage_key: e.target.value })}>
              {journey.stages.map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
            </select></div>
        </div>
        <div className="grid grid-2">
          <div className="field"><label htmlFor="iv-t">Title</label>
            <input id="iv-t" className="input" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
          <div className="field"><label htmlFor="iv-k">Type</label>
            <select id="iv-k" className="select" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>
              {Object.entries(KIND_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select></div>
        </div>
        <div className="field"><label htmlFor="iv-d">Description</label>
          <input id="iv-d" className="input" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></div>
        <div className="grid grid-4">
          {(["low", "mid", "high"] as const).map((k) => (
            <div key={k} className="field"><label htmlFor={`iv-${k}`}>{sentence(k)} uplift (%)</label>
              <input id={`iv-${k}`} className="input" type="number" step="any" min={0} value={form[k]} onChange={(e) => setForm({ ...form, [k]: Number(e.target.value) })} /></div>
          ))}
          <div className="field"><label htmlFor="iv-e">Effort</label>
            <select id="iv-e" className="select" value={form.effort} onChange={(e) => setForm({ ...form, effort: e.target.value })}>
              <option value="S">Small</option><option value="M">Medium</option><option value="L">Large</option>
            </select></div>
        </div>
        <div><button className="btn primary" disabled={create.isPending}>Add and simulate</button></div>
      </form>
    </details>
  );
}
