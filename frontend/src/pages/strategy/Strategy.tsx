import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useProject, useProjectMutation, useScenarios, useWorkflows } from "../../api/hooks";
import type { Scenario } from "../../api/types";
import { BarChart } from "../../components/charts/basic";
import { Waterfall } from "../../components/charts/special";
import { StartWorkflow } from "../../components/domain";
import { Callout, Card, Empty, Icon, PageHeader, Stat, StatusBadge, Tabs, useToast } from "../../components/ui";
import { compact, money, num, pct, sentence, signedPct } from "../../lib/format";
import Decisions from "./Decisions";
import ModelCanvas from "./ModelCanvas";
import { MediaMix, PriceView, RiskView } from "./StrategyAnalysis";
import { ScenarioBuilder } from "./ScenarioBuilder";

type View = "scenarios" | "model" | "risk" | "price" | "media" | "decisions";

const METRIC_NAMES: Record<string, string> = { romi: "ROMI", cac: "CAC", clv: "CLV", gross_margin: "Gross margin", spend: "Media spend" };

export default function Strategy({ pid }: { pid: string }) {
  const { data: project } = useProject(pid);
  const { data: scenarios } = useScenarios(pid);
  const { data: workflows } = useWorkflows(pid);
  const [view, setView] = useState<View>("scenarios");
  const toast = useToast();
  const build = useProjectMutation(pid, () => api.post(`/projects/${pid}/scenarios/baseline`, {}));
  const baseline = scenarios?.find((s) => s.kind === "baseline");
  const running = workflows?.some((w) => w.workflow === "strategy_baseline" && ["queued", "running"].includes(w.status));
  const currency = project?.currency ?? "IDR";
  return (
    <div>
      <PageHeader eyebrow="Strategy Simulator" title="What happens if we change the price, the media mix or the audience?"
        description="Every scenario runs on an explicit market model. Assumptions show their source: research evidence, a benchmark, expert judgment or a guess."
        actions={baseline ? <StartWorkflow pid={pid} workflow="strategy_baseline" label="Re-run strategy agents" primary={false} /> : undefined} />
      {!scenarios ? null : !baseline ? (
        <Card>
          <Empty title="No market model yet" action={
            <div className="row" style={{ justifyContent: "center" }}>
              <StartWorkflow pid={pid} workflow="strategy_baseline" label="Run strategy agents" />
              <button className="btn" disabled={build.isPending || running} onClick={() => build.mutate(undefined, {
                onSuccess: () => toast("Baseline built from research evidence."), onError: (e) => toast(errorMessage(e), "error"),
              })}>Build baseline only</button>
            </div>
          }>
            The Market Model agent builds a baseline from your research evidence (price response, willingness to pay by segment, segment shares)
            and fills the gaps with labeled placeholders you should replace. It then runs what-if scenarios, sensitivity and a risk simulation.
          </Empty>
        </Card>
      ) : (
        <>
          <Tabs<View> value={view} onChange={setView} tabs={[
            { key: "scenarios", label: "Scenarios" }, { key: "model", label: "Model and assumptions" }, { key: "risk", label: "Sensitivity and risk" },
            { key: "price", label: "Price" }, { key: "media", label: "Media mix and positioning" }, { key: "decisions", label: "Decision log" },
          ]} />
          {view === "scenarios" && <Scenarios pid={pid} scenarios={scenarios} baseline={baseline} currency={currency} />}
          {view === "model" && <ModelCanvas pid={pid} baseline={baseline} currency={currency} />}
          {view === "risk" && <RiskView pid={pid} scenarios={scenarios} currency={currency} />}
          {view === "price" && <PriceView pid={pid} baseline={baseline} currency={currency} />}
          {view === "media" && <MediaMix pid={pid} baseline={baseline} currency={currency} />}
          {view === "decisions" && <Decisions pid={pid} scenarios={scenarios} currency={currency} />}
        </>
      )}
    </div>
  );
}

function Scenarios({ pid, scenarios, baseline, currency }: { pid: string; scenarios: Scenario[]; baseline: Scenario; currency: string }) {
  const children = scenarios.filter((s) => s.kind === "scenario");
  // A new scenario is selected before the list refreshes; until it arrives (or after a delete) the baseline shows.
  const [selected, setSelected] = useState<string>(children[0]?.id ?? baseline.id);
  const current = scenarios.find((s) => s.id === selected) ?? baseline;
  const ranked = [baseline, ...children].map((s) => ({ label: s.name, value: s.results.kpis.profit })).sort((a, b) => b.value - a.value);
  return (
    <div className="stack">
      <Callout icon="info">
        Numbers are simulated from the model, not forecasts. Assumptions marked as a guess or benchmark need your own data before a decision.
        See <strong>Model and assumptions</strong>.
      </Callout>
      <div className="row" role="tablist" aria-label="Scenarios" style={{ gap: 6 }}>
        {[baseline, ...children].map((s) => (
          <button key={s.id} role="tab" aria-selected={s.id === current.id} className={`btn sm ${s.id === current.id ? "primary" : ""}`} onClick={() => setSelected(s.id)}>
            {s.kind === "baseline" && <Icon name="flag" size={12} />}{s.name}
          </button>
        ))}
      </div>
      <ScenarioDetail pid={pid} scenario={current} baseline={baseline} currency={currency} />
      <div className="grid grid-2">
        <Card><BarChart title="Monthly profit by scenario" subtitle="Simulated from the market model, sorted from highest to lowest" data={ranked} fmt="money" currency={currency} /></Card>
        <ScenarioBuilder pid={pid} baseline={baseline} currency={currency} onCreated={setSelected} />
      </div>
    </div>
  );
}

function FlowStrip({ scenario, baseline, currency }: { scenario: Scenario; baseline: Scenario; currency: string }) {
  const base = new Map(baseline.results.funnel.map((f) => [f.stage, f.value]));
  const isScenario = scenario.id !== baseline.id;
  return (
    <div className="flow" aria-label="Marketing funnel from budget to profit">
      {scenario.results.funnel.map((f, i) => {
        const isMoney = f.unit === currency;
        const b = base.get(f.stage);
        const delta = isScenario && b ? (f.value - b) / Math.abs(b) : null;
        return (
          <div key={f.stage} className="row" style={{ flex: "1 0 128px", gap: 6, flexWrap: "nowrap" }}>
            <div className="flow-step" style={{ flex: 1 }}>
              <div className="flow-label">{f.stage}</div>
              <div className="flow-value" style={{ color: f.stage === "Profit" && f.value < 0 ? "var(--critical-text)" : undefined }}>
                {isMoney ? money(f.value, currency, { compact: true }) : compact(f.value)}
              </div>
              <div className="flow-unit">
                {isMoney ? "per month" : f.unit}
                {delta !== null && Math.abs(delta) > 0.0005 && <span style={{ marginLeft: 6, fontWeight: 600 }}>{signedPct(delta, 1)}</span>}
              </div>
            </div>
            {i < scenario.results.funnel.length - 1 && <span className="flow-arrow"><Icon name="arrowRight" size={14} /></span>}
          </div>
        );
      })}
    </div>
  );
}

function ScenarioDetail({ pid, scenario, baseline, currency }: { pid: string; scenario: Scenario; baseline: Scenario; currency: string }) {
  const toast = useToast();
  const remove = useProjectMutation(pid, () => api.del(`/projects/${pid}/scenarios/${scenario.id}`));
  const k = scenario.results.kpis;
  const isScenario = scenario.kind === "scenario";
  const cmp = scenario.results.comparison;
  return (
    <div className="stack">
      <Card title={scenario.name} subtitle={isScenario ? (scenario.results.lever_descriptions ?? []).join(" · ") : "Baseline built from research evidence and labeled assumptions"}
        actions={<>
          <StatusBadge status={scenario.status} />
          {isScenario && <button className="btn ghost icon sm" aria-label="Delete scenario" onClick={() => window.confirm(`Delete scenario "${scenario.name}"?`)
            && remove.mutate(undefined, { onSuccess: () => toast("Scenario deleted."), onError: (e) => toast(errorMessage(e), "error") })}><Icon name="trash" size={14} /></button>}
        </>}>
        <div className="stack">
          <FlowStrip scenario={scenario} baseline={baseline} currency={currency} />
          <div className="grid grid-4" style={{ gap: 0 }}>
            <Stat label="Customers per month" value={num(k.customers)} delta={cmp ? signedPct(cmp.customers?.pct, 1) : `${num(k.referrals)} from word of mouth`} />
            <Stat label="Profit per month" value={money(k.profit, currency, { compact: true })} delta={cmp ? `${cmp.profit.delta >= 0 ? "+" : ""}${money(cmp.profit.delta, currency, { compact: true })} vs baseline` : `Break-even at ${num(k.break_even_customers)} customers`}
              deltaTone={cmp ? (cmp.profit.delta >= 0 ? "up" : "down") : undefined} />
            <Stat label="Return on marketing" value={k.romi !== null ? `${num(k.romi, 2)}x` : "n/a"} delta={`CAC ${money(k.cac, currency, { compact: true })}`} />
            <Stat label="Customer lifetime value" value={money(k.clv, currency, { compact: true })} delta={k.clv_to_cac !== null ? `${num(k.clv_to_cac, 1)}x CAC` : undefined} />
          </div>
          <div className="small muted">
            Price {money(k.price, currency)} · break-even price {money(scenario.results.break_even_price, currency)} · market penetration {pct(k.market_penetration, 2)}
          </div>
        </div>
      </Card>
      {isScenario && scenario.results.waterfall && (
        <div className="grid grid-2">
          <Card><Waterfall title="Profit bridge from the baseline" subtitle="Each lever applied in order" steps={scenario.results.waterfall} currency={currency} /></Card>
          <Card title="Scenario versus baseline">
            <div className="table-wrap">
              <table className="table">
                <thead><tr><th>Metric</th><th className="num">Baseline</th><th className="num">Scenario</th><th className="num">Change</th></tr></thead>
                <tbody>
                  {Object.entries(cmp ?? {}).map(([key, v]) => {
                    const isMoney = ["revenue", "profit", "spend", "cac", "clv", "gross_margin", "commission", "fixed_costs"].includes(key);
                    const f = (x: number) => (isMoney ? money(x, currency, { compact: true }) : key === "romi" ? `${num(x, 2)}x` : num(x));
                    return (
                      <tr key={key}>
                        <td>{METRIC_NAMES[key] ?? sentence(key)}</td>
                        <td className="num">{f(v.baseline)}</td><td className="num">{f(v.scenario)}</td>
                        <td className="num">{v.pct !== null ? signedPct(v.pct, 1) : ""}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
      <div className="grid grid-2">
        <Card title="Channels" subtitle="Spend, reach and customers by channel">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Channel</th><th className="num">Spend</th><th className="num">Reach</th><th className="num">Customers</th><th className="num">CAC</th><th className="num">ROMI</th></tr></thead>
              <tbody>
                {scenario.results.channels.map((c) => (
                  <tr key={c.key}>
                    <td>{c.name}</td><td className="num">{money(c.spend, currency, { compact: true })}</td><td className="num">{compact(c.reach)}</td>
                    <td className="num">{num(c.customers)}</td><td className="num">{money(c.cac, currency, { compact: true })}</td>
                    <td className="num">{c.romi !== null ? `${num(c.romi, 2)}x` : "n/a"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
        <Card title="Segments" subtitle="Who buys under this scenario">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Segment</th><th className="num">Customers</th><th className="num">Share</th><th className="num">Revenue</th><th className="num">CLV</th></tr></thead>
              <tbody>
                {scenario.results.segments.map((s) => (
                  <tr key={s.key}>
                    <td>{s.name}</td><td className="num">{num(s.customers)}</td><td className="num">{pct(s.share_of_customers)}</td>
                    <td className="num">{money(s.revenue, currency, { compact: true })}</td><td className="num">{money(s.clv, currency, { compact: true })}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {scenario.model.segments.some((s) => s.needs.length) && (
            <div className="stack-sm" style={{ marginTop: 10 }}>
              {scenario.model.segments.map((s) => (
                <div key={s.key} className="small"><strong>{s.name}:</strong> <span className="secondary">{s.needs.join(", ")}</span></div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
