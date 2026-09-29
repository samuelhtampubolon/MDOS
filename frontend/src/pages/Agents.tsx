import { useState } from "react";
import { useAgents, useApi, useDatasets, useProvider, useWorkflows } from "../api/hooks";
import type { AgentRun } from "../api/types";
import { AGENT_LABELS, AgentRunModal, StartWorkflow, WORKFLOW_LABELS, WorkflowPanel } from "../components/domain";
import { Badge, Callout, Card, Icon, PageHeader, StatusBadge, Tabs } from "../components/ui";
import { dateTime, sentence } from "../lib/format";

type View = "workflows" | "registry" | "coverage" | "runs";

const WORKFLOW_NOTES: Record<string, string> = {
  research_design: "Problem framing, research design, questionnaire, sampling, fieldwork and a quality check. Ends at an approval gate.",
  research_analysis: "Data quality, a cleaning plan (approval gate), statistics, pricing, segments, text, insights and the report.",
  strategy_baseline: "Market model from research evidence, pricing and media scenarios, and a proposed decision.",
  journey_voc: "Voice of customer, journey map, pain points, interventions, simulation and an A/B test design.",
};

export default function Agents({ pid }: { pid: string }) {
  const [view, setView] = useState<View>("workflows");
  const [runId, setRunId] = useState<string | null>(null);
  const { data: provider } = useProvider();
  const { data: registry } = useAgents();
  const { data: datasets } = useDatasets(pid);
  const survey = datasets?.find((d) => d.kind === "survey");
  const reviews = datasets?.find((d) => d.kind === "reviews");
  const inputs: Record<string, Record<string, unknown> | null> = {
    research_design: {}, strategy_baseline: {},
    research_analysis: survey ? { dataset_id: survey.id } : null,
    journey_voc: reviews ? { reviews_dataset_id: reviews.id } : null,
  };
  return (
    <div className="stack">
      <PageHeader eyebrow="Agents" title="The agent team"
        description="Agents orchestrate the work and draft wording. Statistics come from code, every run returns the same output contract, and each agent can only use its allowed tools." />
      {provider && (
        <Callout tone={provider.mode === "claude" ? "good" : "info"} icon={provider.mode === "claude" ? "check" : "info"}>
          <strong>{provider.mode === "claude" ? `Claude is drafting wording (${provider.model}, ${provider.effort} effort).` : "Offline mode."}</strong> {provider.note}
          {provider.mode !== "claude" && <> To enable Claude, set <code>ANTHROPIC_API_KEY</code> in the server environment and restart. Numbers never depend on the model.</>}
        </Callout>
      )}
      <Tabs<View> value={view} onChange={setView} tabs={[
        { key: "workflows", label: "Workflows" }, { key: "registry", label: `Agents (${registry?.counts.executable ?? 0})` },
        { key: "coverage", label: `Specification coverage (${registry?.counts.spec_covered ?? 0} of ${registry?.counts.spec_total ?? 0})` },
        { key: "runs", label: "Run log" },
      ]} />
      {view === "workflows" && (
        <>
          <div className="grid grid-2">
            {Object.keys(WORKFLOW_LABELS).map((w) => (
              <Card key={w} title={WORKFLOW_LABELS[w]} subtitle={WORKFLOW_NOTES[w]}>
                {inputs[w] ? <StartWorkflow pid={pid} workflow={w} inputs={inputs[w] ?? {}} label={`Run ${WORKFLOW_LABELS[w].toLowerCase()}`} primary={false} />
                  : <span className="small muted">Needs a {w === "journey_voc" ? "reviews" : "survey"} dataset. Upload one in the Data workspace.</span>}
              </Card>
            ))}
          </div>
          <WorkflowHistory pid={pid} onOpenRun={setRunId} />
        </>
      )}
      {view === "registry" && registry && (
        <Card title="Executable agents" subtitle="Tools are allowlisted per agent. Agents marked with a gate stop for human approval.">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Agent</th><th>Module</th><th>What it does</th><th>Allowed tools</th><th>Covers from the specification</th></tr></thead>
              <tbody>
                {registry.agents.map((a) => (
                  <tr key={a.key}>
                    <td style={{ fontWeight: 600, whiteSpace: "nowrap" }}>{a.name}{a.requires_approval && <div><Badge tone="warning"><Icon name="approvals" size={12} />Approval gate</Badge></div>}</td>
                    <td>{sentence(a.module)}</td>
                    <td className="small secondary">{a.description}</td>
                    <td><div className="row" style={{ gap: 3 }}>{a.tools.map((t) => <code key={t} className="chip code">{t}</code>)}</div></td>
                    <td className="small">{a.covers.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {view === "coverage" && registry && (
        <Card title="The 50 agents in the specification" subtitle="How each one is covered in this version. Deferred agents are planned for a later phase.">
          <div className="table-wrap">
            <table className="table">
              <thead><tr><th>Specification agent</th><th>Module</th><th>Status</th><th>Implemented by</th><th>Note</th></tr></thead>
              <tbody>
                {registry.spec_agents.map((s) => (
                  <tr key={s.spec_agent}>
                    <td>{s.spec_agent}</td>
                    <td>{sentence(s.module)}</td>
                    <td>{s.status === "deferred" ? <StatusBadge status="skipped" label="Deferred" /> : <StatusBadge status="done" label="In this version" />}</td>
                    <td>{s.implemented_by ? AGENT_LABELS[s.implemented_by] ?? s.implemented_by : ""}</td>
                    <td className="small secondary">{s.reason ?? ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
      {view === "runs" && <RunLog pid={pid} onOpen={setRunId} />}
      <AgentRunModal pid={pid} runId={runId} onClose={() => setRunId(null)} />
    </div>
  );
}

function WorkflowHistory({ pid, onOpenRun }: { pid: string; onOpenRun: (id: string) => void }) {
  const { data: workflows } = useWorkflows(pid);
  const [open, setOpen] = useState<string | null>(null);
  if (!workflows?.length) return <Card title="History"><span className="muted small">No workflows have run yet.</span></Card>;
  const shown = open ?? workflows[0].id;
  return (
    <div className="grid grid-sidebar">
      <Card title="History">
        <div className="stack-sm">
          {workflows.map((w) => (
            <button key={w.id} className="list-item" onClick={() => setOpen(w.id)}
              style={{ textAlign: "left", width: "100%", border: 0, borderRadius: 8, padding: "8px 10px", cursor: "pointer", color: "inherit", background: shown === w.id ? "var(--accent-soft)" : "transparent" }}>
              <div className="grow">
                <div style={{ fontWeight: 600, fontSize: 13 }}>{WORKFLOW_LABELS[w.workflow] ?? w.workflow}</div>
                <div className="small muted">{dateTime(w.created_at)}</div>
              </div>
              <StatusBadge status={w.status} />
            </button>
          ))}
        </div>
      </Card>
      <Card><WorkflowPanel pid={pid} runId={shown} onOpenRun={onOpenRun} /></Card>
    </div>
  );
}

function RunLog({ pid, onOpen }: { pid: string; onOpen: (id: string) => void }) {
  const { data: runs } = useApi<AgentRun[]>([pid, "agent-runs"], `/projects/${pid}/agent-runs`);
  return (
    <Card title="Agent run log" subtitle="The latest 200 runs. Open a run to see its full output contract.">
      <div className="table-wrap" style={{ maxHeight: 620 }}>
        <table className="table">
          <thead><tr><th>Agent</th><th>Status</th><th>Provider</th><th className="num">Attempt</th><th>Started</th><th /></tr></thead>
          <tbody>
            {(runs ?? []).map((r) => (
              <tr key={r.id}>
                <td style={{ fontWeight: 600 }}>{AGENT_LABELS[r.agent] ?? r.agent}</td>
                <td><StatusBadge status={r.status} /></td>
                <td className="small">{r.provider === "offline" ? "Offline (deterministic)" : `${r.provider} ${r.model}`}</td>
                <td className="num">{r.attempt}</td>
                <td className="small">{dateTime(r.created_at)}</td>
                <td><button className="btn ghost sm" onClick={() => onOpen(r.id)}>Open</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}
