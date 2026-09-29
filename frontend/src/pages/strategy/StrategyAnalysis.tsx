import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useApi, useProjectMutation } from "../../api/hooks";
import type { Json, Scenario } from "../../api/types";
import { Histogram, LineChart, ScatterMap } from "../../components/charts/basic";
import { Tornado } from "../../components/charts/special";
import { Callout, Card, Icon, Spinner, Stat, useToast } from "../../components/ui";
import { money, num, pct } from "../../lib/format";

interface Sensitivity {
  metric: string;
  base: number;
  pct: number;
  rows: { parameter: string; label: string; base_value: number; low_value: number; high_value: number; low: number; high: number; swing: number }[];
}

interface MonteCarlo {
  runs: number;
  seed: number;
  profit: { p10: number; p50: number; p90: number; mean: number };
  revenue: { p10: number; p50: number; p90: number; mean: number };
  customers: { p10: number; p50: number; p90: number; mean: number };
  probability_profit_positive: number;
  profit_histogram: { x0: number; x1: number; count: number }[];
}

interface PriceCurve {
  points: { price: number; customers: number; revenue: number; profit: number }[];
  revenue_max_price: number;
  profit_max_price: number;
  current_price: number;
  tested_range: [number, number] | null;
  research: { pmc?: number; pme?: number; opp?: number; ipp?: number } | null;
}

interface Optimized {
  metric: string;
  total_budget: number;
  allocation: { key: string; name: string; current: number; optimized: number }[];
  baseline_value: number;
  optimized_value: number;
  levers: Json[];
  note: string;
}

const METRIC_LABELS: Record<string, string> = { profit: "Profit", revenue: "Revenue", customers: "Customers" };

export function RiskView({ pid, scenarios, currency }: { pid: string; scenarios: Scenario[]; currency: string }) {
  const [sid, setSid] = useState(scenarios.find((s) => s.kind === "baseline")?.id ?? scenarios[0].id);
  const [metric, setMetric] = useState("profit");
  const [spread, setSpread] = useState(0.2);
  const [runs, setRuns] = useState(1000);
  const { data: sens } = useApi<Sensitivity>([pid, "sensitivity", sid, metric, spread], `/projects/${pid}/scenarios/${sid}/sensitivity?metric=${metric}&pct=${spread}`);
  const { data: mc, isFetching } = useApi<MonteCarlo>([pid, "monte-carlo", sid, runs], `/projects/${pid}/scenarios/${sid}/monte-carlo?n=${runs}`);
  const fmt = metric === "customers" ? "number" : "money";
  return (
    <div className="stack">
      <div className="row">
        <label className="row small" style={{ gap: 6 }}>Scenario
          <select className="select sm" value={sid} onChange={(e) => setSid(e.target.value)}>
            {scenarios.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </select>
        </label>
      </div>
      <Card title="Which assumptions matter most?" subtitle="One-at-a-time sensitivity: each assumption moved down and up while the others stay fixed."
        actions={<>
          <select className="select sm" aria-label="Metric" value={metric} onChange={(e) => setMetric(e.target.value)}>
            {Object.entries(METRIC_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <select className="select sm" aria-label="Change size" value={spread} onChange={(e) => setSpread(Number(e.target.value))}>
            {[0.1, 0.2, 0.3].map((p) => <option key={p} value={p}>±{pct(p)}</option>)}
          </select>
        </>}>
        {!sens ? <Spinner /> : (
          <div className="stack-sm">
            <Tornado title={`${METRIC_LABELS[metric]} when each assumption changes by ${pct(spread)}`}
              subtitle={`Base: ${metric === "customers" ? num(sens.base) : money(sens.base, currency)}. Longest bars first.`}
              base={sens.base} rows={sens.rows.slice(0, 10).map((r) => ({ label: r.label, low: r.low, high: r.high }))}
              fmt={fmt} currency={currency} pctLabel={pct(spread)} />
            {sens.rows[0] && (
              <Callout>
                <strong>{sens.rows[0].label}</strong> moves {METRIC_LABELS[metric].toLowerCase()} the most. Validate it first: its range is
                {" "}{metric === "customers" ? `${num(sens.rows[0].low)} to ${num(sens.rows[0].high)}` : `${money(sens.rows[0].low, currency, { compact: true })} to ${money(sens.rows[0].high, currency, { compact: true })}`}.
              </Callout>
            )}
          </div>
        )}
      </Card>
      <Card title="How likely is a profit?" subtitle="Monte Carlo simulation: uncertain assumptions are drawn from ranges based on their confidence, many times over."
        actions={<select className="select sm" aria-label="Runs" value={runs} onChange={(e) => setRuns(Number(e.target.value))}>
          {[500, 1000, 2000].map((n) => <option key={n} value={n}>{num(n)} runs</option>)}
        </select>}>
        {!mc ? <Spinner label="Simulating" /> : (
          <div className="stack">
            <div className="stats inline">
              <Stat label="Chance of a profit" value={pct(mc.probability_profit_positive)} delta={`${num(mc.runs)} runs, seed ${mc.seed}`} />
              <Stat label="Typical profit (median)" value={money(mc.profit.p50, currency, { compact: true })} />
              <Stat label="Bad case (10th percentile)" value={money(mc.profit.p10, currency, { compact: true })} deltaTone={mc.profit.p10 < 0 ? "down" : undefined}
                delta={mc.profit.p10 < 0 ? "Loss" : undefined} />
              <Stat label="Good case (90th percentile)" value={money(mc.profit.p90, currency, { compact: true })} />
            </div>
            <div style={{ opacity: isFetching ? 0.6 : 1 }}>
              <Histogram title="Distribution of simulated monthly profit" subtitle="Red bars are losses" bins={mc.profit_histogram} currency={currency}
                markers={[{ x: mc.profit.p10, label: "P10" }, { x: mc.profit.p50, label: "Median" }, { x: mc.profit.p90, label: "P90" }]} />
            </div>
            <div className="small muted">
              Customers per month: {num(mc.customers.p10)} to {num(mc.customers.p90)} (10th to 90th percentile).
              Revenue: {money(mc.revenue.p10, currency, { compact: true })} to {money(mc.revenue.p90, currency, { compact: true })}.
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

export function PriceView({ pid, baseline, currency }: { pid: string; baseline: Scenario; currency: string }) {
  const { data } = useApi<PriceCurve>([pid, "price-curve", baseline.id], `/projects/${pid}/scenarios/${baseline.id}/price-curve`);
  if (!data) return <Spinner />;
  const markers = [
    { x: data.current_price, label: "Current" },
    { x: data.profit_max_price, label: "Profit max" },
  ];
  const research = data.research;
  return (
    <div className="stack">
      <div>
        <div className="stats">
          <Stat label="Current price" value={money(data.current_price, currency)} />
          <Stat label="Profit-maximizing price" value={money(data.profit_max_price, currency)} hint="Within the tested price range" />
          <Stat label="Revenue-maximizing price" value={money(data.revenue_max_price, currency)} />
          <Stat label="Acceptable range (research)"
            value={<span style={{ fontSize: 17 }}>{research?.pmc ? `${money(research.pmc, currency)} to ${money(research.pme, currency)}` : "No Van Westendorp data"}</span>}
            delta={research?.opp ? `Optimal price point ${money(research.opp, currency)}` : undefined} />
        </div>
      </div>
      {data.tested_range && (
        <Callout>
          The survey tested prices from {money(data.tested_range[0], currency)} to {money(data.tested_range[1], currency)}. The optimum is searched only inside
          that range; the curves outside it are extrapolations, not evidence.
        </Callout>
      )}
      {research?.pme && data.profit_max_price > research.pme && (
        <Callout tone="warning">The model's profit-maximizing price is above the range most respondents find acceptable. Stated intent overstates demand at high prices; test before raising it.</Callout>
      )}
      <div className="grid grid-2">
        <Card><LineChart title="Monthly profit by price" subtitle="Simulated with all other assumptions fixed" xFmt="money" yFmt="money" currency={currency}
          xLabel="Price" markers={markers} zeroLine series={[{ name: "Profit", points: data.points.map((p) => ({ x: p.price, y: p.profit })) }]} /></Card>
        <Card><LineChart title="Monthly revenue by price" subtitle="Price times simulated customers" xFmt="money" yFmt="money" currency={currency}
          xLabel="Price" markers={[{ x: data.revenue_max_price, label: "Revenue max" }]} area
          series={[{ name: "Revenue", points: data.points.map((p) => ({ x: p.price, y: p.revenue })) }]} /></Card>
      </div>
      <Card><LineChart title="Customers per month by price" subtitle="The demand curve implied by the research price-response data" xFmt="money" yFmt="number" currency={currency}
        xLabel="Price" markers={research?.pmc ? [{ x: research.pmc, label: "Too cheap below" }, ...(research.pme ? [{ x: research.pme, label: "Too expensive above" }] : [])] : []}
        series={[{ name: "Customers", points: data.points.map((p) => ({ x: p.price, y: p.customers })) }]} /></Card>
    </div>
  );
}

export function MediaMix({ pid, baseline, currency }: { pid: string; baseline: Scenario; currency: string }) {
  const toast = useToast();
  const total = baseline.model.channels.reduce((a, c) => a + c.budget, 0);
  const [metric, setMetric] = useState("profit");
  const [budget, setBudget] = useState(String(total));
  const [result, setResult] = useState<Optimized | null>(null);
  const optimize = useProjectMutation(pid, () => api.post<Optimized>(`/projects/${pid}/scenarios/${baseline.id}/optimize-media`, { metric, total_budget: Number(budget) || null }));
  const save = useProjectMutation(pid, (r: Optimized) => api.post(`/projects/${pid}/scenarios`, {
    baseline_id: baseline.id, name: `Optimized media mix (${METRIC_LABELS[r.metric].toLowerCase()}, ${money(r.total_budget, currency, { compact: true })})`, levers: r.levers,
  }));
  const maxBudget = result ? Math.max(...result.allocation.flatMap((a) => [a.current, a.optimized]), 1) : 1;
  const pos = baseline.results.positioning;
  return (
    <div className="stack">
      <Card title="Media mix optimizer" subtitle="Allocates the budget where the next rupiah earns the most under the model's saturation curves.">
        <div className="stack">
          <div className="row">
            <label className="field" style={{ minWidth: 180 }}><span className="small">Optimize for</span>
              <select className="select" value={metric} onChange={(e) => setMetric(e.target.value)}>
                {Object.entries(METRIC_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select></label>
            <label className="field" style={{ minWidth: 220 }}><span className="small">Total monthly budget</span>
              <input className="input" type="number" value={budget} onChange={(e) => setBudget(e.target.value)} /></label>
            <button className="btn primary" style={{ alignSelf: "end" }} disabled={optimize.isPending} onClick={() => optimize.mutate(undefined, {
              onSuccess: setResult, onError: (e) => toast(errorMessage(e), "error"),
            })}><Icon name="play" size={14} />Optimize</button>
          </div>
          {result && (
            <div className="stack-sm">
              <div className="grid grid-3" style={{ gap: 0 }}>
                <Stat label={`${METRIC_LABELS[result.metric]} now`} value={result.metric === "customers" ? num(result.baseline_value) : money(result.baseline_value, currency, { compact: true })} />
                <Stat label="After optimizing" value={result.metric === "customers" ? num(result.optimized_value) : money(result.optimized_value, currency, { compact: true })}
                  delta={result.baseline_value ? `${result.optimized_value >= result.baseline_value ? "+" : ""}${pct((result.optimized_value - result.baseline_value) / Math.abs(result.baseline_value), 1)}` : undefined}
                  deltaTone={result.optimized_value >= result.baseline_value ? "up" : "down"} />
                <Stat label="Budget" value={money(result.total_budget, currency, { compact: true })} />
              </div>
              <div className="table-wrap">
                <table className="table">
                  <thead><tr><th>Channel</th><th className="num">Current</th><th className="num">Optimized</th><th style={{ width: "40%" }}>Current (gray) and optimized (blue)</th></tr></thead>
                  <tbody>
                    {result.allocation.map((a) => (
                      <tr key={a.key}>
                        <td>{a.name}</td>
                        <td className="num">{money(a.current, currency, { compact: true })}</td>
                        <td className="num">{money(a.optimized, currency, { compact: true })}</td>
                        <td>
                          <div aria-hidden style={{ display: "grid", gap: 2 }}>
                            <div style={{ height: 8, width: `${(a.current / maxBudget) * 100}%`, background: "var(--deemph)", borderRadius: "0 4px 4px 0" }} />
                            <div style={{ height: 8, width: `${(a.optimized / maxBudget) * 100}%`, background: "var(--series-1)", borderRadius: "0 4px 4px 0" }} />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <Callout>{result.note}</Callout>
              <div><button className="btn" disabled={save.isPending} onClick={() => save.mutate(result, {
                onSuccess: () => toast("Saved as a scenario. Compare it on the Scenarios tab."), onError: (e) => toast(errorMessage(e), "error"),
              })}>Save as scenario</button></div>
            </div>
          )}
        </div>
      </Card>
      {pos && pos.points.length > 1 && (
        <Card>
          <ScatterMap title="Positioning map" subtitle={`${pos.axes[0]} against ${pos.axes[1]} (research score, 1 to 5)`} xLabel={pos.axes[0]} yLabel={pos.axes[1]}
            xFmt={pos.axes[0] === "Price" ? "money" : "number"} currency={currency}
            points={pos.points.filter((p) => p.x !== null && p.y !== null).map((p) => ({ name: p.name, x: p.x as number, y: p.y as number, self: p.self }))} />
        </Card>
      )}
    </div>
  );
}
