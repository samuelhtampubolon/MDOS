import { useEffect, useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useEvidence, useProjectMutation } from "../../api/hooks";
import type { MarketModel, Scenario } from "../../api/types";
import { EvidenceModal } from "../../components/domain";
import { Badge, Callout, Card, Icon, useToast } from "../../components/ui";
import { money, num, pct } from "../../lib/format";

const SOURCES: [string, string][] = [
  ["evidence", "Research evidence"], ["benchmark", "Benchmark"], ["expert_judgment", "Expert judgment"], ["guess", "Guess (placeholder)"],
];

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v)) as T;
}

/** Numeric input bound to a model path; percentages are edited as 0 to 100. */
function NumberCell({ value, onChange, percent = false, label }: { value: number; onChange: (v: number) => void; percent?: boolean; label: string }) {
  return (
    <input className="input sm num" type="number" step="any" aria-label={label} style={{ width: percent ? 80 : 130, textAlign: "right" }}
      value={Number.isFinite(value) ? (percent ? +(value * 100).toFixed(4) : value) : ""}
      onChange={(e) => onChange(percent ? Number(e.target.value) / 100 : Number(e.target.value))} />
  );
}

export default function ModelCanvas({ pid, baseline, currency }: { pid: string; baseline: Scenario; currency: string }) {
  const toast = useToast();
  const [model, setModel] = useState<MarketModel>(() => clone(baseline.model));
  const [dirty, setDirty] = useState(false);
  const [evidenceId, setEvidenceId] = useState<string | null>(null);
  const { data: evidence } = useEvidence(pid);
  useEffect(() => {
    setModel(clone(baseline.model));
    setDirty(false);
  }, [baseline]);
  const save = useProjectMutation(pid, (m: MarketModel) => api.patch(`/projects/${pid}/scenarios/${baseline.id}`, { model: m }));
  const edit = (fn: (m: MarketModel) => void) => {
    setModel((prev) => {
      const next = clone(prev);
      fn(next);
      return next;
    });
    setDirty(true);
  };
  const codes = new Map((evidence ?? []).map((e) => [e.id, e.code]));
  const placeholders = model.assumptions.filter((a) => a.source === "guess" || a.source === "benchmark").length;
  return (
    <div className="stack">
      {placeholders > 0 && (
        <Callout tone="warning">
          <strong>{placeholders} assumption{placeholders === 1 ? " is a" : "s are"} placeholder{placeholders === 1 ? "" : "s"}</strong> (a guess or a generic benchmark).
          Replace them with your own numbers, such as visitor statistics from the tourism office or BPS, your real costs and past campaign results,
          then set the source to match. Scenarios re-run automatically when you save.
        </Callout>
      )}
      <div className="row" style={{ justifyContent: "flex-end" }}>
        {dirty && <button className="btn ghost" onClick={() => { setModel(clone(baseline.model)); setDirty(false); }}>Discard changes</button>}
        <button className="btn primary" disabled={!dirty || save.isPending} onClick={() => save.mutate(model, {
          onSuccess: () => { toast("Model saved. The baseline and every scenario were re-simulated."); setDirty(false); },
          onError: (e) => toast(errorMessage(e), "error"),
        })}><Icon name="refresh" size={14} />Save and re-run</button>
      </div>
      <Card title="Assumption register" subtitle="Every number in the model, where it came from and how confident we are.">
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Assumption</th><th>Value</th><th>Source</th><th>Evidence</th><th>Confidence</th><th>Note</th></tr></thead>
            <tbody>
              {model.assumptions.map((a, i) => (
                <tr key={a.key}>
                  <td style={{ fontWeight: 600 }}>{a.label}</td>
                  <td className="num small">{typeof a.value === "number" ? (a.value >= 1000 ? num(a.value) : num(a.value, a.value < 10 ? 3 : 0)) : a.value ?? ""}{a.unit ? ` ${a.unit}` : ""}</td>
                  <td>
                    <select className="select sm" aria-label={`Source of ${a.label}`} value={a.source}
                      onChange={(e) => edit((m) => { m.assumptions[i].source = e.target.value; })}>
                      {SOURCES.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
                    </select>
                    {(a.source === "guess" || a.source === "benchmark") && <div style={{ marginTop: 4 }}><Badge tone="warning"><Icon name="alert" size={12} />Replace</Badge></div>}
                  </td>
                  <td>{a.evidence_id ? <button className="chip code" onClick={() => setEvidenceId(a.evidence_id)}>{codes.get(a.evidence_id) ?? "view"}</button> : <span className="muted small">None</span>}</td>
                  <td>
                    <select className="select sm" aria-label={`Confidence in ${a.label}`} value={a.confidence}
                      onChange={(e) => edit((m) => { m.assumptions[i].confidence = e.target.value; })}>
                      <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
                    </select>
                  </td>
                  <td><input className="input sm" aria-label={`Note on ${a.label}`} value={a.note} onChange={(e) => edit((m) => { m.assumptions[i].note = e.target.value; })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="grid grid-2">
        <Card title="Market and offer" subtitle={`${model.market_name} · per ${model.period}`}>
          <dl className="kv">
            <dt>Addressable market</dt><dd><NumberCell label="Addressable market" value={model.market_size} onChange={(v) => edit((m) => { m.market_size = v; })} /> people</dd>
            <dt>Price</dt><dd><NumberCell label="Price" value={model.offer.price} onChange={(v) => edit((m) => { m.offer.price = v; })} /> {money(model.offer.price, currency)}</dd>
            <dt>Reference price</dt><dd><NumberCell label="Reference price" value={model.offer.reference_price} onChange={(v) => edit((m) => { m.offer.reference_price = v; })} /></dd>
            <dt>Variable cost per customer</dt><dd><NumberCell label="Unit cost" value={model.offer.unit_cost} onChange={(v) => edit((m) => { m.offer.unit_cost = v; })} /></dd>
            <dt>Fixed costs per {model.period}</dt><dd><NumberCell label="Fixed costs" value={model.offer.fixed_costs} onChange={(v) => edit((m) => { m.offer.fixed_costs = v; })} /></dd>
            <dt>Word of mouth</dt><dd><NumberCell label="Word of mouth rate" value={model.word_of_mouth_rate} onChange={(v) => edit((m) => { m.word_of_mouth_rate = v; })} /> referred customers per customer</dd>
          </dl>
          <div className="small muted" style={{ marginTop: 8 }}>
            Price response: {model.price_response.mode === "curve" ? `${model.price_response.points.length} tested prices from research` : "elasticity"}.
            The reference price is the price at which channel conversion rates apply.
          </div>
        </Card>
        <Card title="Competitors">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Competitor</th><th className="num">Price</th>{model.positioning_axes.slice(1).map((ax) => <th key={ax} className="num">{ax}</th>)}</tr></thead>
              <tbody>
                {model.competitors.map((c, i) => (
                  <tr key={c.key}>
                    <td>{c.name}</td>
                    <td className="num"><NumberCell label={`${c.name} price`} value={c.price} onChange={(v) => edit((m) => { m.competitors[i].price = v; })} /></td>
                    {model.positioning_axes.slice(1).map((ax) => <td key={ax} className="num">{num(c.attributes[ax], 1)}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      </div>
      <Card title="Segments" subtitle="Shares must add up to 100%. WTP multiplier scales willingness to pay relative to the research average.">
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Segment</th><th className="num">Share (%)</th><th className="num">WTP multiplier</th><th className="num">Conversion multiplier</th><th className="num">Repeat rate (%)</th><th className="num">Competitor sensitivity</th></tr></thead>
            <tbody>
              {model.segments.map((s, i) => (
                <tr key={s.key}>
                  <td>{s.name}</td>
                  <td className="num"><NumberCell percent label={`${s.name} share`} value={s.share} onChange={(v) => edit((m) => { m.segments[i].share = v; })} /></td>
                  <td className="num"><NumberCell label={`${s.name} WTP multiplier`} value={s.wtp_multiplier} onChange={(v) => edit((m) => { m.segments[i].wtp_multiplier = v; })} /></td>
                  <td className="num"><NumberCell label={`${s.name} conversion multiplier`} value={s.conversion_multiplier} onChange={(v) => edit((m) => { m.segments[i].conversion_multiplier = v; })} /></td>
                  <td className="num"><NumberCell percent label={`${s.name} repeat rate`} value={s.repeat_rate} onChange={(v) => edit((m) => { m.segments[i].repeat_rate = v; })} /></td>
                  <td className="num"><NumberCell label={`${s.name} cross-price elasticity`} value={s.cross_price_elasticity} onChange={(v) => edit((m) => { m.segments[i].cross_price_elasticity = v; })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="small muted" style={{ marginTop: 6 }}>Total share: {pct(model.segments.reduce((a, s) => a + s.share, 0), 1)}</div>
      </Card>
      <Card title="Channels" subtitle="Monthly budget, cost per 1,000 impressions and funnel rates. Replace benchmarks with your own campaign data.">
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Channel</th><th className="num">Budget</th><th className="num">CPM</th><th className="num">Engagement (%)</th><th className="num">Lead (%)</th><th className="num">Conversion (%)</th><th className="num">Commission (%)</th></tr></thead>
            <tbody>
              {model.channels.map((c, i) => (
                <tr key={c.key}>
                  <td>{c.name}</td>
                  <td className="num"><NumberCell label={`${c.name} budget`} value={c.budget} onChange={(v) => edit((m) => { m.channels[i].budget = v; })} /></td>
                  <td className="num"><NumberCell label={`${c.name} CPM`} value={c.cpm} onChange={(v) => edit((m) => { m.channels[i].cpm = v; })} /></td>
                  <td className="num"><NumberCell percent label={`${c.name} engagement rate`} value={c.engagement_rate} onChange={(v) => edit((m) => { m.channels[i].engagement_rate = v; })} /></td>
                  <td className="num"><NumberCell percent label={`${c.name} lead rate`} value={c.lead_rate} onChange={(v) => edit((m) => { m.channels[i].lead_rate = v; })} /></td>
                  <td className="num"><NumberCell percent label={`${c.name} conversion rate`} value={c.conversion_rate} onChange={(v) => edit((m) => { m.channels[i].conversion_rate = v; })} /></td>
                  <td className="num"><NumberCell percent label={`${c.name} commission`} value={c.commission_rate} onChange={(v) => edit((m) => { m.channels[i].commission_rate = v; })} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <EvidenceModal pid={pid} evidenceId={evidenceId} onClose={() => setEvidenceId(null)} />
    </div>
  );
}
