import { Fragment, useState, type ReactNode } from "react";
import { api, download, errorMessage, openHtml } from "../../api/client";
import { useEvidence, useExperiments, useProjectMutation, useReport, useReports } from "../../api/hooks";
import type { Report, ReportBlock } from "../../api/types";
import { EvidenceModal } from "../../components/domain";
import { Callout, Card, Empty, Icon, ModelBadge, StatusBadge, useToast } from "../../components/ui";
import { dateTime, sentence } from "../../lib/format";

export const REPORT_KINDS: Record<string, { label: string; description: string }> = {
  research_report: { label: "Research report", description: "Full report: method, sample, findings, hypotheses, limitations and the evidence register." },
  executive_summary: { label: "Executive summary", description: "One page for decision makers: key findings and recommendations with citations." },
  decision_memo: { label: "Decision memo", description: "The strategy decision, the scenarios behind it and the evidence it rests on." },
  methods_appendix: { label: "Methods appendix", description: "Every analysis with parameters, assumption checks and data versions." },
  experiment_brief: { label: "Experiment brief", description: "Hypothesis, metric, sample size and duration for one A/B test." },
};

/** Render **bold** spans inside report text (the only inline markup the builder emits). */
function inline(text: string): ReactNode {
  const parts = text.split(/\*\*(.+?)\*\*/g);
  return parts.map((p, i) => (i % 2 ? <strong key={i}>{p}</strong> : <Fragment key={i}>{p}</Fragment>));
}

export default function ReportBuilder({ pid, kinds = ["research_report", "executive_summary", "decision_memo", "methods_appendix"] }: {
  pid: string; kinds?: string[];
}) {
  const { data: reports } = useReports(pid);
  const [chosen, setChosen] = useState<string | undefined>();
  const selected = chosen ?? reports?.[0]?.id;
  return (
    <div className="grid grid-sidebar">
      <div className="stack">
        <Generate pid={pid} kinds={kinds} onCreated={setChosen} />
        <Card title="Reports">
          {!reports?.length ? <span className="small muted">No reports yet.</span> : (
            <div className="stack-sm">
              {reports.map((r) => (
                <button key={r.id} onClick={() => setChosen(r.id)} className="list-item"
                  style={{ textAlign: "left", width: "100%", border: 0, borderRadius: 8, padding: "8px 10px", cursor: "pointer", color: "inherit",
                    background: selected === r.id ? "var(--accent-soft)" : "transparent" }}>
                  <div className="grow">
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{REPORT_KINDS[r.kind]?.label ?? sentence(r.kind)}</div>
                    <div className="small muted">{dateTime(r.created_at)}</div>
                  </div>
                  <StatusBadge status={r.status} />
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>
      {selected ? <ReportView pid={pid} rid={selected} onDeleted={() => setChosen(undefined)} /> : <Empty title="Generate a report">Reports are assembled from approved and draft evidence. Drafts are labeled.</Empty>}
    </div>
  );
}

function Generate({ pid, kinds, onCreated }: { pid: string; kinds: string[]; onCreated: (id: string) => void }) {
  const toast = useToast();
  const [kind, setKind] = useState(kinds[0]);
  const [experimentId, setExperimentId] = useState("");
  const { data: experiments } = useExperiments(pid);
  const create = useProjectMutation(pid, () => api.post<Report>(`/projects/${pid}/reports`, { kind, experiment_id: kind === "experiment_brief" ? experimentId : null }));
  return (
    <Card title="New report">
      <div className="stack-sm">
        <div className="field">
          <label htmlFor="rep-kind">Type</label>
          <select id="rep-kind" className="select" value={kind} onChange={(e) => setKind(e.target.value)}>
            {kinds.map((k) => <option key={k} value={k}>{REPORT_KINDS[k]?.label ?? sentence(k)}</option>)}
          </select>
          <span className="hint">{REPORT_KINDS[kind]?.description}</span>
        </div>
        {kind === "experiment_brief" && (
          <div className="field">
            <label htmlFor="rep-exp">Experiment</label>
            <select id="rep-exp" className="select" value={experimentId} onChange={(e) => setExperimentId(e.target.value)}>
              <option value="">Choose an experiment</option>
              {(experiments ?? []).map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
            </select>
          </div>
        )}
        <div>
          <button className="btn primary" disabled={create.isPending || (kind === "experiment_brief" && !experimentId)}
            onClick={() => create.mutate(undefined, { onSuccess: (r) => { toast("Report generated."); onCreated(r.id); }, onError: (e) => toast(errorMessage(e), "error") })}>
            <Icon name="reports" size={14} />{create.isPending ? "Generating" : "Generate"}
          </button>
        </div>
      </div>
    </Card>
  );
}

function ReportView({ pid, rid, onDeleted }: { pid: string; rid: string; onDeleted: () => void }) {
  const { data: report } = useReport(pid, rid);
  const { data: evidence } = useEvidence(pid);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const toast = useToast();
  const finalize = useProjectMutation(pid, () => api.post(`/projects/${pid}/reports/${rid}/finalize`));
  const remove = useProjectMutation(pid, () => api.del(`/projects/${pid}/reports/${rid}`));
  if (!report?.document) return <Card title="Loading"><span className="muted">Loading</span></Card>;
  const codes = new Map((evidence ?? []).map((e) => [e.code, e.id]));
  const cite = (list?: string[]) => list && list.length > 0 && (
    <span className="row" style={{ display: "inline-flex", gap: 3, marginLeft: 6 }}>
      {list.map((c) => codes.get(c)
        ? <button key={c} className="chip code" onClick={() => setEvidenceId(codes.get(c) as string)}>{c}</button>
        : <span key={c} className="chip code">{c}</span>)}
    </span>
  );
  const doc = report.document;
  const slug = report.title.toLowerCase().replace(/[^a-z0-9]+/g, "_").slice(0, 50);
  return (
    <Card title={doc.title} subtitle={`${doc.subtitle} · version ${report.version} · ${dateTime(doc.generated_at)}`}
      actions={<>
        <StatusBadge status={report.status} />
        <button className="btn sm" onClick={() => download(`/projects/${pid}/reports/${rid}/export?format=md`, `${slug}.md`).catch((e) => toast(errorMessage(e), "error"))}>
          <Icon name="download" size={14} />Markdown</button>
        <button className="btn sm" onClick={() => openHtml(`/projects/${pid}/reports/${rid}/export?format=html`)}>
          <Icon name="external" size={14} />Printable HTML</button>
        {report.status !== "final" && (
          <button className="btn sm good" disabled={finalize.isPending} onClick={() => window.confirm("Finalize this report? Final reports are locked; generate a new version to change them.")
            && finalize.mutate(undefined, { onSuccess: () => toast("Report finalized."), onError: (e) => toast(errorMessage(e), "error") })}>
            <Icon name="lock" size={14} />Finalize</button>
        )}
        <button className="btn ghost icon sm" aria-label="Delete report" onClick={() => window.confirm("Delete this report?")
          && remove.mutate(undefined, { onSuccess: () => { toast("Report deleted."); onDeleted(); }, onError: (e) => toast(errorMessage(e), "error") })}><Icon name="trash" size={14} /></button>
      </>}>
      <article className="report-doc">
        {doc.blocks.map((b, i) => <Block key={i} block={b} cite={cite} />)}
      </article>
      <EvidenceModal pid={pid} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />
    </Card>
  );
}

function Block({ block: b, cite }: { block: ReportBlock; cite: (list?: string[]) => ReactNode }) {
  switch (b.type) {
    case "heading":
      return b.level === 3 ? <h3>{b.text}</h3> : <h2>{b.text}</h2>;
    case "paragraph":
      return <p>{inline(b.text ?? "")}{cite(b.citations)}{b.model_generated && <span style={{ marginLeft: 6 }}><ModelBadge /></span>}</p>;
    case "callout":
      return <div style={{ margin: "12px 0" }}><Callout tone={b.tone === "warning" ? "warning" : b.tone === "critical" ? "critical" : "info"}>{inline(b.text ?? "")}</Callout></div>;
    case "list":
      return <ul>{(b.items ?? []).map((it, i) => <li key={i}>{inline(it.text ?? "")}{cite(it.citations)}</li>)}</ul>;
    case "table":
      return (
        <div className="table-wrap" style={{ margin: "10px 0" }}>
          <table className="table">
            <thead><tr>{(b.columns ?? []).map((c) => <th key={c}>{c}</th>)}</tr></thead>
            <tbody>{(b.rows ?? []).map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j} className={typeof v === "number" ? "num" : ""}>{String(v)}</td>)}</tr>)}</tbody>
          </table>
        </div>
      );
    case "evidence_register":
      return (
        <div className="table-wrap" style={{ margin: "10px 0" }}>
          <table className="table">
            <thead><tr><th>Code</th><th>Finding</th><th>Design</th><th>Strength</th><th>Source</th></tr></thead>
            <tbody>
              {(b.items ?? []).map((it) => (
                <tr key={it.code}>
                  <td><span className="chip code">{it.code}</span></td>
                  <td><div style={{ fontWeight: 600 }}>{it.title}</div><div className="small secondary">{it.statement}</div></td>
                  <td className="small">{sentence(it.design ?? "")}</td>
                  <td><span className={`chip strength-${it.strength}`}>{it.strength}</span></td>
                  <td className="small secondary">{it.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    default:
      return null;
  }
}
