import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../../api/client";
import { useApprovals, useDatasets, useEvidence, useInsights, useProject, useProjectMutation, useResearch, useWorkflows } from "../../api/hooks";
import type { Project } from "../../api/types";
import { AgentRunModal, StartWorkflow, WorkflowPanel } from "../../components/domain";
import { Callout, Card, Icon, PageHeader, Stat, Tabs, useToast } from "../../components/ui";
import AnalysisStudio from "./AnalysisStudio";
import DataWorkspace from "./DataWorkspace";
import Insights from "./Insights";
import Plan from "./Plan";
import Questionnaire from "./Questionnaire";
import ReportBuilder from "./ReportBuilder";

const TABS = [
  { key: "dashboard", label: "Dashboard" },
  { key: "brief", label: "Project brief" },
  { key: "plan", label: "Research plan" },
  { key: "questionnaire", label: "Questionnaire" },
  { key: "data", label: "Data workspace" },
  { key: "analysis", label: "Analysis studio" },
  { key: "insights", label: "Insights and evidence" },
  { key: "report", label: "Report builder" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

export default function Research({ pid }: { pid: string }) {
  const { tab = "dashboard" } = useParams();
  const navigate = useNavigate();
  const { data: project } = useProject(pid);
  const current = (TABS.some((t) => t.key === tab) ? tab : "dashboard") as TabKey;
  return (
    <div>
      <PageHeader eyebrow="Research Lab" title={project?.name ?? "Research"} description={project?.business_question} />
      <Tabs tabs={TABS.map((t) => ({ key: t.key, label: t.label }))} value={current} onChange={(k) => navigate(`/p/${pid}/research/${k}`)} />
      {current === "dashboard" && <Dashboard pid={pid} />}
      {current === "brief" && project && <Brief project={project} />}
      {current === "plan" && <Plan pid={pid} />}
      {current === "questionnaire" && <Questionnaire pid={pid} />}
      {current === "data" && <DataWorkspace pid={pid} />}
      {current === "analysis" && <AnalysisStudio pid={pid} />}
      {current === "insights" && <Insights pid={pid} />}
      {current === "report" && <ReportBuilder pid={pid} />}
    </div>
  );
}

function Dashboard({ pid }: { pid: string }) {
  const { data: research } = useResearch(pid);
  const { data: workflows } = useWorkflows(pid);
  const { data: datasets } = useDatasets(pid);
  const { data: evidence } = useEvidence(pid);
  const { data: insights } = useInsights(pid);
  const { data: approvals } = useApprovals(pid);
  const navigate = useNavigate();
  const [runId, setRunId] = useState<string | null>(null);
  const progress = research?.progress ?? [];
  const done = progress.filter((s) => s.status === "done").length;
  const research_runs = (workflows ?? []).filter((w) => w.workflow.startsWith("research_"));
  const surveyDataset = (datasets ?? []).find((d) => d.kind === "survey");
  const hasDesign = (research?.hypotheses.length ?? 0) > 0;
  const nextStep = !hasDesign
    ? { text: "Generate a research design from your business question.", tab: "brief", cta: "Open the project brief" }
    : !surveyDataset
      ? { text: "Export the questionnaire, run fieldwork, then upload the responses.", tab: "questionnaire", cta: "Open the questionnaire" }
      : !(evidence?.length)
        ? { text: "Run the analysis workflow on your survey data.", tab: "data", cta: "Open the data workspace" }
        : (approvals?.length ?? 0) > 0
          ? { text: `Review ${approvals?.length} pending approval${approvals?.length === 1 ? "" : "s"}: insights, verdicts and the report stay drafts until you decide.`, tab: "insights", cta: "Review insights" }
          : { text: "Generate the research report and carry the evidence into the Strategy Simulator.", tab: "report", cta: "Open the report builder" };
  const counted = progress.filter((s) => s.status !== "deferred");
  const nextIndex = progress.findIndex((s) => s.status !== "done" && s.status !== "deferred");
  return (
    <div className="stack" style={{ gap: 24 }}>
      <div className="next-step">
        <Icon name="flag" />
        <div className="next-step-text"><strong>Next step:</strong> {nextStep.text}</div>
        <button className="btn primary" onClick={() => navigate(`/p/${pid}/research/${nextStep.tab}`)}>{nextStep.cta}<Icon name="arrowRight" size={14} /></button>
      </div>
      <div className="stats">
        <Stat label="Workflow steps done" value={`${done} of ${counted.length}`} />
        <Stat label="Hypotheses" value={research?.hypotheses.length ?? 0}
          delta={`${research?.hypotheses.filter((h) => ["supported", "not_supported", "inconclusive"].includes(h.status)).length ?? 0} with approved verdicts`} />
        <Stat label="Evidence records" value={evidence?.length ?? 0} delta={`${insights?.length ?? 0} insights drafted or approved`} />
        <Stat label="Pending approvals" value={approvals?.length ?? 0} delta="Waiting for a person" />
      </div>
      <div className="grid grid-2 align-start">
        <section aria-labelledby="workflow-title">
          <div className="section-title">
            <h2 id="workflow-title">Research workflow</h2>
            <p>{done} of {counted.length} steps</p>
          </div>
          <div className="progress-bar" aria-hidden style={{ marginBottom: 12 }}>
            <span style={{ width: `${counted.length ? (done / counted.length) * 100 : 0}%` }} />
          </div>
          <ol className="progress-steps" aria-label="Research workflow steps">
            {progress.map((s, i) => (
              <li key={s.step} className={`progress-step ${s.status} ${i === nextIndex ? "next" : ""}`}
                title={s.status === "deferred" ? "Planned for a later version" : undefined}>
                {s.status === "done" ? <Icon name="check" size={14} /> : <span className="num muted" style={{ width: 14, textAlign: "right" }}>{s.step}</span>}
                <span>{s.name}{i === nextIndex && <span className="visually-hidden"> (next)</span>}</span>
              </li>
            ))}
          </ol>
        </section>
        <section aria-labelledby="agents-title" className="stack-sm">
          <div className="section-title" style={{ marginBottom: 0 }}>
            <h2 id="agents-title">Agent workflows</h2>
          </div>
          <p className="small secondary measure">Research, questionnaire, sampling, fieldwork, cleaning, statistics, insight and report agents. They draft; you approve.</p>
          <div className="actions" style={{ margin: "4px 0 8px" }}>
            {/* The next-step button above is the page's one primary action. */}
            <StartWorkflow pid={pid} workflow="research_design" label="Run design agents" primary={false} />
            <StartWorkflow pid={pid} workflow="research_analysis" label="Run analysis agents" primary={false}
              disabled={!hasDesign || !surveyDataset} inputs={surveyDataset ? { dataset_id: surveyDataset.id } : {}} />
          </div>
          {research_runs.length ? (
            <div className="stack">
              {research_runs.slice(0, 2).map((w) => <WorkflowPanel key={w.id} pid={pid} runId={w.id} onOpenRun={setRunId} />)}
            </div>
          ) : (
            <p className="small muted">No agent runs yet. {hasDesign ? "Upload survey responses to run the analysis agents." : "Run the design agents to draft hypotheses, a questionnaire and a sampling plan."}</p>
          )}
        </section>
      </div>
      <details className="disclosure">
        <summary><Icon name="chevronDown" size={12} />How MDOS keeps research defensible</summary>
        <ul className="small secondary measure" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
          <li>Every statistic comes from code and reports its assumption checks, sample size and limitations.</li>
          <li>Insights and recommendations must cite evidence; causal wording is blocked unless evidence comes from an experiment.</li>
          <li>Segmentation needs a stated objective and variable rationale.</li>
          <li>Agents propose hypothesis verdicts; only a person can approve them.</li>
          <li>Every cleaning step creates a new dataset version with a checksum and an operations log.</li>
        </ul>
      </details>
      <AgentRunModal pid={pid} runId={runId} onClose={() => setRunId(null)} />
    </div>
  );
}

function Brief({ project }: { project: Project }) {
  const toast = useToast();
  const [form, setForm] = useState({
    name: project.name, business_question: project.business_question, decision_to_inform: project.decision_to_inform,
    context: project.context, industry: project.industry, geography: project.geography, currency: project.currency,
  });
  const save = useProjectMutation(project.id, () => api.patch<Project>(`/projects/${project.id}`, form));
  const [parsed, setParsed] = useState<Record<string, unknown> | null>(null);
  const preview = async () => {
    try {
      setParsed(await api.post<Record<string, unknown>>("/tools/parse-question", { text: form.business_question, currency: form.currency }));
    } catch (err) {
      toast(errorMessage(err), "error");
    }
  };
  return (
    <div className="grid grid-2">
      <Card title="Project brief" subtitle="The Problem Framing agent starts from this brief.">
        <form className="stack-sm" onSubmit={(e) => { e.preventDefault(); save.mutate(undefined, { onSuccess: () => toast("Brief saved."), onError: (er) => toast(errorMessage(er), "error") }); }}>
          <div className="field"><label htmlFor="b-name">Name</label>
            <input id="b-name" className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></div>
          <div className="field"><label htmlFor="b-q">Business question</label>
            <textarea id="b-q" className="textarea" value={form.business_question} onChange={(e) => setForm({ ...form, business_question: e.target.value })} /></div>
          <div className="field"><label htmlFor="b-d">Decision to inform</label>
            <input id="b-d" className="input" value={form.decision_to_inform} onChange={(e) => setForm({ ...form, decision_to_inform: e.target.value })} /></div>
          <div className="field"><label htmlFor="b-c">Context</label>
            <textarea id="b-c" className="textarea" value={form.context} placeholder="What is the offer? Who is it for? Constraints, timeline, budget."
              onChange={(e) => setForm({ ...form, context: e.target.value })} /></div>
          <div className="grid grid-3">
            <div className="field"><label htmlFor="b-i">Industry</label>
              <input id="b-i" className="input" value={form.industry} onChange={(e) => setForm({ ...form, industry: e.target.value })} /></div>
            <div className="field"><label htmlFor="b-g">Geography</label>
              <input id="b-g" className="input" value={form.geography} onChange={(e) => setForm({ ...form, geography: e.target.value })} /></div>
            <div className="field"><label htmlFor="b-cur">Currency</label>
              <input id="b-cur" className="input" maxLength={3} value={form.currency} onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })} /></div>
          </div>
          <div className="actions">
            <button className="btn primary" disabled={save.isPending}>Save brief</button>
            <button type="button" className="btn" onClick={preview}>Preview how agents read the question</button>
          </div>
        </form>
      </Card>
      <div className="stack">
        <Card title="Generate the research design" subtitle="Problem framing, design, questionnaire, sampling, fieldwork and a quality check. Nothing is saved until you approve the package.">
          <StartWorkflow pid={project.id} workflow="research_design" label="Run design agents" />
        </Card>
        {parsed && (
          <Card title="How the question was parsed">
            <dl className="kv">
              <dt>Intents</dt><dd>{(parsed.intents as string[]).join(", ")}</dd>
              <dt>Target price</dt><dd>{parsed.price ? `${String(parsed.currency)} ${Number(parsed.price).toLocaleString("en-US")}` : "none found"}</dd>
              <dt>Population</dt><dd>{String(parsed.population_en)} ({String(parsed.population_id)})</dd>
              <dt>Offering</dt><dd>{String(parsed.offering)}</dd>
              <dt>Tourism context</dt><dd>{parsed.tourism ? "yes" : "no"}</dd>
              <dt>Cultural context</dt><dd>{parsed.cultural ? "yes" : "no"}</dd>
            </dl>
            {(parsed.notes as string[]).length > 0 && <div style={{ marginTop: 8 }}><Callout tone="warning">{(parsed.notes as string[]).join(" ")}</Callout></div>}
          </Card>
        )}
      </div>
    </div>
  );
}
