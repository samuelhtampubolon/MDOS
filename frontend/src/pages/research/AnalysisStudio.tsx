import { useEffect, useMemo, useState, type FormEvent } from "react";
import { api, errorMessage } from "../../api/client";
import { useAnalyses, useAnalysis, useDataset, useDatasets, useEvidence, useMethods, useProject, useProjectMutation } from "../../api/hooks";
import type { Analysis, ColumnProfile } from "../../api/types";
import { AnalysisChart } from "../../components/charts/AnalysisChart";
import { AGENT_LABELS } from "../../components/domain";
import { Badge, Callout, Card, ChecksList, Empty, Icon, useToast } from "../../components/ui";
import { dateTime, pValue } from "../../lib/format";

type ColumnFilter = "any" | "numeric" | "categorical" | "text" | "likert";

interface Field {
  key: string;
  label: string;
  kind: "column" | "columns" | "number" | "text" | "select" | "bool" | "priceMap";
  filter?: ColumnFilter;
  optional?: boolean;
  options?: [string, string][];
  initial?: unknown;
  hint?: string;
}

const NUMERIC_TYPES = ["numeric", "likert", "price", "binary"];
const CATEGORICAL_TYPES = ["categorical", "binary"];

/** Parameter forms per method. The server validates the same parameters against its registry. */
const METHOD_FORMS: Record<string, Field[]> = {
  descriptive: [{ key: "columns", label: "Variables", kind: "columns", filter: "any" }],
  crosstab: [
    { key: "row", label: "Row variable", kind: "column", filter: "categorical" },
    { key: "col", label: "Column variable", kind: "column", filter: "categorical" },
  ],
  correlation: [
    { key: "columns", label: "Variables (two or more)", kind: "columns", filter: "numeric" },
    { key: "method", label: "Method", kind: "select", options: [["pearson", "Pearson"], ["spearman", "Spearman (ranks)"]], initial: "pearson" },
  ],
  regression_ols: [
    { key: "dv", label: "Outcome (dependent variable)", kind: "column", filter: "numeric" },
    { key: "predictors", label: "Predictors", kind: "columns", filter: "any" },
    { key: "robust", label: "Standard errors", kind: "select", options: [["auto", "Robust (HC3) when checks fail"], ["none", "Classical"], ["HC3", "Always robust (HC3)"]], initial: "auto" },
    { key: "categorical", label: "Treat as categorical", kind: "columns", filter: "any", optional: true },
  ],
  regression_logistic: [
    { key: "dv", label: "Yes/no outcome", kind: "column", filter: "categorical" },
    { key: "predictors", label: "Predictors", kind: "columns", filter: "any" },
    { key: "positive", label: "Value that counts as yes", kind: "text", optional: true, hint: "For example Ya. Leave empty to detect it." },
    { key: "categorical", label: "Treat as categorical", kind: "columns", filter: "any", optional: true },
  ],
  reliability: [
    { key: "items", label: "Scale items (two or more)", kind: "columns", filter: "likert" },
    { key: "scale_name", label: "Scale name", kind: "text", optional: true },
  ],
  mediation: [
    { key: "x", label: "X (antecedent)", kind: "column", filter: "numeric" },
    { key: "m", label: "M (mediator)", kind: "column", filter: "numeric" },
    { key: "y", label: "Y (outcome)", kind: "column", filter: "numeric" },
    { key: "covariates", label: "Covariates", kind: "columns", filter: "any", optional: true },
    { key: "n_boot", label: "Bootstrap resamples", kind: "number", initial: 5000, hint: "1,000 to 20,000. The seed is fixed so results reproduce." },
  ],
  moderation: [
    { key: "x", label: "X (antecedent)", kind: "column", filter: "numeric" },
    { key: "w", label: "W (moderator)", kind: "column", filter: "numeric" },
    { key: "y", label: "Y (outcome)", kind: "column", filter: "numeric" },
    { key: "covariates", label: "Covariates", kind: "columns", filter: "any", optional: true },
    { key: "center", label: "Mean-center X and W", kind: "bool", initial: true },
  ],
  van_westendorp: [
    { key: "too_cheap", label: "Too cheap", kind: "column", filter: "numeric" },
    { key: "cheap", label: "Cheap (a bargain)", kind: "column", filter: "numeric" },
    { key: "expensive", label: "Expensive", kind: "column", filter: "numeric" },
    { key: "too_expensive", label: "Too expensive", kind: "column", filter: "numeric" },
    { key: "target_price", label: "Target price", kind: "number", optional: true },
  ],
  gabor_granger: [
    { key: "price_columns", label: "Price and question pairs", kind: "priceMap", hint: "One line per price: price = column, for example 150000 = wtp_150k." },
    { key: "target_price", label: "Target price", kind: "number", optional: true },
  ],
  wtp: [
    { key: "column", label: "Yes/no question", kind: "column", filter: "categorical" },
    { key: "price", label: "Price asked", kind: "number" },
    { key: "group", label: "Compare by group", kind: "column", filter: "categorical", optional: true },
    { key: "positive", label: "Value that counts as yes", kind: "text", optional: true },
  ],
  segmentation: [
    { key: "objective", label: "Segmentation objective", kind: "text", hint: "Required. What decision will the segments inform?" },
    { key: "rationale", label: "Why these variables", kind: "text", hint: "Required. Link the variables to the objective." },
    { key: "variables", label: "Clustering variables", kind: "columns", filter: "numeric" },
    { key: "k", label: "Number of segments", kind: "number", optional: true, hint: "Leave empty to choose by silhouette and stability." },
    { key: "profile_columns", label: "Describe segments by", kind: "columns", filter: "any", optional: true },
    { key: "text_column", label: "Open text for personas", kind: "column", filter: "text", optional: true },
  ],
  text_themes: [
    { key: "text_column", label: "Text column", kind: "column", filter: "text" },
    { key: "n_topics", label: "Number of themes", kind: "number", initial: 5 },
  ],
  sentiment: [
    { key: "text_column", label: "Text column", kind: "column", filter: "text" },
    { key: "group", label: "Compare by group", kind: "column", filter: "categorical", optional: true },
  ],
  journey_voc: [
    { key: "text_column", label: "Review text", kind: "column", filter: "text" },
    { key: "template", label: "Journey template", kind: "select", options: [["tourism", "Tourism experience"], ["generic", "Generic purchase"]], initial: "tourism" },
    { key: "rating_column", label: "Star rating", kind: "column", filter: "numeric", optional: true },
  ],
};

function matches(c: ColumnProfile, filter: ColumnFilter = "any"): boolean {
  const t = c.type ?? c.inferred_type;
  if (t === "id" || t === "datetime") return false;
  if (filter === "numeric") return NUMERIC_TYPES.includes(t);
  if (filter === "likert") return t === "likert" || t === "numeric";
  if (filter === "categorical") return CATEGORICAL_TYPES.includes(t) || (t === "numeric" && c.unique <= 12);
  if (filter === "text") return t === "text";
  return true;
}

export default function AnalysisStudio({ pid }: { pid: string }) {
  const { data: analyses } = useAnalyses(pid);
  const [chosen, setViewId] = useState<string | undefined>();
  const viewId = chosen ?? analyses?.[0]?.id;
  return (
    <div className="stack">
      <RunPanel pid={pid} onRan={setViewId} />
      <div className="grid grid-sidebar">
        <Card title="History" subtitle="Every analysis is stored with its parameters and data version.">
          {!analyses?.length ? <span className="muted small">No analyses yet.</span> : (
            <div className="stack-sm" style={{ maxHeight: 900, overflowY: "auto" }}>
              {analyses.map((a) => (
                <button key={a.id} onClick={() => setViewId(a.id)} className="list-item"
                  style={{ textAlign: "left", width: "100%", border: 0, borderRadius: 8, padding: "8px 10px", cursor: "pointer", color: "inherit",
                    background: viewId === a.id ? "var(--accent-soft)" : "transparent" }}>
                  <div className="grow">
                    <div style={{ fontWeight: 600, fontSize: 13 }}>{a.title}</div>
                    <div className="small muted">{a.created_by?.startsWith("agent:") ? `${AGENT_LABELS[a.created_by.slice(6)] ?? "Agent"} agent` : "You"} · {dateTime(a.created_at)}</div>
                  </div>
                  {a.status === "failed" && <Badge tone="critical">Failed</Badge>}
                </button>
              ))}
            </div>
          )}
        </Card>
        {viewId ? <AnalysisView pid={pid} aid={viewId} onDeleted={() => setViewId(undefined)} /> : <Empty title="Choose a method above to run your first analysis" />}
      </div>
    </div>
  );
}

function RunPanel({ pid, onRan }: { pid: string; onRan: (id: string) => void }) {
  const { data: datasets } = useDatasets(pid);
  const { data: methods } = useMethods();
  const toast = useToast();
  const [did, setDid] = useState<string | undefined>();
  const [method, setMethod] = useState("descriptive");
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [title, setTitle] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    if (!did && datasets?.length) setDid((datasets.find((d) => d.kind === "survey") ?? datasets[0]).id);
  }, [datasets, did]);
  const { data: dataset } = useDataset(pid, did);
  const version = dataset?.versions?.find((v) => v.id === dataset.current_version_id);
  const columns = version?.columns ?? [];
  const fields = METHOD_FORMS[method] ?? [];
  useEffect(() => {
    setValues(Object.fromEntries(fields.filter((f) => f.initial !== undefined).map((f) => [f.key, f.initial])));
    setError("");
  }, [method]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = useProjectMutation(pid, (body: Record<string, unknown>) => api.post<Analysis>(`/projects/${pid}/analyses`, body));
  const grouped = useMemo(() => {
    const out: Record<string, { key: string; label: string; description: string }[]> = {};
    for (const m of methods ?? []) (out[m.category] ??= []).push(m);
    return out;
  }, [methods]);
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!version) return;
    const params: Record<string, unknown> = {};
    for (const f of fields) {
      const v = values[f.key];
      if (v === undefined || v === "" || (Array.isArray(v) && !v.length)) {
        if (!f.optional && f.kind !== "bool") return setError(`${f.label} is required.`);
        continue;
      }
      if (f.kind === "priceMap") {
        const map: Record<string, string> = {};
        for (const line of String(v).split("\n")) {
          const [price, col] = line.split("=").map((s) => s.trim());
          if (price && col) map[String(Number(price.replace(/[^\d.]/g, "")))] = col;
        }
        params[f.key] = map;
      } else {
        params[f.key] = v;
      }
    }
    setError("");
    run.mutate({ dataset_version_id: version.id, method, params, title }, {
      onSuccess: (a) => { toast(a.status === "failed" ? "The analysis could not run. See the details." : "Analysis complete."); onRan(a.id); setTitle(""); },
      onError: (err) => setError(errorMessage(err)),
    });
  };
  const description = methods?.find((m) => m.key === method)?.description;
  return (
    <Card title="Run an analysis" subtitle="Statistics are computed in code. Every result reports its sample size, assumption checks and limitations.">
      <form className="stack" onSubmit={submit}>
        <div className="grid grid-3">
          <div className="field">
            <label htmlFor="an-ds">Dataset</label>
            <select id="an-ds" className="select" value={did ?? ""} onChange={(e) => setDid(e.target.value)}>
              {(datasets ?? []).map((d) => <option key={d.id} value={d.id}>{d.name} (v{d.current_version?.version ?? 1})</option>)}
            </select>
          </div>
          <div className="field" style={{ gridColumn: "span 2" }}>
            <label htmlFor="an-method">Method</label>
            <select id="an-method" className="select" value={method} onChange={(e) => setMethod(e.target.value)}>
              {Object.entries(grouped).map(([cat, list]) => (
                <optgroup key={cat} label={cat}>{list.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}</optgroup>
              ))}
            </select>
            {description && <span className="hint">{description}</span>}
          </div>
        </div>
        {!version ? <span className="muted small">Upload a dataset first.</span> : (
          <div className="grid grid-2">
            {fields.map((f) => <ParamField key={`${method}-${f.key}`} field={f} columns={columns} value={values[f.key]}
              onChange={(v) => setValues((prev) => ({ ...prev, [f.key]: v }))} />)}
            <div className="field">
              <label htmlFor="an-title">Title (optional)</label>
              <input id="an-title" className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Generated from the method and variables" />
            </div>
          </div>
        )}
        {error && <Callout tone="critical">{error}</Callout>}
        <div><button className="btn primary" disabled={!version || run.isPending}><Icon name="play" size={14} />{run.isPending ? "Running" : "Run analysis"}</button></div>
      </form>
    </Card>
  );
}

function ParamField({ field, columns, value, onChange }: { field: Field; columns: ColumnProfile[]; value: unknown; onChange: (v: unknown) => void }) {
  const id = `pf-${field.key}`;
  const eligible = columns.filter((c) => matches(c, field.filter));
  const label = <label htmlFor={id}>{field.label}{field.optional ? " (optional)" : ""}</label>;
  const hint = field.hint && <span className="hint">{field.hint}</span>;
  if (field.kind === "column") {
    return (
      <div className="field">{label}
        <select id={id} className="select" value={String(value ?? "")} onChange={(e) => onChange(e.target.value || undefined)}>
          <option value="">{field.optional ? "None" : "Choose a column"}</option>
          {eligible.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
        </select>{hint}
      </div>
    );
  }
  if (field.kind === "columns") {
    const selected = (value as string[] | undefined) ?? [];
    return (
      <div className="field" style={{ gridColumn: "span 1" }}>{label}
        <select id={id} className="select" multiple size={Math.min(7, Math.max(3, eligible.length))} value={selected}
          onChange={(e) => onChange(Array.from(e.target.selectedOptions).map((o) => o.value))}>
          {eligible.map((c) => <option key={c.name} value={c.name}>{c.name}{c.inferred_type === "likert" ? " (Likert)" : ""}</option>)}
        </select>
        <span className="hint">{field.hint ?? "Hold Ctrl or Cmd to choose several."} {selected.length ? `${selected.length} chosen.` : ""}</span>
      </div>
    );
  }
  if (field.kind === "select") {
    return (
      <div className="field">{label}
        <select id={id} className="select" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)}>
          {field.options?.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>{hint}
      </div>
    );
  }
  if (field.kind === "bool") {
    return <label className="checkbox" style={{ alignSelf: "end" }}><input type="checkbox" checked={Boolean(value)} onChange={(e) => onChange(e.target.checked)} />{field.label}</label>;
  }
  if (field.kind === "number") {
    return (
      <div className="field">{label}
        <input id={id} className="input" type="number" value={value === undefined ? "" : String(value)}
          onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))} />{hint}
      </div>
    );
  }
  if (field.kind === "priceMap") {
    return (
      <div className="field">{label}
        <textarea id={id} className="textarea" value={String(value ?? "")} placeholder={"100000 = gg_100k\n150000 = wtp_150k\n200000 = gg_200k"}
          onChange={(e) => onChange(e.target.value)} />{hint}
      </div>
    );
  }
  return (
    <div className="field">{label}
      <input id={id} className="input" value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />{hint}
    </div>
  );
}

export function AnalysisView({ pid, aid, onDeleted }: { pid: string; aid: string; onDeleted?: () => void }) {
  const { data: a } = useAnalysis(pid, aid);
  const { data: project } = useProject(pid);
  const { data: evidence } = useEvidence(pid);
  const toast = useToast();
  const [chosen, setChosen] = useState<string[]>([]);
  const save = useProjectMutation(pid, (keys: string[]) => api.post(`/projects/${pid}/analyses/${aid}/evidence`, { keys }));
  const remove = useProjectMutation(pid, () => api.del(`/projects/${pid}/analyses/${aid}`));
  useEffect(() => setChosen([]), [aid]);
  if (!a) return <Card title="Loading"><span className="muted">Loading</span></Card>;
  const saved = new Map((evidence ?? []).filter((e) => e.analysis_id === a.id).map((e) => [String(e.source_ref?.key ?? ""), e.code]));
  const cands = a.result?.evidence_candidates ?? [];
  const currency = project?.currency ?? "IDR";
  return (
    <div className="stack">
      <Card title={a.title} subtitle={`${a.n !== null ? `n = ${a.n} · ` : ""}${dateTime(a.created_at)}`}
        actions={<button className="btn ghost icon" aria-label="Delete analysis" title="Delete analysis"
          onClick={() => window.confirm("Delete this analysis? Evidence created from it must be deleted first.") && remove.mutate(undefined, {
            onSuccess: () => { toast("Analysis deleted."); onDeleted?.(); }, onError: (e) => toast(errorMessage(e), "error"),
          })}><Icon name="trash" size={16} /></button>}>
        {a.status === "failed" ? <Callout tone="critical">{a.error || "The analysis failed."}</Callout> : (
          <p style={{ margin: 0, fontSize: 15 }}>{a.result.summary}</p>
        )}
      </Card>
      {a.result?.charts?.map((c, i) => <Card key={i}><AnalysisChart spec={c} currency={currency} /></Card>)}
      <div className="grid grid-2">
        <Card title="Assumption checks" subtitle="Violations change how results are reported; they are never hidden.">
          {a.assumptions.length ? <ChecksList checks={a.assumptions} /> : <span className="muted small">No formal assumptions for this method.</span>}
        </Card>
        <Card title="Warnings and limitations">
          <div className="stack-sm">
            {a.warnings.map((w, i) => <Callout key={i} tone="warning">{w}</Callout>)}
            <ul className="small secondary" style={{ margin: 0, paddingLeft: 18 }}>{a.limitations.map((l, i) => <li key={i}>{l}</li>)}</ul>
            {!a.warnings.length && !a.limitations.length && <span className="muted small">None reported.</span>}
          </div>
        </Card>
      </div>
      {cands.length > 0 && (
        <Card title="Evidence candidates" subtitle="Save findings as evidence so insights, the strategy model and reports can cite them."
          actions={<button className="btn primary" disabled={!chosen.length || save.isPending} onClick={() => save.mutate(chosen, {
            onSuccess: () => { toast(`${chosen.length} evidence record(s) saved.`); setChosen([]); }, onError: (e) => toast(errorMessage(e), "error"),
          })}>Save {chosen.length || ""} as evidence</button>}>
          <div className="stack-sm">
            {cands.map((c) => {
              const code = saved.get(c.key);
              return (
                <label key={c.key} className="list-item" style={{ cursor: code ? "default" : "pointer" }}>
                  <input type="checkbox" disabled={Boolean(code)} checked={Boolean(code) || chosen.includes(c.key)}
                    onChange={(e) => setChosen((prev) => (e.target.checked ? [...prev, c.key] : prev.filter((k) => k !== c.key)))} />
                  <div className="grow">
                    <div style={{ fontWeight: 600 }}>{c.title}</div>
                    <div className="small secondary">{c.statement}</div>
                    <div className="small muted">{c.n ? `n = ${c.n}` : ""}{c.p_value !== undefined && c.p_value !== null ? ` · ${pValue(c.p_value)}` : ""}</div>
                  </div>
                  <span className={`chip strength-${c.strength}`}>{c.strength}</span>
                  {code && <Badge tone="good">Saved as {code}</Badge>}
                </label>
              );
            })}
          </div>
        </Card>
      )}
      <details className="disclosure">
        <summary><Icon name="chevronDown" size={12} />Parameters and raw result (JSON)</summary>
        <pre className="pre">{JSON.stringify({ method: a.method, params: a.params, dataset_version_id: a.dataset_version_id }, null, 2)}</pre>
        <pre className="pre">{JSON.stringify(a.result?.data ?? {}, null, 2).slice(0, 20000)}</pre>
      </details>
    </div>
  );
}
