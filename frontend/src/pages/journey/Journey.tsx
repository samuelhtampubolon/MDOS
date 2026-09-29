import { useEffect, useState } from "react";
import { api, errorMessage } from "../../api/client";
import { useApi, useDataset, useDatasets, useJourney, useJourneys, useProject, useProjectMutation } from "../../api/hooks";
import type { Journey as JourneyT, JourneyStage } from "../../api/types";
import { Heatmap, EmotionCurve } from "../../components/charts/special";
import { StartWorkflow } from "../../components/domain";
import { Badge, Callout, Card, Empty, Icon, PageHeader, Stat, StatusBadge, Tabs, useToast } from "../../components/ui";
import { compact, money, num, pct } from "../../lib/format";
import { Interventions, PainPoints } from "./JourneyParts";

type View = "map" | "pain" | "interventions" | "settings";

export default function Journey({ pid }: { pid: string }) {
  const { data: journeys } = useJourneys(pid);
  const [jid, setJid] = useState<string | undefined>();
  const [view, setView] = useState<View>("map");
  useEffect(() => {
    if (journeys?.length && (!jid || !journeys.some((j) => j.id === jid))) setJid(journeys[0].id);
  }, [journeys, jid]);
  const { data: journey } = useJourney(pid, jid);
  const { data: project } = useProject(pid);
  const currency = project?.currency ?? "IDR";
  return (
    <div>
      <PageHeader eyebrow="Journey Designer" title="Where do customers struggle, and what should we fix first?"
        description="Map the journey, find friction in reviews and comments, simulate improvements and turn the best ones into A/B tests."
        actions={journeys && journeys.length > 1 ? (
          <select className="select" aria-label="Journey" value={jid} onChange={(e) => setJid(e.target.value)}>
            {journeys.map((j) => <option key={j.id} value={j.id}>{j.name}</option>)}
          </select>
        ) : undefined} />
      {!journeys ? null : !journeys.length ? <NoJourney pid={pid} /> : !journey ? null : (
        <>
          <Tabs<View> value={view} onChange={setView} tabs={[
            { key: "map", label: "Journey map" },
            { key: "pain", label: `Pain points (${journey.pain_points.length})` },
            { key: "interventions", label: `Interventions (${journey.interventions.length})` },
            { key: "settings", label: "Stages and settings" },
          ]} />
          {view === "map" && <JourneyMap journey={journey} currency={currency} />}
          {view === "pain" && <PainPoints pid={pid} journey={journey} />}
          {view === "interventions" && <Interventions pid={pid} journey={journey} currency={currency} />}
          {view === "settings" && <JourneySettings pid={pid} journey={journey} currency={currency} />}
        </>
      )}
    </div>
  );
}

function NoJourney({ pid }: { pid: string }) {
  const toast = useToast();
  const { data: templates } = useApi<{ key: string; name: string; entrants: number; stages: { key: string; name: string }[] }[]>(
    [pid, "journey-templates"], `/projects/${pid}/journey-templates`);
  const { data: datasets } = useDatasets(pid);
  const [form, setForm] = useState({ name: "Customer journey", template: "tourism" });
  const create = useProjectMutation(pid, () => api.post(`/projects/${pid}/journeys`, form));
  const reviews = datasets?.find((d) => d.kind === "reviews");
  return (
    <div className="grid grid-2">
      <Card title="Map from reviews with the agents" subtitle="Voice of Customer, Journey Mapping, Pain Point, Experience Opportunity, Journey Simulation and Experiment Design.">
        {reviews ? (
          <div className="stack-sm">
            <span className="small secondary">Uses <strong>{reviews.name}</strong>. The agents map each review sentence to a stage, score its sentiment and cluster friction themes.</span>
            <div><StartWorkflow pid={pid} workflow="journey_voc" label="Run journey agents" inputs={{ reviews_dataset_id: reviews.id }} /></div>
          </div>
        ) : (
          <Empty title="No reviews uploaded">Upload reviews or open comments (kind: reviews) in the Data workspace, then run the journey agents.</Empty>
        )}
      </Card>
      <Card title="Start from a template">
        <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); create.mutate(undefined, { onSuccess: () => toast("Journey created."), onError: (er) => toast(errorMessage(er), "error") }); }}>
          <div className="field"><label htmlFor="j-name">Name</label>
            <input id="j-name" className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="field"><label htmlFor="j-tpl">Template</label>
            <select id="j-tpl" className="select" value={form.template} onChange={(e) => setForm({ ...form, template: e.target.value })}>
              {(templates ?? []).map((t) => <option key={t.key} value={t.key}>{t.name}</option>)}
            </select>
            <span className="hint">{templates?.find((t) => t.key === form.template)?.stages.map((s) => s.name).join(", ")}</span></div>
          <div><button className="btn primary" disabled={create.isPending}><Icon name="plus" size={14} />Create journey</button></div>
        </form>
      </Card>
    </div>
  );
}

function emotionLabel(v: number | null): { text: string; tone: string } {
  if (v === null) return { text: "No mentions", tone: "" };
  if (v >= 0.15) return { text: "Positive", tone: "good" };
  if (v <= -0.15) return { text: "Negative", tone: "critical" };
  return { text: "Mixed", tone: "warning" };
}

function StageColumn({ stage, touchpoints }: { stage: JourneyStage; touchpoints: JourneyT["touchpoints"] }) {
  const e = emotionLabel(stage.emotion);
  return (
    <div className="card flat" style={{ minWidth: 190, flex: "1 0 190px", padding: 12 }}>
      <div className="stack-sm">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <strong>{stage.name}</strong>
          {stage.kind === "outcome" && <Badge>Outcome</Badge>}
        </div>
        <div className="small muted">{stage.description}</div>
        <div className="row" style={{ gap: 6 }}>
          <span className={`badge ${e.tone}`}><Icon name={e.tone === "good" ? "check" : e.tone === "critical" ? "alert" : "info"} size={12} />{e.text}</span>
          <span className="small muted">{stage.mentions} reviews</span>
        </div>
        <div className="small">
          {stage.kind === "funnel" ? <>Continue rate <strong>{pct(stage.conversion ?? null)}</strong></> : <>Rate <strong>{pct(stage.rate ?? null)}</strong></>}
          {stage.negative_share !== null && stage.mentions > 0 && <span className="muted"> · {pct(stage.negative_share)} negative</span>}
        </div>
        {touchpoints.length > 0 && (
          <div className="stack-sm" style={{ gap: 4 }}>
            <div className="small muted">Touchpoints</div>
            {touchpoints.map((t) => <span key={t.id} className="chip" title={t.channel}>{t.name}</span>)}
          </div>
        )}
        {stage.top_negative && stage.top_negative.length > 0 && (
          <blockquote className="small secondary" style={{ margin: 0, paddingLeft: 8, borderLeft: "2px solid var(--div-neg)" }} lang="id">"{stage.top_negative[0]}"</blockquote>
        )}
        {stage.top_positive && stage.top_positive.length > 0 && (
          <blockquote className="small secondary" style={{ margin: 0, paddingLeft: 8, borderLeft: "2px solid var(--div-pos)" }}>"{stage.top_positive[0]}"</blockquote>
        )}
      </div>
    </div>
  );
}

function JourneyMap({ journey, currency }: { journey: JourneyT; currency: string }) {
  const sim = journey.simulation;
  const heat = journey.voc.heatmap;
  return (
    <div className="stack">
      {journey.voc.summary ? <Callout icon="sparkles">{journey.voc.summary}</Callout> : (
        <Callout tone="warning">No voice-of-customer data yet. Run the analysis on reviews in the <strong>Stages and settings</strong> tab to fill in emotions and friction.</Callout>
      )}
      <div className="card">
        <div className="grid grid-4" style={{ gap: 0 }}>
          <Stat label="People entering per month" value={compact(sim.entrants)} hint={String(journey.settings.entrants_source ?? "")} />
          <Stat label="Customers per month" value={num(sim.total_customers)} delta={`${num(sim.wom_customers)} from word of mouth`} />
          <Stat label="Journey conversion" value={pct(sim.customers / (sim.entrants || 1), 2)} />
          <Stat label="Revenue per month" value={money(sim.revenue, currency, { compact: true })} delta={`at ${money(journey.settings.price ?? null, currency)} per customer`} />
        </div>
      </div>
      <div style={{ display: "flex", gap: 10, overflowX: "auto", paddingBottom: 6 }} aria-label="Journey stages">
        {journey.stages.map((s) => <StageColumn key={s.key} stage={s} touchpoints={journey.touchpoints.filter((t) => t.stage_key === s.key)} />)}
      </div>
      <div className="grid grid-2">
        <Card><EmotionCurve title="Emotion along the journey" subtitle="Mean sentiment of review sentences mapped to each stage (−1 to +1)"
          data={journey.stages.map((s) => ({ label: s.name, value: s.emotion, n: s.mentions }))} /></Card>
        {heat && heat.themes.length > 0 ? (
          <Card><Heatmap title="Where friction concentrates" subtitle="Reviews with a negative mention, by stage and theme" rows={heat.stages} cols={heat.themes}
            data={heat.counts} fmt="number" /></Card>
        ) : <Card title="Where friction concentrates"><span className="muted small">No negative themes found yet.</span></Card>}
      </div>
      <Card title="Simulated funnel" subtitle="People continuing at each stage with the current continue rates">
        <div className="flow">
          {sim.funnel.map((f, i) => (
            <div key={f.key} className="row" style={{ flex: "1 0 120px", gap: 6, flexWrap: "nowrap" }}>
              <div className="flow-step" style={{ flex: 1 }}>
                <div className="flow-label">{f.name}</div>
                <div className="flow-value">{compact(f.entering)}</div>
                <div className="flow-unit">{pct(f.conversion)} continue</div>
              </div>
              {i < sim.funnel.length - 1 && <span className="flow-arrow"><Icon name="arrowRight" size={14} /></span>}
            </div>
          ))}
        </div>
        <div className="small muted" style={{ marginTop: 8 }}>
          After the experience: {num(sim.sharers)} share it, {num(sim.recommenders)} recommend it and {num(sim.returners)} come back.
        </div>
      </Card>
    </div>
  );
}

function JourneySettings({ pid, journey, currency }: { pid: string; journey: JourneyT; currency: string }) {
  const toast = useToast();
  const [stages, setStages] = useState(journey.stages);
  const [settings, setSettings] = useState({ entrants: journey.settings.entrants ?? 10000, price: journey.settings.price ?? 0 });
  useEffect(() => {
    setStages(journey.stages);
    setSettings({ entrants: journey.settings.entrants ?? 10000, price: journey.settings.price ?? 0 });
  }, [journey]);
  const save = useProjectMutation(pid, () => api.patch(`/projects/${pid}/journeys/${journey.id}`, {
    stages, settings: { ...journey.settings, ...settings, entrants_source: "set by a person" },
  }));
  const adopt = useProjectMutation(pid, () => api.patch(`/projects/${pid}/journeys/${journey.id}`, { status: journey.status === "adopted" ? "draft" : "adopted" }));
  return (
    <div className="stack">
      <div className="grid grid-2">
        <Card title="Journey settings" actions={<StatusBadge status={journey.status} />}>
          <div className="stack-sm">
            <div className="grid grid-2">
              <div className="field"><label htmlFor="js-e">People entering per month</label>
                <input id="js-e" className="input" type="number" value={settings.entrants} onChange={(e) => setSettings({ ...settings, entrants: Number(e.target.value) })} />
                <span className="hint">{String(journey.settings.entrants_source ?? "")}</span></div>
              <div className="field"><label htmlFor="js-p">Price per customer</label>
                <input id="js-p" className="input" type="number" value={settings.price} onChange={(e) => setSettings({ ...settings, price: Number(e.target.value) })} />
                <span className="hint">{money(settings.price, currency)}</span></div>
            </div>
            <div className="row">
              <button className="btn primary" disabled={save.isPending} onClick={() => save.mutate(undefined, {
                onSuccess: () => toast("Journey saved and re-simulated."), onError: (e) => toast(errorMessage(e), "error"),
              })}>Save and re-simulate</button>
              <button className="btn" onClick={() => adopt.mutate(undefined, { onError: (e) => toast(errorMessage(e), "error") })}>
                {journey.status === "adopted" ? "Return to draft" : "Adopt this journey"}</button>
            </div>
          </div>
        </Card>
        <VocRunner pid={pid} journey={journey} />
      </div>
      <Touchpoints pid={pid} journey={journey} />
      <Card title="Stage continue rates" subtitle="Share of people who move on to the next stage. Template defaults are assumptions; replace them with analytics or booking data.">
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Stage</th><th>Type</th><th className="num">Rate (%)</th><th>Source</th></tr></thead>
            <tbody>
              {stages.map((s, i) => {
                const field = s.kind === "funnel" ? "conversion" : "rate";
                const value = (s[field] as number | undefined) ?? 0;
                return (
                  <tr key={s.key}>
                    <td>{s.name}</td>
                    <td className="small">{s.kind === "funnel" ? "Continue to next stage" : "Outcome rate"}</td>
                    <td className="num">
                      <input className="input sm num" type="number" step="any" min={0} max={100} aria-label={`${s.name} rate`} style={{ width: 90, textAlign: "right" }}
                        value={+(value * 100).toFixed(2)}
                        onChange={(e) => setStages(stages.map((x, j) => (j === i ? { ...x, [field]: Number(e.target.value) / 100, assumption_source: "set by a person" } : x)))} />
                    </td>
                    <td className="small muted">{s.assumption_source ?? ""}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Touchpoints({ pid, journey }: { pid: string; journey: JourneyT }) {
  const toast = useToast();
  const [form, setForm] = useState({ stage_key: journey.stages[0]?.key ?? "", name: "", channel: "" });
  const add = useProjectMutation(pid, () => api.post(`/projects/${pid}/journeys/${journey.id}/touchpoints`, form));
  const remove = useProjectMutation(pid, (tid: string) => api.del(`/projects/${pid}/journeys/${journey.id}/touchpoints/${tid}`));
  return (
    <Card title="Touchpoints" subtitle="Where customers meet the offer at each stage: channels, pages, people and places.">
      <div className="stack-sm">
        <div className="table-wrap">
          <table className="table">
            <thead><tr><th>Stage</th><th>Touchpoint</th><th>Channel</th><th /></tr></thead>
            <tbody>
              {journey.touchpoints.map((t) => (
                <tr key={t.id}>
                  <td>{journey.stages.find((s) => s.key === t.stage_key)?.name ?? t.stage_key}</td>
                  <td>{t.name}</td>
                  <td className="small secondary">{t.channel}</td>
                  <td><button className="btn ghost icon sm" aria-label={`Remove ${t.name}`}
                    onClick={() => remove.mutate(t.id, { onError: (e) => toast(errorMessage(e), "error") })}><Icon name="trash" size={14} /></button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <form className="row" onSubmit={(e) => { e.preventDefault(); add.mutate(undefined, {
          onSuccess: () => { toast("Touchpoint added."); setForm({ ...form, name: "", channel: "" }); }, onError: (er) => toast(errorMessage(er), "error"),
        }); }}>
          <select className="select sm" aria-label="Stage" value={form.stage_key} onChange={(e) => setForm({ ...form, stage_key: e.target.value })}>
            {journey.stages.map((s) => <option key={s.key} value={s.key}>{s.name}</option>)}
          </select>
          <input className="input sm" required placeholder="Touchpoint, for example WhatsApp booking" aria-label="Touchpoint name" style={{ width: 280 }}
            value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <input className="input sm" placeholder="Channel, for example Messaging" aria-label="Channel" style={{ width: 220 }}
            value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })} />
          <button className="btn sm primary" disabled={add.isPending}><Icon name="plus" size={12} />Add</button>
        </form>
      </div>
    </Card>
  );
}

function VocRunner({ pid, journey }: { pid: string; journey: JourneyT }) {
  const toast = useToast();
  const { data: datasets } = useDatasets(pid);
  const textSets = (datasets ?? []).filter((d) => d.kind === "reviews" || d.kind === "survey");
  const [did, setDid] = useState<string | undefined>();
  useEffect(() => {
    if (!did && textSets.length) setDid((textSets.find((d) => d.kind === "reviews") ?? textSets[0]).id);
  }, [textSets, did]);
  const { data: dataset } = useDataset(pid, did);
  const version = dataset?.versions?.find((v) => v.id === dataset.current_version_id);
  const textCols = (version?.columns ?? []).filter((c) => (c.type ?? c.inferred_type) === "text");
  const numCols = (version?.columns ?? []).filter((c) => ["numeric", "likert"].includes(c.type ?? c.inferred_type));
  const [text, setText] = useState("");
  const [rating, setRating] = useState("");
  useEffect(() => {
    setText(textCols[0]?.name ?? "");
    setRating(numCols.find((c) => /rating|star|score/i.test(c.name))?.name ?? "");
  }, [version?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const run = useProjectMutation(pid, () => api.post(`/projects/${pid}/journeys/${journey.id}/voc`, {
    dataset_version_id: version?.id, text_column: text, rating_column: rating || null,
  }));
  return (
    <Card title="Voice of the customer" subtitle="Map review sentences to stages, score sentiment and find friction themes.">
      {!textSets.length ? <span className="small muted">Upload reviews or open comments in the Data workspace first.</span> : (
        <div className="stack-sm">
          <div className="grid grid-3">
            <div className="field"><label htmlFor="voc-ds">Dataset</label>
              <select id="voc-ds" className="select" value={did ?? ""} onChange={(e) => setDid(e.target.value)}>
                {textSets.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select></div>
            <div className="field"><label htmlFor="voc-t">Text column</label>
              <select id="voc-t" className="select" value={text} onChange={(e) => setText(e.target.value)}>
                {textCols.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
              </select></div>
            <div className="field"><label htmlFor="voc-r">Rating (optional)</label>
              <select id="voc-r" className="select" value={rating} onChange={(e) => setRating(e.target.value)}>
                <option value="">None</option>{numCols.map((c) => <option key={c.name} value={c.name}>{c.name}</option>)}
              </select></div>
          </div>
          <div><button className="btn primary" disabled={!version || !text || run.isPending} onClick={() => run.mutate(undefined, {
            onSuccess: () => toast("Voice-of-customer analysis complete. Pain points were updated."), onError: (e) => toast(errorMessage(e), "error"),
          })}><Icon name="play" size={14} />{run.isPending ? "Analyzing" : "Analyze reviews"}</button></div>
          {typeof journey.voc.coverage === "number" && (
            <div className="small muted">Last run mapped {pct(journey.voc.coverage, 1)} of texts to a stage
              {typeof journey.voc.rating_correlation === "number" ? `; sentiment correlates with ratings at r = ${num(journey.voc.rating_correlation, 2)}` : ""}.</div>
          )}
        </div>
      )}
    </Card>
  );
}
