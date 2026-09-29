import { useState, type FormEvent } from "react";
import { api, ApiError, errorMessage } from "../../api/client";
import { useEvidence, useGraph, useInsights, useProjectMutation, useRecommendations } from "../../api/hooks";
import type { Evidence, Insight, Recommendation } from "../../api/types";
import { EvidenceModal } from "../../components/domain";
import { LineageGraph } from "../../components/LineageGraph";
import { Callout, Card, Empty, EvidenceChips, Icon, ModelBadge, OriginBadge, StatusBadge, Tabs, useToast } from "../../components/ui";
import { num, pValue, sentence } from "../../lib/format";

type View = "insights" | "recommendations" | "register" | "graph";

export default function Insights({ pid }: { pid: string }) {
  const [view, setView] = useState<View>("insights");
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const { data: insights } = useInsights(pid);
  const { data: recs } = useRecommendations(pid);
  const { data: evidence } = useEvidence(pid);
  return (
    <div className="stack">
      <Callout icon="lock">
        <strong>Quality gates.</strong> Insights and recommendations must cite evidence. Causal words such as "causes", "drives" or
        "increases" are blocked unless the cited evidence comes from an experiment. Agent drafts stay drafts until a person approves them.
      </Callout>
      <Tabs<View> value={view} onChange={setView} tabs={[
        { key: "insights", label: `Insights (${insights?.length ?? 0})` },
        { key: "recommendations", label: `Recommendations (${recs?.length ?? 0})` },
        { key: "register", label: `Evidence register (${evidence?.length ?? 0})` },
        { key: "graph", label: "Evidence graph" },
      ]} />
      {view === "insights" && <InsightList pid={pid} insights={insights ?? []} evidence={evidence ?? []} onEvidence={setEvidenceId} />}
      {view === "recommendations" && <RecommendationList pid={pid} recs={recs ?? []} evidence={evidence ?? []} onEvidence={setEvidenceId} />}
      {view === "register" && <EvidenceRegister pid={pid} evidence={evidence ?? []} onOpen={setEvidenceId} />}
      {view === "graph" && <GraphView pid={pid} />}
      <EvidenceModal pid={pid} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />
    </div>
  );
}

function DecideButtons({ pending, onDecide }: { pending: boolean; onDecide: (decision: "approved" | "rejected") => void }) {
  return (
    <div className="row" style={{ gap: 4 }}>
      <button className="btn sm good" disabled={pending} onClick={() => onDecide("approved")}><Icon name="check" size={12} />Approve</button>
      <button className="btn sm ghost danger" disabled={pending} onClick={() => onDecide("rejected")}><Icon name="x" size={12} />Reject</button>
    </div>
  );
}

function InsightList({ pid, insights, evidence, onEvidence }: { pid: string; insights: Insight[]; evidence: Evidence[]; onEvidence: (id: string) => void }) {
  return (
    <div className="stack">
      {!insights.length ? <Empty title="No insights yet">Run the analysis agents, or write one below from saved evidence.</Empty> : (
        insights.map((i) => <InsightCard key={i.id} pid={pid} insight={i} onEvidence={onEvidence} />)
      )}
      <NewInsight pid={pid} evidence={evidence} />
    </div>
  );
}

/** Copies the insight with its evidence codes, ready to paste into a deck or an email. */
function CopyCitation({ insight }: { insight: Insight }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    const codes = insight.evidence.map((e) => e.code).join(", ");
    try {
      await navigator.clipboard.writeText(`${insight.code} ${insight.title}: ${insight.statement}${codes ? ` (Evidence ${codes})` : ""}`);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  };
  return (
    <button className="btn sm ghost" onClick={copy} aria-live="polite">
      {copied ? <span className="copied">Copied</span> : <><Icon name="link" size={12} />Copy with evidence</>}
    </button>
  );
}

function InsightCard({ pid, insight, onEvidence }: { pid: string; insight: Insight; onEvidence: (id: string) => void }) {
  const toast = useToast();
  const [error, setError] = useState("");
  const decide = useProjectMutation(pid, (decision: string) => api.post(`/projects/${pid}/insights/${insight.id}/decide`, { decision }));
  const run = (decision: "approved" | "rejected") => decide.mutate(decision, {
    onSuccess: () => { setError(""); toast(`${insight.code} ${decision}.`); },
    onError: (e) => setError(errorMessage(e)),
  });
  return (
    <Card title={<span className="row" style={{ gap: 8 }}><span className="mono muted">{insight.code}</span>{insight.title}</span>}
      actions={<>{insight.is_model_generated && <ModelBadge />}{insight.status !== "draft" && <StatusBadge status={insight.status} />}</>}>
      <div className="stack-sm">
        <p className="measure" style={{ margin: 0 }}>{insight.statement}</p>
        {insight.implication && <div className="measure"><span className="small muted">So what: </span>{insight.implication}</div>}
        {insight.uncertainty && <div className="small secondary measure"><Icon name="alert" size={12} /> {insight.uncertainty}</div>}
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="row" style={{ gap: 8 }}>
            <span className="small muted">Evidence</span>
            <EvidenceChips evidence={insight.evidence} onOpen={onEvidence} />
            <span className="small muted">{sentence(insight.confidence)} confidence</span>
          </div>
          <div className="row" style={{ gap: 4 }}>
            <CopyCitation insight={insight} />
            {insight.status === "draft" && <DecideButtons pending={decide.isPending} onDecide={run} />}
          </div>
        </div>
        {error && <Callout tone="critical">{error}</Callout>}
      </div>
    </Card>
  );
}

function EvidencePicker({ evidence, value, onChange }: { evidence: Evidence[]; value: string[]; onChange: (ids: string[]) => void }) {
  return (
    <div className="field">
      <label>Supporting evidence</label>
      <div className="table-wrap" style={{ maxHeight: 200 }}>
        {evidence.map((e) => (
          <label key={e.id} className="list-item" style={{ padding: "4px 6px", cursor: "pointer" }}>
            <input type="checkbox" checked={value.includes(e.id)} onChange={(ev) => onChange(ev.target.checked ? [...value, e.id] : value.filter((x) => x !== e.id))} />
            <span className={`chip code strength-${e.strength}`}>{e.code}</span>
            <span className="small grow">{e.title}</span>
            <span className="small muted">{sentence(e.design)}</span>
          </label>
        ))}
      </div>
      <span className="hint">{value.length} selected. Observational evidence supports associations only.</span>
    </div>
  );
}

function NewInsight({ pid, evidence }: { pid: string; evidence: Evidence[] }) {
  const toast = useToast();
  const empty = { title: "", statement: "", implication: "", uncertainty: "", confidence: "medium", evidence_ids: [] as string[] };
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const create = useProjectMutation(pid, (body: typeof empty) => api.post(`/projects/${pid}/insights`, body));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    create.mutate(form, {
      onSuccess: () => { toast("Insight saved as a draft."); setForm(empty); setError(""); setSuggestion(""); },
      onError: (err) => {
        setError(errorMessage(err));
        setSuggestion(err instanceof ApiError && typeof err.details.suggestion === "string" ? err.details.suggestion : "");
      },
    });
  };
  return (
    <details className="disclosure card" style={{ padding: 16 }}>
      <summary><Icon name="plus" size={12} />Write an insight</summary>
      <form className="stack-sm" onSubmit={submit}>
        <div className="field"><label htmlFor="in-title">Title</label>
          <input id="in-title" className="input" required minLength={3} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
        <div className="field"><label htmlFor="in-statement">Statement</label>
          <textarea id="in-statement" className="textarea" required minLength={5} value={form.statement}
            placeholder="Associational wording, for example: visitors who rate authenticity higher also report higher purchase intention."
            onChange={(e) => setForm({ ...form, statement: e.target.value })} /></div>
        <div className="grid grid-2">
          <div className="field"><label htmlFor="in-impl">Implication</label>
            <input id="in-impl" className="input" value={form.implication} onChange={(e) => setForm({ ...form, implication: e.target.value })} /></div>
          <div className="field"><label htmlFor="in-unc">Uncertainty</label>
            <input id="in-unc" className="input" value={form.uncertainty} onChange={(e) => setForm({ ...form, uncertainty: e.target.value })} /></div>
        </div>
        <div className="field" style={{ maxWidth: 220 }}><label htmlFor="in-conf">Confidence</label>
          <select id="in-conf" className="select" value={form.confidence} onChange={(e) => setForm({ ...form, confidence: e.target.value })}>
            <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
          </select></div>
        <EvidencePicker evidence={evidence} value={form.evidence_ids} onChange={(ids) => setForm({ ...form, evidence_ids: ids })} />
        {error && (
          <Callout tone="critical">
            {error}
            {suggestion && (
              <div style={{ marginTop: 6 }}>
                <span className="small">Associational wording: "{suggestion}"</span>{" "}
                <button type="button" className="btn sm" onClick={() => { setForm({ ...form, statement: suggestion }); setError(""); setSuggestion(""); }}>
                  Use this wording</button>
              </div>
            )}
          </Callout>
        )}
        <div><button className="btn primary" disabled={create.isPending}>Save draft insight</button></div>
      </form>
    </details>
  );
}

function RecommendationList({ pid, recs, evidence, onEvidence }: { pid: string; recs: Recommendation[]; evidence: Evidence[]; onEvidence: (id: string) => void }) {
  return (
    <div className="stack">
      {!recs.length ? <Empty title="No recommendations yet">The Insight agent drafts recommendations from approved-quality evidence.</Empty> : (
        recs.map((r) => <RecommendationCard key={r.id} pid={pid} rec={r} onEvidence={onEvidence} />)
      )}
      <NewRecommendation pid={pid} evidence={evidence} />
    </div>
  );
}

function RecommendationCard({ pid, rec, onEvidence }: { pid: string; rec: Recommendation; onEvidence: (id: string) => void }) {
  const toast = useToast();
  const [error, setError] = useState("");
  const decide = useProjectMutation(pid, (decision: string) => api.post(`/projects/${pid}/recommendations/${rec.id}/decide`, { decision }));
  return (
    <Card title={<span className="row" style={{ gap: 8 }}><span className="mono muted">{rec.code}</span>{sentence(rec.module)} recommendation</span>}
      actions={<>{rec.is_model_generated && <ModelBadge />}<StatusBadge status={rec.priority} label={`${sentence(rec.priority)} priority`} /><StatusBadge status={rec.status} /></>}>
      <div className="stack-sm">
        <p className="measure" style={{ margin: 0 }}>{rec.statement}</p>
        {rec.rationale && <div className="small secondary">{rec.rationale}</div>}
        <div className="row" style={{ justifyContent: "space-between" }}>
          <div className="row" style={{ gap: 6 }}><span className="small muted">Evidence</span><EvidenceChips evidence={rec.evidence} onOpen={onEvidence} /></div>
          {rec.status === "draft" && <DecideButtons pending={decide.isPending} onDecide={(d) => decide.mutate(d, {
            onSuccess: () => { setError(""); toast(`${rec.code} ${d}.`); }, onError: (e) => setError(errorMessage(e)),
          })} />}
        </div>
        {error && <Callout tone="critical">{error}</Callout>}
      </div>
    </Card>
  );
}

function NewRecommendation({ pid, evidence }: { pid: string; evidence: Evidence[] }) {
  const toast = useToast();
  const empty = { statement: "", rationale: "", module: "research", priority: "medium", evidence_ids: [] as string[] };
  const [form, setForm] = useState(empty);
  const [error, setError] = useState("");
  const create = useProjectMutation(pid, (body: typeof empty) => api.post(`/projects/${pid}/recommendations`, body));
  return (
    <details className="disclosure card" style={{ padding: 16 }}>
      <summary><Icon name="plus" size={12} />Write a recommendation</summary>
      <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); create.mutate(form, {
        onSuccess: () => { toast("Recommendation saved as a draft."); setForm(empty); setError(""); }, onError: (err) => setError(errorMessage(err)),
      }); }}>
        <div className="field"><label htmlFor="rec-s">Recommendation</label>
          <textarea id="rec-s" className="textarea" required minLength={5} value={form.statement} onChange={(e) => setForm({ ...form, statement: e.target.value })} /></div>
        <div className="field"><label htmlFor="rec-r">Rationale</label>
          <input id="rec-r" className="input" value={form.rationale} onChange={(e) => setForm({ ...form, rationale: e.target.value })} /></div>
        <div className="grid grid-2">
          <div className="field"><label htmlFor="rec-m">Module</label>
            <select id="rec-m" className="select" value={form.module} onChange={(e) => setForm({ ...form, module: e.target.value })}>
              <option value="research">Research</option><option value="strategy">Strategy</option><option value="journey">Journey</option>
            </select></div>
          <div className="field"><label htmlFor="rec-p">Priority</label>
            <select id="rec-p" className="select" value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}>
              <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
            </select></div>
        </div>
        <EvidencePicker evidence={evidence} value={form.evidence_ids} onChange={(ids) => setForm({ ...form, evidence_ids: ids })} />
        {error && <Callout tone="critical">{error}</Callout>}
        <div><button className="btn primary" disabled={create.isPending}>Save draft recommendation</button></div>
      </form>
    </details>
  );
}

function EvidenceRegister({ pid, evidence, onOpen }: { pid: string; evidence: Evidence[]; onOpen: (id: string) => void }) {
  const [filter, setFilter] = useState({ text: "", strength: "", origin: "" });
  const rows = evidence.filter((e) => (!filter.strength || e.strength === filter.strength) && (!filter.origin || e.origin === filter.origin)
    && (!filter.text || `${e.code} ${e.title} ${e.statement}`.toLowerCase().includes(filter.text.toLowerCase())));
  const origins = Array.from(new Set(evidence.map((e) => e.origin)));
  return (
    <div className="stack">
      <Card title="Evidence register" subtitle="Every finding the system can cite, with its origin, design, strength and statistics."
        actions={<>
          <input className="input sm" placeholder="Search" aria-label="Search evidence" value={filter.text} onChange={(e) => setFilter({ ...filter, text: e.target.value })} />
          <select className="select sm" aria-label="Filter by strength" value={filter.strength} onChange={(e) => setFilter({ ...filter, strength: e.target.value })}>
            <option value="">Any strength</option>{["strong", "moderate", "weak", "insufficient"].map((s) => <option key={s} value={s}>{sentence(s)}</option>)}
          </select>
          <select className="select sm" aria-label="Filter by origin" value={filter.origin} onChange={(e) => setFilter({ ...filter, origin: e.target.value })}>
            <option value="">Any origin</option>{origins.map((o) => <option key={o} value={o}>{sentence(o)}</option>)}
          </select>
        </>}>
        {!evidence.length ? <Empty title="No evidence yet">Save evidence candidates from the Analysis studio, or add an external source below.</Empty> : (
          <div className="table-wrap" style={{ maxHeight: 560 }}>
            <table className="table">
              <thead><tr><th>Code</th><th>Finding</th><th>Origin</th><th>Design</th><th>Strength</th><th className="num">n</th><th className="num">p</th><th className="num">Effect</th></tr></thead>
              <tbody>
                {rows.map((e) => (
                  <tr key={e.id} onClick={() => onOpen(e.id)} style={{ cursor: "pointer" }}>
                    <td><button className="chip code" onClick={(ev) => { ev.stopPropagation(); onOpen(e.id); }}>{e.code}</button></td>
                    <td><div style={{ fontWeight: 600 }}>{e.title}</div><div className="small secondary">{e.statement.length > 180 ? `${e.statement.slice(0, 179)}…` : e.statement}</div></td>
                    <td><OriginBadge origin={e.origin} /></td>
                    <td className="small">{sentence(e.design)}</td>
                    <td><span className={`chip strength-${e.strength}`}>{e.strength}</span></td>
                    <td className="num">{e.n ?? ""}</td>
                    <td className="num small">{e.p_value !== null ? pValue(e.p_value).replace("p ", "") : ""}</td>
                    <td className="num small">{e.effect_size !== null ? `${num(e.effect_size, 2)}${e.effect_label ? ` ${e.effect_label}` : ""}` : ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
      <ExternalEvidence pid={pid} />
    </div>
  );
}

function ExternalEvidence({ pid }: { pid: string }) {
  const toast = useToast();
  const empty = { title: "", statement: "", citation: "", url: "", strength: "weak", design: "external", origin: "external" };
  const [form, setForm] = useState(empty);
  const create = useProjectMutation(pid, (body: typeof empty) => api.post(`/projects/${pid}/evidence`, body));
  return (
    <details className="disclosure card" style={{ padding: 16 }}>
      <summary><Icon name="plus" size={12} />Add external evidence (statistics office data, published studies, industry reports)</summary>
      <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); create.mutate(form, {
        onSuccess: () => { toast("External evidence added."); setForm(empty); }, onError: (err) => toast(errorMessage(err), "error"),
      }); }}>
        <div className="grid grid-2">
          <div className="field"><label htmlFor="ex-t">Title</label>
            <input id="ex-t" className="input" required minLength={3} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
          <div className="field"><label htmlFor="ex-c">Citation</label>
            <input id="ex-c" className="input" placeholder="BPS Sumatera Utara (2025), table 4.2" value={form.citation} onChange={(e) => setForm({ ...form, citation: e.target.value })} /></div>
        </div>
        <div className="field"><label htmlFor="ex-s">What the source says</label>
          <textarea id="ex-s" className="textarea" required minLength={5} value={form.statement} onChange={(e) => setForm({ ...form, statement: e.target.value })} /></div>
        <div className="grid grid-3">
          <div className="field"><label htmlFor="ex-u">Link</label>
            <input id="ex-u" className="input" type="url" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} /></div>
          <div className="field"><label htmlFor="ex-d">Design</label>
            <select id="ex-d" className="select" value={form.design} onChange={(e) => setForm({ ...form, design: e.target.value })}>
              <option value="external">External statistic or report</option><option value="observational">Observational data</option>
              <option value="qualitative">Qualitative</option><option value="cross_sectional_survey">Survey</option><option value="experiment">Experiment</option>
            </select></div>
          <div className="field"><label htmlFor="ex-st">Strength</label>
            <select id="ex-st" className="select" value={form.strength} onChange={(e) => setForm({ ...form, strength: e.target.value })}>
              {["strong", "moderate", "weak", "insufficient"].map((s) => <option key={s} value={s}>{sentence(s)}</option>)}
            </select></div>
        </div>
        <div><button className="btn primary" disabled={create.isPending}>Add evidence</button></div>
      </form>
    </details>
  );
}

function GraphView({ pid }: { pid: string }) {
  const { data } = useGraph(pid);
  if (!data) return null;
  if (!data.nodes.length) return <Empty title="Nothing to trace yet">The graph fills in as you upload data, run analyses and save evidence.</Empty>;
  return <Card><LineageGraph data={data} /></Card>;
}
