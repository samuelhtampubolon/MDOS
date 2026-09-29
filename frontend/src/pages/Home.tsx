import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { useProjects, useProvider } from "../api/hooks";
import type { Project } from "../api/types";
import { useQueryClient } from "@tanstack/react-query";
import { Badge, Callout, Card, Empty, Icon, PageHeader, useToast } from "../components/ui";
import { dateTime } from "../lib/format";

const LOOP = [
  { title: "Customer and market data", note: "Surveys, reviews, comments" },
  { title: "Research Lab", note: "Design, clean, analyze" },
  { title: "Market understanding", note: "Evidence and insights" },
  { title: "Strategy Simulator", note: "Price, media, segments" },
  { title: "Decisions and scenarios", note: "Approved by people" },
  { title: "Journey Designer", note: "Friction to interventions" },
  { title: "Experimentation", note: "A/B tests with power" },
  { title: "Results", note: "Back to research as evidence" },
];

export function ClosedLoop() {
  return (
    <div className="loop" aria-label="The closed loop from data to results and back to research">
      {LOOP.map((n, i) => (
        <div key={n.title} className="loop-node">
          <strong>{i + 1}. {n.title}</strong>
          <span className="muted">{n.note}</span>
        </div>
      ))}
    </div>
  );
}

function NewProject() {
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [form, setForm] = useState({ name: "", business_question: "", decision_to_inform: "", industry: "", currency: "IDR" });
  const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const p = await api.post<Project>("/projects", form);
      await qc.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/p/${p.id}/research`);
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="stack-sm" onSubmit={submit}>
      <div className="field">
        <label htmlFor="bq">Business question</label>
        <textarea id="bq" className="textarea" required minLength={10} placeholder="For example: Would tourists pay Rp 150,000 for a new Lake Toba cultural experience?"
          value={form.business_question} onChange={(e) => setForm({ ...form, business_question: e.target.value })} />
        <span className="hint">Write the decision-relevant question in plain language. Prices such as "Rp 150.000" or "150 ribu" are recognized.</span>
      </div>
      <div className="grid grid-2">
        <div className="field">
          <label htmlFor="pname">Project name</label>
          <input id="pname" className="input" required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="industry">Industry</label>
          <select id="industry" className="select" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })}>
            <option value="">General</option>
            <option value="tourism">Tourism and hospitality</option>
            <option value="retail">Retail</option>
            <option value="food">Food and beverage</option>
            <option value="education">Education</option>
            <option value="services">Services</option>
          </select>
        </div>
      </div>
      <div className="grid grid-2">
        <div className="field">
          <label htmlFor="decision">Decision to inform (optional)</label>
          <input id="decision" className="input" value={form.decision_to_inform} onChange={(e) => setForm({ ...form, decision_to_inform: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="currency">Currency</label>
          <select id="currency" className="select" value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value })}>
            {["IDR", "USD", "SGD", "MYR", "EUR"].map((c) => <option key={c}>{c}</option>)}
          </select>
        </div>
      </div>
      <div><button className="btn primary" disabled={busy}><Icon name="plus" size={14} />Create project</button></div>
    </form>
  );
}

export default function Home() {
  const { data: projects, isLoading } = useProjects();
  const { data: provider } = useProvider();
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();
  const [demoBusy, setDemoBusy] = useState(false);
  const loadDemo = async () => {
    setDemoBusy(true);
    try {
      const p = await api.post<Project>("/projects/demo");
      await qc.invalidateQueries({ queryKey: ["projects"] });
      navigate(`/p/${p.id}/research`);
    } catch (err) {
      toast(errorMessage(err), "error");
    } finally {
      setDemoBusy(false);
    }
  };
  return (
    <div className="stack">
      <PageHeader eyebrow="Marketing Decision OS" title="From business question to defensible marketing evidence"
        description="Design research, analyze data with visible assumptions, simulate strategy on evidence, and redesign customer journeys you can test. Agents draft; people decide."
        actions={<button className="btn lg" onClick={loadDemo} disabled={demoBusy}><Icon name="play" size={14} />{demoBusy ? "Building demo" : "Load the Lake Toba demo"}</button>} />
      {provider && (
        <Callout tone={provider.mode === "claude" ? "good" : "info"} icon="sparkles">
          <strong>{provider.mode === "claude" ? `Claude drafting on (${provider.model})` : "Offline mode"}.</strong> {provider.note}
        </Callout>
      )}
      <div className="grid grid-2">
        <Card title="Start a project" subtitle="The Research Director agent turns your question into a research design.">
          <NewProject />
        </Card>
        <Card title="The closed loop" subtitle="Research findings feed strategy, strategy feeds the journey, experiments feed research.">
          <ClosedLoop />
        </Card>
      </div>
      <Card title="Projects" subtitle={projects ? `${projects.length} in this workspace` : undefined}>
        {isLoading ? <span className="muted">Loading</span> : !projects?.length ? (
          <Empty title="No projects yet">Create one above, or load the demo to see the full loop on synthetic data.</Empty>
        ) : (
          <div className="grid grid-auto">
            {projects.map((p) => (
              <Link key={p.id} to={`/p/${p.id}/research`} className="card flat" style={{ color: "inherit", textDecoration: "none" }}>
                <div className="card-body stack-sm">
                  <div className="row" style={{ justifyContent: "space-between" }}>
                    <strong>{p.name}</strong>
                    {p.is_demo && <Badge tone="warning">Synthetic demo</Badge>}
                  </div>
                  <span className="small secondary">{p.business_question}</span>
                  <span className="small muted">{p.currency} · {p.industry || "general"} · created {dateTime(p.created_at)}</span>
                </div>
              </Link>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
