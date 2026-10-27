/* React Query hooks. Keys are scoped by project so every view of a project stays consistent. */

import { useMutation, useQuery, useQueryClient, type UseQueryOptions } from "@tanstack/react-query";
import { api } from "./client";
import type {
  AgentRegistry, Analysis, Approval, AuditEntry, Dataset, Decision, Evidence, Experiment, GraphData, Insight, Journey,
  MethodSpec, Project, ProviderStatus, Recommendation, Report, ResearchOverview, Scenario, Survey, WorkflowRun,
} from "./types";

export function useApi<T>(key: unknown[], path: string | null, options: Partial<UseQueryOptions<T>> = {}) {
  return useQuery<T>({ queryKey: key, queryFn: () => api.get<T>(path as string), enabled: path !== null, ...options });
}

export const useProjects = () => useApi<Project[]>(["projects"], "/projects");
export const useProject = (pid?: string) =>
  useApi<Project>(["project", pid], pid ? `/projects/${pid}` : null, {
    refetchInterval: (q) => ((q.state.data as Project | undefined)?.brief?.demo_status === "building" ? 1500 : false),
  });
export const useResearch = (pid: string) => useApi<ResearchOverview>([pid, "research"], `/projects/${pid}/research`);
export const useSurvey = (pid: string, sid?: string) => useApi<Survey>([pid, "survey", sid], sid ? `/projects/${pid}/surveys/${sid}` : null);
export const useDatasets = (pid: string) => useApi<Dataset[]>([pid, "datasets"], `/projects/${pid}/datasets`);
export const useDataset = (pid: string, did?: string) => useApi<Dataset>([pid, "dataset", did], did ? `/projects/${pid}/datasets/${did}` : null);
export const useAnalyses = (pid: string) => useApi<Analysis[]>([pid, "analyses"], `/projects/${pid}/analyses`);
export const useAnalysis = (pid: string, aid?: string) => useApi<Analysis>([pid, "analysis", aid], aid ? `/projects/${pid}/analyses/${aid}` : null);
export const useMethods = () => useApi<MethodSpec[]>(["methods"], "/tools/analysis-methods", { staleTime: Infinity });
export const useEvidence = (pid: string) => useApi<Evidence[]>([pid, "evidence"], `/projects/${pid}/evidence`);
export const useInsights = (pid: string) => useApi<Insight[]>([pid, "insights"], `/projects/${pid}/insights`);
export const useRecommendations = (pid: string) => useApi<Recommendation[]>([pid, "recommendations"], `/projects/${pid}/recommendations`);
export const useGraph = (pid: string) => useApi<GraphData>([pid, "graph"], `/projects/${pid}/evidence-graph`);
export const useApprovals = (pid?: string) =>
  useApi<Approval[]>([pid, "approvals"], pid ? `/projects/${pid}/approvals` : null, { refetchInterval: 8000 });
export const useReports = (pid: string) => useApi<Report[]>([pid, "reports"], `/projects/${pid}/reports`);
export const useReport = (pid: string, rid?: string) => useApi<Report>([pid, "report", rid], rid ? `/projects/${pid}/reports/${rid}` : null);
export const useScenarios = (pid: string) => useApi<Scenario[]>([pid, "scenarios"], `/projects/${pid}/scenarios`);
export const useDecisions = (pid: string) => useApi<Decision[]>([pid, "decisions"], `/projects/${pid}/decisions`);
export const useJourneys = (pid: string) => useApi<Journey[]>([pid, "journeys"], `/projects/${pid}/journeys`);
export const useJourney = (pid: string, jid?: string) => useApi<Journey>([pid, "journey", jid], jid ? `/projects/${pid}/journeys/${jid}` : null);
export const useExperiments = (pid: string) => useApi<Experiment[]>([pid, "experiments"], `/projects/${pid}/experiments`);
export const useAgents = () => useApi<AgentRegistry>(["agents"], "/agents", { staleTime: Infinity });
export const useProvider = () => useApi<ProviderStatus>(["provider"], "/agents/provider", { staleTime: 60_000 });
export const useAudit = (pid: string) => useApi<AuditEntry[]>([pid, "audit"], `/projects/${pid}/audit?limit=300`);
export const useWorkflows = (pid: string) =>
  useApi<WorkflowRun[]>([pid, "workflows"], `/projects/${pid}/workflows`, {
    refetchInterval: (q) => ((q.state.data as WorkflowRun[] | undefined)?.some((w) => ["queued", "running"].includes(w.status)) ? 1500 : false),
  });
export const useWorkflow = (pid: string, wid?: string) =>
  useApi<WorkflowRun>([pid, "workflow", wid], wid ? `/projects/${pid}/workflows/${wid}` : null, {
    refetchInterval: (q) => (["queued", "running"].includes((q.state.data as WorkflowRun | undefined)?.status ?? "") ? 1200 : false),
  });

/** Mutation that invalidates the whole project scope on success (simple and always consistent). */
export function useProjectMutation<TVars, TResult = unknown>(pid: string, fn: (vars: TVars) => Promise<TResult>) {
  const qc = useQueryClient();
  return useMutation<TResult, Error, TVars>({
    mutationFn: fn,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [pid] });
      void qc.invalidateQueries({ queryKey: ["project", pid] });
    },
  });
}
