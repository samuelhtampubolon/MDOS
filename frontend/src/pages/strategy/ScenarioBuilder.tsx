import { useState, type FormEvent } from "react";
import { api, errorMessage } from "../../api/client";
import { useProjectMutation } from "../../api/hooks";
import type { MarketModel, Scenario } from "../../api/types";
import { Callout, Card, Icon, useToast } from "../../components/ui";
import { money } from "../../lib/format";

type FieldKind = "money" | "pct" | "signedPct" | "number" | "channel" | "segment" | "competitor";

interface LeverField {
  key: string;
  label: string;
  kind: FieldKind;
  optional?: boolean;
}

export const LEVER_SPECS: Record<string, { label: string; fields: LeverField[] }> = {
  set_price: { label: "Set the price", fields: [{ key: "value", label: "New price", kind: "money" }] },
  reallocate_budget: { label: "Move budget between channels", fields: [
    { key: "from", label: "From", kind: "channel" }, { key: "to", label: "To", kind: "channel" }, { key: "share", label: "Share moved (%)", kind: "pct" }] },
  set_budget: { label: "Set a channel budget", fields: [{ key: "channel", label: "Channel", kind: "channel" }, { key: "value", label: "Budget per month", kind: "money" }] },
  scale_budget: { label: "Scale all budgets", fields: [{ key: "factor", label: "Factor (1.2 means +20%)", kind: "number" }] },
  set_segment_share: { label: "Change a segment's share of the market", fields: [
    { key: "segment", label: "Segment", kind: "segment" }, { key: "value", label: "Share of the market (%)", kind: "pct" }] },
  competitor_price: { label: "A competitor sets a new price", fields: [
    { key: "competitor", label: "Competitor", kind: "competitor" }, { key: "value", label: "Competitor price", kind: "money" }] },
  competitor_price_change: { label: "A competitor changes its price", fields: [
    { key: "competitor", label: "Competitor", kind: "competitor" }, { key: "pct", label: "Change (%), for example -25", kind: "signedPct" }] },
  conversion_uplift: { label: "Improve conversion", fields: [
    { key: "pct", label: "Uplift (%)", kind: "signedPct" }, { key: "channel", label: "Only on channel", kind: "channel", optional: true }] },
  set_wom: { label: "Change word of mouth", fields: [{ key: "value", label: "Referred customers per customer", kind: "number" }] },
};

type Draft = { type: string; values: Record<string, string> };

function defaults(type: string, model: MarketModel): Record<string, string> {
  const first = { channel: model.channels[0]?.key ?? "", segment: model.segments[0]?.key ?? "", competitor: model.competitors[0]?.key ?? "" };
  const out: Record<string, string> = {};
  for (const f of LEVER_SPECS[type].fields) {
    if (f.kind === "channel" && !f.optional) out[f.key] = f.key === "to" ? model.channels[1]?.key ?? first.channel : first.channel;
    if (f.kind === "segment") out[f.key] = first.segment;
    if (f.kind === "competitor") out[f.key] = first.competitor;
  }
  if (type === "set_price") out.value = String(model.offer.price);
  return out;
}

function toLever(d: Draft): Record<string, unknown> {
  const lever: Record<string, unknown> = { type: d.type };
  for (const f of LEVER_SPECS[d.type].fields) {
    const raw = d.values[f.key];
    if (raw === undefined || raw === "") {
      if (f.optional) continue;
      throw new Error(`${LEVER_SPECS[d.type].label}: ${f.label} is required.`);
    }
    if (["channel", "segment", "competitor"].includes(f.kind)) lever[f.key] = raw;
    else if (f.kind === "pct" || f.kind === "signedPct") lever[f.key] = Number(raw) / 100;
    else lever[f.key] = Number(raw);
  }
  return lever;
}

export function ScenarioBuilder({ pid, baseline, currency, onCreated }: { pid: string; baseline: Scenario; currency: string; onCreated: (id: string) => void }) {
  const toast = useToast();
  const model = baseline.model;
  const [name, setName] = useState("");
  const [drafts, setDrafts] = useState<Draft[]>([{ type: "set_price", values: defaults("set_price", model) }]);
  const [error, setError] = useState("");
  const create = useProjectMutation(pid, (body: Record<string, unknown>) => api.post<Scenario>(`/projects/${pid}/scenarios`, body));
  const update = (i: number, d: Draft) => setDrafts((prev) => prev.map((x, j) => (j === i ? d : x)));
  const submit = (e: FormEvent) => {
    e.preventDefault();
    try {
      const levers = drafts.map(toLever);
      setError("");
      create.mutate({ baseline_id: baseline.id, name, levers }, {
        onSuccess: (s) => { toast(`Scenario "${s.name}" simulated.`); onCreated(s.id); setName(""); },
        onError: (err) => setError(errorMessage(err)),
      });
    } catch (err) {
      setError(errorMessage(err));
    }
  };
  const options = (kind: FieldKind) => (kind === "channel" ? model.channels : kind === "segment" ? model.segments : model.competitors).map((x) => [x.key, x.name]);
  return (
    <Card title="Build a scenario" subtitle="Combine levers. The simulator applies them in order to a copy of the baseline.">
      <form className="stack-sm" onSubmit={submit}>
        <div className="field"><label htmlFor="sc-name">Scenario name</label>
          <input id="sc-name" className="input" required value={name} placeholder="Launch at Rp 150.000 with more TikTok" onChange={(e) => setName(e.target.value)} /></div>
        {drafts.map((d, i) => (
          <div key={i} className="card flat" style={{ padding: 10 }}>
            <div className="row" style={{ justifyContent: "space-between", marginBottom: 6 }}>
              <select className="select sm" aria-label={`Lever ${i + 1} type`} value={d.type} onChange={(e) => update(i, { type: e.target.value, values: defaults(e.target.value, model) })}>
                {Object.entries(LEVER_SPECS).map(([k, s]) => <option key={k} value={k}>{s.label}</option>)}
              </select>
              {drafts.length > 1 && <button type="button" className="btn ghost icon sm" aria-label={`Remove lever ${i + 1}`} onClick={() => setDrafts(drafts.filter((_, j) => j !== i))}><Icon name="x" size={14} /></button>}
            </div>
            <div className="grid grid-3">
              {LEVER_SPECS[d.type].fields.map((f) => (
                <div key={f.key} className="field">
                  <label htmlFor={`lv-${i}-${f.key}`}>{f.label}{f.optional ? " (optional)" : ""}</label>
                  {["channel", "segment", "competitor"].includes(f.kind) ? (
                    <select id={`lv-${i}-${f.key}`} className="select sm" value={d.values[f.key] ?? ""} onChange={(e) => update(i, { ...d, values: { ...d.values, [f.key]: e.target.value } })}>
                      {f.optional && <option value="">All channels</option>}
                      {options(f.kind).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                    </select>
                  ) : (
                    <input id={`lv-${i}-${f.key}`} className="input sm" type="number" step="any" value={d.values[f.key] ?? ""}
                      onChange={(e) => update(i, { ...d, values: { ...d.values, [f.key]: e.target.value } })} />
                  )}
                  {f.kind === "money" && d.values[f.key] && <span className="hint">{money(Number(d.values[f.key]), currency)}</span>}
                </div>
              ))}
            </div>
          </div>
        ))}
        <div className="row">
          <button type="button" className="btn sm" onClick={() => setDrafts([...drafts, { type: "reallocate_budget", values: defaults("reallocate_budget", model) }])}>
            <Icon name="plus" size={12} />Add lever</button>
        </div>
        {error && <Callout tone="critical">{error}</Callout>}
        <div><button className="btn primary" disabled={create.isPending}><Icon name="play" size={14} />Simulate scenario</button></div>
      </form>
    </Card>
  );
}
