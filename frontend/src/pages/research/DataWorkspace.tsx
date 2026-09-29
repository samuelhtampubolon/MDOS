import { useEffect, useState, type FormEvent } from "react";
import { api, errorMessage } from "../../api/client";
import { useApi, useApprovals, useDataset, useDatasets, useProjectMutation } from "../../api/hooks";
import type { ColumnProfile, Dataset, DatasetVersion, Json, QualityIssue } from "../../api/types";
import { AGENT_LABELS, ApprovalCard, StartWorkflow } from "../../components/domain";
import { Badge, Callout, Card, Empty, Icon, OriginBadge, Stat, StatusBadge, useToast } from "../../components/ui";
import { dateTime, num, pct, sentence } from "../../lib/format";

const KINDS: [string, string][] = [
  ["survey", "Survey responses"], ["reviews", "Reviews or comments"], ["sales", "Sales or bookings"],
  ["web_analytics", "Web analytics"], ["experiment", "Experiment results"], ["other", "Other"],
];

/** Plain-language description of one entry in a version's operations log. */
export function describeOperation(o: Json): string {
  const p = (o.params ?? {}) as Record<string, unknown>;
  const cols = (p.columns as string[] | undefined)?.join(", ");
  const moved = typeof o.rows_before === "number" && typeof o.rows_after === "number" && o.rows_before !== o.rows_after
    ? ` (${num((o.rows_before as number) - (o.rows_after as number))} rows removed)` : "";
  switch (o.op) {
    case "import": return `Imported ${String(p.filename ?? "file")}`;
    case "pseudonymize": return `Pseudonymized ${cols}`;
    case "drop_duplicates": return `Dropped exact duplicate rows${moved}`;
    case "set_out_of_range_missing": return `Set values of ${String(p.column)} outside ${String(p.min)} to ${String(p.max)} to missing`;
    case "drop_rows": return `Dropped rows: ${String(p.reason ?? o.reason ?? "flagged respondents")}${moved}`;
    case "drop_columns": return `Dropped columns ${cols}`;
    case "compute_scale": return `Computed ${String(p.name)} as the mean of ${(p.items as string[] | undefined)?.join(", ")}`;
    case "winsorize": return `Winsorized ${String(p.column)}`;
    default: return `${sentence(String(o.op))}${cols ? ` ${cols}` : ""}${moved}`;
  }
}

function actor(id: string | null | undefined): string {
  if (!id) return "";
  if (id.startsWith("agent:")) return `${AGENT_LABELS[id.slice(6)] ?? id.slice(6)} agent`;
  return "a person";
}

export default function DataWorkspace({ pid }: { pid: string }) {
  const { data: datasets } = useDatasets(pid);
  const [selected, setSelected] = useState<string | undefined>();
  useEffect(() => {
    if (!selected && datasets?.length) setSelected((datasets.find((d) => d.kind === "survey") ?? datasets[0]).id);
    if (selected && datasets && !datasets.some((d) => d.id === selected)) setSelected(datasets[0]?.id);
  }, [datasets, selected]);
  return (
    <div className="stack">
      <div className="grid grid-2">
        <Card title="Datasets" subtitle="Every change creates a new version with a checksum. Earlier versions stay restorable.">
          {!datasets?.length ? (
            <Empty title="No data yet">Upload survey responses exported from KoboToolbox, Google Forms or Excel, or reviews as a CSV.</Empty>
          ) : (
            <div className="stack-sm">
              {datasets.map((d) => (
                <button key={d.id} className={`list-item ${selected === d.id ? "active" : ""}`} onClick={() => setSelected(d.id)}
                  style={{ textAlign: "left", width: "100%", background: selected === d.id ? "var(--accent-soft)" : "transparent", border: 0, borderRadius: 8, padding: "8px 10px", cursor: "pointer", color: "inherit" }}>
                  <Icon name={d.kind === "reviews" ? "journey" : "data"} />
                  <div className="grow">
                    <div style={{ fontWeight: 600 }}>{d.name}</div>
                    <div className="small muted">
                      {sentence(d.kind)} · v{d.current_version?.version ?? 1} of {d.version_count ?? 1} · {num(d.current_version?.n_rows)} rows × {num(d.current_version?.n_cols)} columns
                    </div>
                  </div>
                  <OriginBadge origin={d.origin} />
                </button>
              ))}
            </div>
          )}
        </Card>
        <UploadCard pid={pid} onUploaded={setSelected} />
      </div>
      {selected && <DatasetDetail key={selected} pid={pid} did={selected} />}
    </div>
  );
}

function UploadCard({ pid, onUploaded }: { pid: string; onUploaded: (id: string) => void }) {
  const toast = useToast();
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("survey");
  const upload = useProjectMutation(pid, (form: FormData) => api.upload<Dataset>(`/projects/${pid}/datasets`, form));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    form.append("name", name || file.name);
    form.append("kind", kind);
    upload.mutate(form, {
      onSuccess: (d) => { toast(`${d.name} uploaded. Quality checks ran automatically.`); setFile(null); setName(""); onUploaded(d.id); },
      onError: (err) => toast(errorMessage(err), "error"),
    });
  };
  return (
    <Card title="Upload data" subtitle="CSV or Excel (.xlsx), up to 25 MB. Column names should match the questionnaire codes.">
      <form className="stack-sm" onSubmit={submit}>
        <div className="field">
          <label htmlFor="up-file">File</label>
          <input id="up-file" className="input" type="file" accept=".csv,.xlsx,.xls,.tsv,.txt" required
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </div>
        <div className="grid grid-2">
          <div className="field">
            <label htmlFor="up-name">Name (optional)</label>
            <input id="up-name" className="input" value={name} placeholder={file?.name ?? "Survey wave 1"} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field">
            <label htmlFor="up-kind">What is it?</label>
            <select id="up-kind" className="select" value={kind} onChange={(e) => setKind(e.target.value)}>
              {KINDS.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </div>
        </div>
        <span className="hint">Files are stored in your workspace. Personal data columns (emails, phone numbers) are flagged for pseudonymization.</span>
        <div><button className="btn primary" disabled={!file || upload.isPending}><Icon name="upload" size={14} />{upload.isPending ? "Uploading" : "Upload and check quality"}</button></div>
      </form>
    </Card>
  );
}

function DatasetDetail({ pid, did }: { pid: string; did: string }) {
  const { data: dataset } = useDataset(pid, did);
  const [versionId, setVersionId] = useState<string | undefined>();
  const toast = useToast();
  const remove = useProjectMutation(pid, () => api.del(`/projects/${pid}/datasets/${did}`));
  const scales = useProjectMutation(pid, () => api.post<DatasetVersion>(`/projects/${pid}/datasets/${did}/compute-scales`));
  if (!dataset) return null;
  const versions = [...(dataset.versions ?? [])].sort((a, b) => b.version - a.version);
  const current = versions.find((v) => v.id === dataset.current_version_id) ?? versions[0];
  const shown = versions.find((v) => v.id === versionId) ?? current;
  if (!shown) return null;
  const hasScoreItems = dataset.kind === "survey";
  return (
    <div className="stack">
      <Card title={dataset.name} subtitle={dataset.description || `${sentence(dataset.kind)} dataset`}
        actions={<>
          {hasScoreItems && (
            <button className="btn" disabled={scales.isPending} onClick={() => scales.mutate(undefined, {
              onSuccess: (v) => { toast(`Construct scores added as version ${v.version}.`); setVersionId(undefined); },
              onError: (e) => toast(errorMessage(e), "error"),
            })}>Compute construct scores</button>
          )}
          {dataset.kind === "survey" && (
            <StartWorkflow pid={pid} workflow="research_analysis" label="Run analysis agents" inputs={{ dataset_id: dataset.id }} />
          )}
          {dataset.kind === "reviews" && (
            <StartWorkflow pid={pid} workflow="journey_voc" label="Run journey agents" inputs={{ reviews_dataset_id: dataset.id }} />
          )}
          <button className="btn ghost icon" aria-label="Delete dataset" title="Delete dataset"
            onClick={() => window.confirm(`Delete ${dataset.name} and all its versions?`) && remove.mutate(undefined, {
              onSuccess: () => toast("Dataset deleted."), onError: (e) => toast(errorMessage(e), "error"),
            })}><Icon name="trash" size={16} /></button>
        </>}>
        <VersionLineage pid={pid} dataset={dataset} versions={versions} currentId={current?.id} shownId={shown.id} onShow={setVersionId} />
      </Card>
      <QualityPanel pid={pid} dataset={dataset} version={shown} isCurrent={shown.id === current?.id} />
      <ColumnDictionary columns={shown.columns} />
      <PreviewGrid pid={pid} did={did} vid={shown.id} />
    </div>
  );
}

function VersionLineage({ pid, dataset, versions, currentId, shownId, onShow }: {
  pid: string; dataset: Dataset; versions: DatasetVersion[]; currentId?: string; shownId: string; onShow: (id: string) => void;
}) {
  const toast = useToast();
  const restore = useProjectMutation(pid, (vid: string) => api.post(`/projects/${pid}/datasets/${dataset.id}/versions/${vid}/restore`));
  return (
    <div className="timeline" aria-label="Version history">
      {versions.map((v) => (
        <div key={v.id} className="timeline-step">
          <span className={`timeline-dot ${v.id === currentId ? "succeeded" : ""}`}>{v.id === currentId && <Icon name="check" size={12} />}</span>
          <div className="stack-sm" style={{ gap: 4 }}>
            <div className="row" style={{ gap: 8 }}>
              <strong>Version {v.version}</strong>
              {v.id === currentId ? <Badge tone="good">Current</Badge> : v.status === "superseded" ? <Badge>Superseded</Badge> : null}
              <span className="small muted">{num(v.n_rows)} rows × {num(v.n_cols)} columns · {dateTime(v.created_at)}</span>
              {v.id !== shownId && <button className="btn ghost sm" onClick={() => onShow(v.id)}>View</button>}
              {v.id !== currentId && (
                <button className="btn ghost sm" onClick={() => window.confirm(`Make version ${v.version} current? Later versions are kept but marked superseded.`)
                  && restore.mutate(v.id, { onSuccess: () => toast(`Version ${v.version} restored.`), onError: (e) => toast(errorMessage(e), "error") })}>
                  <Icon name="undo" size={12} />Restore</button>
              )}
            </div>
            <ul className="small secondary" style={{ margin: 0, paddingLeft: 18 }}>
              {v.operations.slice(0, 8).map((o, i) => <li key={i}>{describeOperation(o)}</li>)}
              {v.operations.length > 8 && <li>and {v.operations.length - 8} more</li>}
            </ul>
            <div className="small muted">
              {v.parent_id ? `Created by ${actor(v.created_by)}` : "Original upload"}
              {v.approved_by ? `, approved by ${actor(v.approved_by)}` : ""}
              {" · "}checksum <code>{v.checksum.slice(0, 12)}</code>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

function QualityPanel({ pid, dataset, version, isCurrent }: { pid: string; dataset: Dataset; version: DatasetVersion; isCurrent: boolean }) {
  const toast = useToast();
  const { data: approvals } = useApprovals(pid);
  const [plan, setPlan] = useState<{ operations: Json[]; approval_id: string | null } | null>(null);
  const propose = useProjectMutation(pid, () => api.post<{ operations: Json[]; approval_id: string | null; parent_version_id: string }>(
    `/projects/${pid}/datasets/${dataset.id}/cleaning-plan`));
  const issues = (version.quality.issues ?? []) as QualityIssue[];
  const pending = approvals?.find((a) => a.action === "apply_cleaning" && a.entity_id === version.id);
  const counts = { high: 0, medium: 0, low: 0 } as Record<string, number>;
  for (const i of issues) counts[i.severity] = (counts[i.severity] ?? 0) + 1;
  return (
    <Card title="Data quality" subtitle={`Checks for version ${version.version}: attention checks, speeders, straight-lining, duplicates, out-of-range values, outliers, missing data and personal data.`}
      actions={isCurrent && issues.some((i) => i.operation) && !pending ? (
        <button className="btn primary" disabled={propose.isPending} onClick={() => propose.mutate(undefined, {
          onSuccess: (r) => { setPlan(r); toast(r.approval_id ? "Cleaning plan proposed. Approve it to create a new version." : "Nothing to clean."); },
          onError: (e) => toast(errorMessage(e), "error"),
        })}>Propose cleaning plan</button>
      ) : undefined}>
      <div className="stack">
        <div className="grid grid-4" style={{ gap: 0 }}>
          <Stat label="Quality score" value={version.quality.quality_score !== undefined ? `${num(version.quality.quality_score)} / 100` : "n/a"} />
          <Stat label="Flagged respondents" value={num(version.quality.flagged_respondents ?? 0)}
            delta={typeof version.quality.flagged_share === "number" ? `${pct(version.quality.flagged_share, 1)} of rows` : undefined} />
          <Stat label="High severity" value={counts.high} />
          <Stat label="Medium and low" value={counts.medium + counts.low} />
        </div>
        {pending && (
          <div>
            <Callout tone="warning">A cleaning plan for this version is waiting for your decision. Approving creates a new version; this one stays unchanged.</Callout>
            <ApprovalCard pid={pid} approval={pending} />
          </div>
        )}
        {plan && !plan.approval_id && <Callout tone="good">No automatic fixes are needed. Review the remaining notes below.</Callout>}
        {!issues.length ? <Callout tone="good">No quality issues found.</Callout> : (
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Severity</th><th>Issue</th><th>Suggested action</th><th className="num">Rows</th><th>Automatic fix</th></tr></thead>
              <tbody>
                {issues.map((i) => (
                  <tr key={i.id}>
                    <td><StatusBadge status={i.severity} /></td>
                    <td>{i.message}</td>
                    <td className="small secondary">{i.suggestion}</td>
                    <td className="num">{i.count ? num(i.count) : ""}</td>
                    <td className="small">{i.operation ? <code>{String(i.operation.op)}</code> : <span className="muted">Needs a person</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Card>
  );
}

function ColumnDictionary({ columns }: { columns: ColumnProfile[] }) {
  const [filter, setFilter] = useState("");
  const rows = columns.filter((c) => !filter || `${c.name} ${c.inferred_type}`.toLowerCase().includes(filter.toLowerCase()));
  return (
    <Card title="Columns" subtitle={`${columns.length} columns with inferred types and summaries`}
      actions={<input className="input sm" placeholder="Filter" aria-label="Filter columns" value={filter} onChange={(e) => setFilter(e.target.value)} />}>
      <div className="table-wrap" style={{ maxHeight: 380 }}>
        <table className="table">
          <thead><tr><th>Column</th><th>Type</th><th className="num">Missing</th><th className="num">Unique</th><th>Summary</th></tr></thead>
          <tbody>
            {rows.map((c) => (
              <tr key={c.name}>
                <td><code>{c.name}</code></td>
                <td>{c.type ?? c.inferred_type}</td>
                <td className="num">{c.missing ? pct(c.missing_share, 1) : ""}</td>
                <td className="num">{num(c.unique)}</td>
                <td className="small secondary">
                  {c.mean !== undefined ? `mean ${num(c.mean, 2)}, SD ${num(c.sd, 2)}, range ${num(c.min, c.max !== undefined && c.max < 100 ? 1 : 0)} to ${num(c.max, c.max !== undefined && c.max < 100 ? 1 : 0)}`
                    : c.top_values?.length ? c.top_values.slice(0, 3).map((t) => `${t.value} (${t.count})`).join(", ")
                      : c.examples?.length ? `"${c.examples[0].slice(0, 60)}"` : ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function PreviewGrid({ pid, did, vid }: { pid: string; did: string; vid: string }) {
  const { data } = useApi<{ columns: string[]; rows: Record<string, unknown>[]; n_rows: number }>(
    [pid, "preview", vid], `/projects/${pid}/datasets/${did}/versions/${vid}/preview?limit=50`);
  if (!data) return null;
  return (
    <Card title="Preview" subtitle={`First ${data.rows.length} of ${num(data.n_rows)} rows`}>
      <div className="table-wrap" style={{ maxHeight: 360 }}>
        <table className="table">
          <thead><tr>{data.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
          <tbody>
            {data.rows.map((r, i) => (
              <tr key={i}>
                {data.columns.map((c) => {
                  const v = r[c];
                  return <td key={c} className={typeof v === "number" ? "num" : "small"} style={{ whiteSpace: "nowrap", maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis" }}
                    title={typeof v === "string" ? v : undefined}>{v === null || v === undefined ? <span className="muted">·</span> : String(v)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
