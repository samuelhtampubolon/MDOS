import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { useProjects, useProvider } from "../api/hooks";
import type { Project } from "../api/types";
import { useQueryClient } from "@tanstack/react-query";
import { Badge, Callout, Card, Icon, PageHeader, useToast } from "../components/ui";
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

function ProjectList({ projects }: { projects: Project[] }) {
  return (
    <ul className="project-list">
      {projects.map((p) => (
        <li key={p.id}>
          <Link to={`/p/${p.id}/research`} className="project-row">
            <span className="project-name">{p.name}</span>
            {p.is_demo ? <Badge tone="warning">Synthetic demo</Badge> : <span />}
            <span className="project-question">{p.business_question}</span>
            <span className="project-meta">{p.currency} · {p.industry || "general"} · created {dateTime(p.created_at)}</span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function ListSkeleton() {
  return (
    <div aria-hidden className="stack-sm" style={{ paddingTop: 8 }}>
      {[0, 1, 2].map((i) => (
        <div key={i}>
          <span className="skeleton skeleton-line" style={{ width: "40%" }} />
          <span className="skeleton skeleton-line" style={{ width: "75%" }} />
        </div>
      ))}
    </div>
  );
}

export default function Home() {
  const { data: projects, isLoading, error } = useProjects();
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
  const firstRun = !isLoading && !error && !projects?.length;
  const demoButton = (
    <button className="btn" onClick={loadDemo} disabled={demoBusy}>
      <Icon name="play" size={14} />{demoBusy ? "Building the demo" : "Load the Lake Toba demo"}
    </button>
  );
  return (
    <div className="stack" style={{ gap: 32 }}>
      <PageHeader title="From business question to defensible marketing evidence"
        description="Design research, analyze data with visible assumptions, simulate strategy on evidence and redesign customer journeys you can test. Agents draft; people decide."
        actions={firstRun ? undefined : demoButton} />
      {provider && (
        <Callout tone={provider.mode === "claude" ? "good" : "info"} icon={provider.mode === "claude" ? "check" : "info"}>
          <strong>{provider.mode === "claude" ? `Claude drafting is on (${provider.model}).` : "Offline mode."}</strong> {provider.note}
        </Callout>
      )}
      {!firstRun && (
        <section aria-labelledby="projects-title">
          <div className="section-title">
            <h2 id="projects-title">Projects</h2>
            {projects && <p>{projects.length} in this workspace</p>}
          </div>
          {isLoading ? <ListSkeleton /> : error ? (
            <Callout tone="critical">Your projects could not be loaded: {errorMessage(error)}</Callout>
          ) : <ProjectList projects={projects ?? []} />}
        </section>
      )}
      <div className="grid grid-2 align-start">
        <Card title={firstRun ? "Start with your business question" : "Start a new project"}
          subtitle="The Research Director agent turns your question into a research design you can review.">
          <NewProject />
        </Card>
        <section className="stack-sm" aria-labelledby="loop-title">
          <div className="section-title" style={{ marginBottom: 0 }}>
            <h2 id="loop-title">How the loop works</h2>
          </div>
          <p className="small secondary measure">Research findings feed strategy, strategy feeds the journey, and experiment results come back as evidence.</p>
          <ClosedLoop />
          {firstRun && (
            <div className="stack-sm" style={{ marginTop: 16 }}>
              <p className="small secondary measure">New to MDOS? The demo builds the whole loop on synthetic Lake Toba tourism data in a few seconds.</p>
              <div>{demoButton}</div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
