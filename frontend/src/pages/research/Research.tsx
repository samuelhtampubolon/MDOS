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
    ? { text: "Generate a research design from your business question.", tab: "brief" }
    : !surveyDataset
      ? { text: "Export the questionnaire, run fieldwork, then upload the responses.", tab: "questionnaire" }
      : !(evidence?.length)
        ? { text: "Run the analysis workflow on your survey data.", tab: "data" }
        : (approvals?.length ?? 0) > 0
          ? { text: `Review ${approvals?.length} pending approval(s): insights, verdicts and the report stay drafts until you decide.`, tab: "insights" }
          : { text: "Generate the research report and carry the evidence into the Strategy Simulator.", tab: "report" };
  return (
    <div className="stack">
      <Callout icon="flag"><strong>Next step:</strong> {nextStep.text}{" "}
        <button className="btn sm" style={{ marginLeft: 8 }} onClick={() => navigate(`/p/${pid}/research/${nextStep.tab}`)}>Go<Icon name="arrowRight" size={12} /></button>
      </Callout>
      <div className="card">
        <div className="grid grid-4" style={{ gap: 0 }}>
          <Stat label="Workflow steps done" value={`${done} of ${progress.filter((s) => s.status !== "deferred").length}`} />
          <Stat label="Hypotheses" value={research?.hypotheses.length ?? 0}
            delta={`${research?.hypotheses.filter((h) => ["supported", "not_supported", "inconclusive"].includes(h.status)).length ?? 0} with approved verdicts`} />
          <Stat label="Evidence records" value={evidence?.length ?? 0} delta={`${insights?.length ?? 0} insights drafted or approved`} />
          <Stat label="Pending approvals" value={approvals?.length ?? 0} delta="Human gates" />
        </div>
      </div>
      <Card title="Research workflow" subtitle="The 23 steps from the specification. Presentation export is deferred to Phase 2.">
        <div className="progress-steps">
          {progress.map((s) => (
            <div key={s.step} className={`progress-step ${s.status}`} title={s.status}>
              {s.status === "done" ? <Icon name="check" size={14} /> : <span className="num muted" style={{ width: 14 }}>{s.step}</span>}
              {s.name}
            </div>
          ))}
        </div>
      </Card>
      <div className="grid grid-2">
        <Card title="Agent workflows" subtitle="Graph1 pipeline: Research, Questionnaire, Sampling, Fieldwork, Cleaning, Statistics, Insight, Report."
          actions={<>
            <StartWorkflow pid={pid} workflow="research_design" label="Run design agents" primary={!hasDesign} />
            <StartWorkflow pid={pid} workflow="research_analysis" label="Run analysis agents" primary={hasDesign && Boolean(surveyDataset)}
              disabled={!hasDesign || !surveyDataset} inputs={surveyDataset ? { dataset_id: surveyDataset.id } : {}} />
          </>}>
          {research_runs.length ? (
            <div className="stack">
              {research_runs.slice(0, 2).map((w) => <WorkflowPanel key={w.id} pid={pid} runId={w.id} onOpenRun={setRunId} />)}
            </div>
          ) : <span className="muted">No agent runs yet.</span>}
        </Card>
        <Card title="How the lab keeps research defensible">
          <ul className="small secondary" style={{ margin: 0, paddingLeft: 18, lineHeight: 1.7 }}>
            <li>Every statistic comes from code and reports its assumption checks, sample size and limitations.</li>
            <li>Insights and recommendations must cite evidence; causal wording is blocked unless evidence comes from an experiment.</li>
            <li>Segmentation needs a stated objective and variable rationale.</li>
            <li>Agents propose hypothesis verdicts; only a person can approve them.</li>
            <li>Every cleaning step creates a new dataset version with a checksum and an operations log.</li>
          </ul>
        </Card>
      </div>
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
