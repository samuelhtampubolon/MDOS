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
        </div>
      </Card>
      <div className="grid grid-2">
        <Card title="Measurement model" subtitle="Constructs from the curated library, with source citations.">
          <div className="stack-sm">
            {data.constructs.map((c) => (
              <div key={c.id} className="list-item" style={{ padding: "6px 0" }}>
                <span className="chip">{c.code}</span>
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
      <VariableDictionary pid={pid} />
      <EvidenceModal pid={pid} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />
    </div>
  );
}

function HypothesisRow({ pid, h, onEvidence }: { pid: string; h: Hypothesis; onEvidence: (id: string) => void }) {
  const toast = useToast();
  const decide = useProjectMutation(pid, (approve: boolean) => api.post(`/projects/${pid}/hypotheses/${h.id}/verdict/decide`, { approve }));
  const proposed = h.status.startsWith("proposed_");
  return (
    <div className="list-item">
      <span className="chip" style={{ minWidth: 30, justifyContent: "center" }}>{h.code}</span>
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
