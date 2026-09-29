import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useProjectMutation, useResearch } from "../../api/hooks";
import type { Hypothesis } from "../../api/types";
import { EvidenceModal } from "../../components/domain";
import { Callout, Card, Empty, Icon, StatusBadge, useToast } from "../../components/ui";
import { num, pct, sentence } from "../../lib/format";

function list(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String) : [];
}

export default function Plan({ pid }: { pid: string }) {
  const { data } = useResearch(pid);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  if (!data) return null;
  if (!data.hypotheses.length && !Object.keys(data.plans).length) {
    return <Empty title="No research plan yet">Run the design agents from the Project brief tab, then approve the design package.</Empty>;
  }
  const framing = data.plans.framing?.content ?? {};
  const design = data.plans.design?.content ?? {};
  const sampling = data.plans.sampling?.content ?? {};
  const fieldwork = data.plans.fieldwork?.content ?? {};
  const guide = data.plans.interview_guide?.content ?? {};
  const size = (sampling.sample_size ?? {}) as Record<string, number>;
  return (
    <div className="stack">
      <div className="grid grid-2">
        <Card title="Problem framing" subtitle={String(framing.study_type ?? "")}>
          <div className="stack-sm">
            <div><div className="small muted">Decision</div><div>{String(framing.decision_statement ?? "")}</div></div>
            <div><div className="small muted">Research problem</div><div>{String(framing.research_problem ?? "")}</div></div>
            <div>
              <div className="small muted">Objectives</div>
              <ol style={{ margin: 0, paddingLeft: 18 }}>{list(framing.objectives).map((o, i) => <li key={i}>{o}</li>)}</ol>
            </div>
            {list(framing.decision_criteria).length > 0 && <Callout icon="flag"><strong>Decision criteria:</strong> {list(framing.decision_criteria).join(" ")}</Callout>}
          </div>
        </Card>
        <Card title="Research questions and caveats">
          <ol style={{ margin: 0, paddingLeft: 18 }} className="stack-sm">
            {data.research_questions.map((q) => <li key={q.id}><strong>{q.code}.</strong> {q.text}</li>)}
          </ol>
          {list(design.design_caveats).length > 0 && (
            <div style={{ marginTop: 12 }}>
              <Callout tone="warning"><strong>Design caveats.</strong> {list(design.design_caveats).join(" ")}</Callout>
            </div>
          )}
        </Card>
      </div>
      <Card title="Hypothesis canvas" subtitle="Agents may propose verdicts from evidence; only a person can approve them.">
        <div className="stack-sm">
          {data.hypotheses.map((h) => <HypothesisRow key={h.id} pid={pid} h={h} onEvidence={setEvidenceId} />)}
          <NewHypothesis pid={pid} />
        </div>
      </Card>
      <div className="grid grid-2">
        <Card title="Measurement model" subtitle="Constructs from the curated library, with source citations.">
          <div className="stack-sm">
            {data.constructs.map((c) => (
              <div key={c.id} className="list-item" style={{ padding: "6px 0" }}>
                <span className="chip code">{c.code}</span>
                <div className="grow">
                  <strong>{c.name}</strong>
                  <div className="small secondary">{c.definition}</div>
                  <div className="small muted">{c.source_reference}</div>
                </div>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Sampling plan" subtitle={String(sampling.method ?? "")}>
          <dl className="kv">
            <dt>Population</dt><dd>{String(sampling.target_population ?? "")}</dd>
            <dt>Recommended n</dt><dd className="num">{num(size.recommended)}</dd>
            <dt>n for 5% margin</dt><dd className="num">{num(size.for_5pct_margin)}</dd>
            <dt>Regression minimum</dt><dd className="num">{num(size.regression_minimum)}</dd>
            <dt>Frame</dt><dd>{list(sampling.sampling_frame).join("; ")}</dd>
          </dl>
          {Array.isArray(sampling.quotas) && sampling.quotas.length > 0 && (
            <div className="table-wrap" style={{ marginTop: 10 }}>
              <table className="table">
                <thead><tr><th>Quota</th><th className="num">Share</th><th className="num">n</th></tr></thead>
                <tbody>{(sampling.quotas as { group: string; share: number; n: number }[]).map((q) => (
                  <tr key={q.group}><td>{q.group}</td><td className="num">{pct(q.share)}</td><td className="num">{q.n}</td></tr>
                ))}</tbody>
              </table>
            </div>
          )}
          {list(sampling.assumptions).map((a) => <div key={a} style={{ marginTop: 8 }}><Callout tone="warning">{a}</Callout></div>)}
        </Card>
      </div>
      <div className="grid grid-2">
        <Card title="Fieldwork plan">
          <div className="stack-sm">
            <div className="small muted">Channels</div>
            <ul style={{ margin: 0, paddingLeft: 18 }}>{list(fieldwork.channels).map((c) => <li key={c}>{c}</li>)}</ul>
            <div className="small muted">Timeline</div>
            <ul style={{ margin: 0, paddingLeft: 18 }}>
              {(Array.isArray(fieldwork.timeline) ? fieldwork.timeline as { week: number; activity: string }[] : []).map((t) => <li key={t.week}>Week {t.week}: {t.activity}</li>)}
            </ul>
            <div className="small muted">Quality control</div>
            <ul style={{ margin: 0, paddingLeft: 18 }}>{list(fieldwork.quality_control).map((c) => <li key={c}>{c}</li>)}</ul>
          </div>
        </Card>
        <Card title="Interview guide" subtitle="For 8 to 12 qualitative interviews that explain survey findings.">
          <ol style={{ margin: 0, paddingLeft: 18 }} className="stack-sm">{list(guide.questions).map((q) => <li key={q}>{q}</li>)}</ol>
        </Card>
      </div>
      <SampleSizeCalculator />
      <VariableDictionary pid={pid} />
      <EvidenceModal pid={pid} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />
    </div>
  );
}

type HypothesisFields = Pick<Hypothesis, "statement" | "iv" | "dv" | "mediator" | "moderator" | "expected_direction" | "rationale">;

function HypothesisForm({ initial, busy, submitLabel, onSubmit, onCancel }: {
  initial: HypothesisFields; busy: boolean; submitLabel: string; onSubmit: (v: HypothesisFields) => void; onCancel?: () => void;
}) {
  const [v, setV] = useState(initial);
  const field = (key: keyof HypothesisFields, label: string) => (
    <div className="field"><label htmlFor={`hf-${key}`}>{label}</label>
      <input id={`hf-${key}`} className="input sm" value={v[key]} onChange={(e) => setV({ ...v, [key]: e.target.value })} /></div>
  );
  return (
    <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); onSubmit(v); }}>
      <div className="field"><label htmlFor="hf-statement">Statement</label>
        <textarea id="hf-statement" className="textarea" required minLength={5} value={v.statement} onChange={(e) => setV({ ...v, statement: e.target.value })}
          placeholder="Perceived authenticity is positively associated with purchase intention." /></div>
      <div className="grid grid-4">
        {field("iv", "Independent variable")}{field("dv", "Dependent variable")}{field("mediator", "Mediator (optional)")}{field("moderator", "Moderator (optional)")}
      </div>
      <div className="grid grid-2">
        <div className="field"><label htmlFor="hf-dir">Expected direction</label>
          <select id="hf-dir" className="select sm" value={v.expected_direction} onChange={(e) => setV({ ...v, expected_direction: e.target.value })}>
            <option value="positive">Positive</option><option value="negative">Negative</option><option value="difference">Difference between groups</option><option value="none">No effect</option>
          </select></div>
        {field("rationale", "Rationale (theory or prior evidence)")}
      </div>
      <div className="row">
        <button className="btn sm primary" disabled={busy}>{submitLabel}</button>
        {onCancel && <button type="button" className="btn sm ghost" onClick={onCancel}>Cancel</button>}
      </div>
    </form>
  );
}

function NewHypothesis({ pid }: { pid: string }) {
  const toast = useToast();
  const [key, setKey] = useState(0);
  const create = useProjectMutation(pid, (v: HypothesisFields) => api.post(`/projects/${pid}/hypotheses`, v));
  return (
    <details className="disclosure" style={{ marginTop: 6 }}>
      <summary><Icon name="plus" size={12} />Add a hypothesis</summary>
      <HypothesisForm key={key} busy={create.isPending} submitLabel="Add hypothesis"
        initial={{ statement: "", iv: "", dv: "", mediator: "", moderator: "", expected_direction: "positive", rationale: "" }}
        onSubmit={(v) => create.mutate(v, { onSuccess: () => { toast("Hypothesis added."); setKey((k) => k + 1); }, onError: (e) => toast(errorMessage(e), "error") })} />
    </details>
  );
}

function SampleSizeCalculator() {
  const toast = useToast();
  const [kind, setKind] = useState("proportion");
  const [form, setForm] = useState({ p: 50, margin: 5, confidence: 95, population: "", sd: 1, meanMargin: 0.1, n: 400, baseline: 5, mde: 20, power: 80 });
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const run = async () => {
    const body: Record<string, unknown> = { kind, confidence: form.confidence / 100, population: form.population ? Number(form.population) : null };
    if (kind === "proportion") Object.assign(body, { p: form.p / 100, margin: form.margin / 100 });
    if (kind === "mean") Object.assign(body, { sd: form.sd, margin: form.meanMargin });
    if (kind === "margin_of_error") Object.assign(body, { n: form.n, p: form.p / 100 });
    if (kind === "ab_test") Object.assign(body, { baseline: form.baseline / 100, mde_relative: form.mde / 100, power: form.power / 100 });
    try {
      setResult(await api.post<Record<string, unknown>>("/tools/sample-size", body));
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  };
  const num_ = (key: keyof typeof form, label: string, step = "any") => (
    <div className="field"><label htmlFor={`ss-${key}`}>{label}</label>
      <input id={`ss-${key}`} className="input sm" type="number" step={step} value={form[key]} onChange={(e) => setForm({ ...form, [key]: e.target.value === "" ? "" : Number(e.target.value) })} /></div>
  );
  return (
    <Card title="Sample size calculator" subtitle="Closed-form formulas with finite population correction. Use it to check the plan or size a new wave.">
      <div className="stack-sm">
        <div className="grid grid-4">
          <div className="field"><label htmlFor="ss-kind">I want to</label>
            <select id="ss-kind" className="select sm" value={kind} onChange={(e) => { setKind(e.target.value); setResult(null); }}>
              <option value="proportion">Estimate a share (for example % willing to pay)</option>
              <option value="mean">Estimate an average</option>
              <option value="margin_of_error">Find the margin of error for a sample</option>
              <option value="ab_test">Size an A/B test</option>
            </select></div>
          {kind === "proportion" && <>{num_("p", "Expected share (%)")}{num_("margin", "Margin of error (± points)")}</>}
          {kind === "mean" && <>{num_("sd", "Standard deviation")}{num_("meanMargin", "Margin of error (same unit)")}</>}
          {kind === "margin_of_error" && <>{num_("n", "Sample size", "1")}{num_("p", "Expected share (%)")}</>}
          {kind === "ab_test" && <>{num_("baseline", "Current conversion (%)")}{num_("mde", "Smallest relative lift (%)")}</>}
        </div>
        <div className="grid grid-4">
          {kind !== "ab_test" ? <>{num_("confidence", "Confidence (%)")}{num_("population", "Population size (optional)", "1")}</> : num_("power", "Power (%)")}
          <div style={{ alignSelf: "end" }}><button className="btn sm primary" onClick={run}>Calculate</button></div>
        </div>
        {result && (
          <Callout tone="good">
            {kind === "ab_test" ? <><strong>{num(result.n_per_arm)} per variant</strong> ({num(result.total)} in total) to detect a change from {pct(result.baseline, 1)} to {pct(result.target, 1)}.</>
              : kind === "margin_of_error" ? <><strong>±{pct(result.margin_of_error, 1)}</strong> margin of error with n = {num(result.n)}.</>
                : <><strong>n = {num(result.n)}</strong> completed responses{result.population ? ` for a population of ${num(result.population)}` : ""} (n = {num(result.n_infinite)} without the population correction). <span className="small muted">{String(result.formula ?? "")}</span></>}
          </Callout>
        )}
      </div>
    </Card>
  );
}

function HypothesisRow({ pid, h, onEvidence }: { pid: string; h: Hypothesis; onEvidence: (id: string) => void }) {
  const toast = useToast();
  const [editing, setEditing] = useState(false);
  const decide = useProjectMutation(pid, (approve: boolean) => api.post(`/projects/${pid}/hypotheses/${h.id}/verdict/decide`, { approve }));
  const update = useProjectMutation(pid, (v: HypothesisFields) => api.patch(`/projects/${pid}/hypotheses/${h.id}`, v));
  const proposed = h.status.startsWith("proposed_");
  const decided = ["supported", "not_supported", "inconclusive"].includes(h.status);
  if (editing) {
    return (
      <div className="list-item"><div className="grow">
        <HypothesisForm initial={h} busy={update.isPending} submitLabel="Save" onCancel={() => setEditing(false)}
          onSubmit={(v) => update.mutate(v, { onSuccess: () => { toast(`${h.code} saved.`); setEditing(false); }, onError: (e) => toast(errorMessage(e), "error") })} />
      </div></div>
    );
  }
  return (
    <div className="list-item">
      <span className="chip code" style={{ minWidth: 30, justifyContent: "center" }}>{h.code}</span>
      <div className="grow stack-sm">
        <div>{h.statement}</div>
        <div className="small muted">
          {h.iv} to {h.dv}{h.mediator ? ` through ${h.mediator}` : ""} · expected {h.expected_direction}
        </div>
        {h.verdict_rationale && <div className="small secondary">{h.verdict_rationale}</div>}
        {h.verdict_evidence.length > 0 && (
          <div className="row" style={{ gap: 4 }}>
            <span className="small muted">Evidence:</span>
            {h.verdict_evidence.map((id) => <button key={id} className="chip" onClick={() => onEvidence(id)}>view</button>)}
          </div>
        )}
      </div>
      <div className="stack-sm" style={{ alignItems: "flex-end" }}>
        <StatusBadge status={h.status} />
        {!decided && <button className="btn ghost sm" onClick={() => setEditing(true)}>Edit</button>}
        {proposed && (
          <div className="row" style={{ gap: 4 }}>
            <button className="btn sm good" onClick={() => decide.mutate(true, { onSuccess: () => toast(`${h.code} verdict approved.`), onError: (e) => toast(errorMessage(e), "error") })}>
              <Icon name="check" size={12} />Approve</button>
            <button className="btn sm danger" onClick={() => decide.mutate(false, { onSuccess: () => toast(`${h.code} verdict rejected.`) })}>Reject</button>
          </div>
        )}
      </div>
    </div>
  );
}

function VariableDictionary({ pid }: { pid: string }) {
  const { data } = useResearch(pid);
  const [filter, setFilter] = useState("");
  if (!data?.variables.length) return null;
  const rows = data.variables.filter((v) => !filter || `${v.name} ${v.label} ${v.role} ${v.var_type}`.toLowerCase().includes(filter.toLowerCase()));
  const constructs = Object.fromEntries(data.constructs.map((c) => [c.id, c.code]));
  return (
    <Card title="Variable dictionary" subtitle={`${data.variables.length} variables. Names match the questionnaire and the uploaded data.`}
      actions={<input className="input sm" placeholder="Filter" value={filter} onChange={(e) => setFilter(e.target.value)} aria-label="Filter variables" />}>
      <div className="table-wrap" style={{ maxHeight: 420 }}>
        <table className="table">
          <thead><tr><th>Variable</th><th>Label</th><th>Type</th><th>Role</th><th>Construct</th><th>Scale</th></tr></thead>
          <tbody>
            {rows.map((v) => (
              <tr key={v.id}>
                <td><code>{v.name}</code></td>
                <td className="small">{v.label}</td>
                <td>{v.var_type}</td>
                <td>{sentence(v.role)}</td>
                <td>{v.construct_id ? constructs[v.construct_id] : ""}</td>
                <td className="num">{v.scale_min !== null ? `${v.scale_min} to ${v.scale_max}` : ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
