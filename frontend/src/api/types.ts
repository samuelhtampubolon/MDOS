/* API shapes returned by the backend (subset of fields the UI uses). */

export type Json = Record<string, unknown>;

export interface User {
  id: string;
  email: string;
  name: string;
  role: string;
  org_id: string;
  organization: string;
}

export interface Project {
  id: string;
  name: string;
  business_question: string;
  decision_to_inform: string;
  context: string;
  industry: string;
  geography: string;
  currency: string;
  status: string;
  is_demo: boolean;
  brief: { demo_status?: string; demo_error?: string } & Json;
  created_at: string;
  updated_at: string;
  my_role?: string;
}

export interface ProgressStep {
  step: number;
  name: string;
  status: "done" | "todo" | "deferred";
}

export interface Hypothesis {
  id: string;
  code: string;
  statement: string;
  iv: string;
  dv: string;
  mediator: string;
  moderator: string;
  expected_direction: string;
  rationale: string;
  status: string;
  verdict_rationale: string;
  verdict_evidence: string[];
}

export interface ResearchQuestion {
  id: string;
  code: string;
  text: string;
}

export interface Construct {
  id: string;
  code: string;
  name: string;
  definition: string;
  source_reference: string;
}

export interface Variable {
  id: string;
  name: string;
  label: string;
  var_type: string;
  role: string;
  construct_id: string | null;
  scale_min: number | null;
  scale_max: number | null;
}

export interface Plan {
  id: string;
  kind: string;
  content: Json;
}

export interface SurveySummary {
  id: string;
  title: string;
  status: string;
  version: number;
  question_count: number;
  languages: string[];
}

export interface Question {
  id: string;
  code: string;
  section: string;
  position: number;
  qtype: string;
  text: string;
  text_id: string;
  options: { value: string; label: string; label_id?: string }[];
  scale: Json;
  logic: Json;
  required: boolean;
  construct_code: string;
}

export interface Survey extends Omit<SurveySummary, "question_count"> {
  introduction: string;
  consent_text: string;
  questions: Question[];
}

export interface ResearchOverview {
  research_questions: ResearchQuestion[];
  hypotheses: Hypothesis[];
  constructs: Construct[];
  variables: Variable[];
  plans: Record<string, Plan>;
  surveys: SurveySummary[];
  progress: ProgressStep[];
}

export interface ColumnProfile {
  name: string;
  inferred_type: string;
  type?: string;
  role?: string;
  n: number;
  missing: number;
  missing_share: number;
  unique: number;
  mean?: number;
  sd?: number;
  min?: number;
  max?: number;
  top_values?: { value: string; count: number }[];
  examples?: string[];
}

export interface QualityIssue {
  id: string;
  check: string;
  severity: "high" | "medium" | "low";
  column: string | null;
  count: number;
  message: string;
  suggestion: string;
  operation: Json | null;
}

export interface DatasetVersion {
  id: string;
  dataset_id: string;
  version: number;
  parent_id: string | null;
  status: string;
  original_filename: string;
  n_rows: number;
  n_cols: number;
  columns: ColumnProfile[];
  operations: Json[];
  quality: { issues?: QualityIssue[]; quality_score?: number; flagged_respondents?: number; flagged_share?: number } & Json;
  checksum: string;
  created_by: string;
  approved_by: string | null;
  source_run_id: string | null;
  created_at: string;
}

export interface Dataset {
  id: string;
  name: string;
  kind: string;
  origin: string;
  description: string;
  current_version_id: string | null;
  created_at: string;
  versions?: DatasetVersion[];
  current_version?: Omit<DatasetVersion, "columns" | "quality"> | null;
  version_count?: number;
}

export interface Check {
  name: string;
  status: "ok" | "warning" | "violated" | "not_applicable";
  detail: string;
  value?: number | null;
}

export interface EvidenceCandidate {
  key: string;
  title: string;
  statement: string;
  n?: number;
  p_value?: number | null;
  strength: string;
}

export interface ChartSpec {
  type: string;
  title: string;
  [k: string]: unknown;
}

export interface Analysis {
  id: string;
  method: string;
  title: string;
  params: Json;
  status: string;
  result: { summary: string; data: Json; evidence_candidates: EvidenceCandidate[]; charts: ChartSpec[] };
  assumptions: Check[];
  warnings: string[];
  limitations: string[];
  n: number | null;
  dataset_version_id: string | null;
  error: string;
  created_by: string;
  created_at: string;
  summary?: string;
}

export interface MethodSpec {
  key: string;
  label: string;
  category: string;
  description: string;
  params_schema: Json;
}

export interface Evidence {
  id: string;
  code: string;
  seq: number;
  kind: string;
  title: string;
  statement: string;
  analysis_id: string | null;
  origin: string;
  design: string;
  strength: string;
  n: number | null;
  p_value: number | null;
  effect_size: number | null;
  effect_label: string;
  ci_low: number | null;
  ci_high: number | null;
  source_ref: Json;
  created_at: string;
}

export interface EvidenceRef {
  id: string;
  code: string;
  title: string;
  strength: string;
}

export interface Insight {
  id: string;
  code: string;
  title: string;
  statement: string;
  implication: string;
  confidence: string;
  uncertainty: string;
  status: string;
  is_model_generated: boolean;
  evidence: EvidenceRef[];
  created_at: string;
}

export interface Recommendation {
  id: string;
  code: string;
  statement: string;
  rationale: string;
  module: string;
  priority: string;
  status: string;
  is_model_generated: boolean;
  evidence: EvidenceRef[];
}

export interface Approval {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  status: string;
  summary: string;
  payload: Json;
  requested_by: string;
  requested_at: string;
  decided_at: string | null;
  rationale: string;
}

export interface ReportBlock {
  type: "heading" | "paragraph" | "list" | "table" | "callout" | "evidence_register";
  level?: number;
  text?: string;
  citations?: string[];
  model_generated?: boolean;
  items?: { text?: string; citations?: string[]; code?: string; title?: string; statement?: string; origin?: string;
    design?: string; strength?: string; source?: string }[];
  columns?: string[];
  rows?: (string | number)[][];
  tone?: string;
}

export interface Report {
  id: string;
  kind: string;
  title: string;
  status: string;
  version: number;
  created_at: string;
  document?: { title: string; subtitle: string; generated_at: string; synthetic: boolean; blocks: ReportBlock[] };
}

export interface KPIs {
  price: number;
  spend: number;
  impressions: number;
  reach: number;
  engaged: number;
  leads: number;
  paid_customers: number;
  referrals: number;
  customers: number;
  revenue: number;
  gross_margin: number;
  commission: number;
  fixed_costs: number;
  profit: number;
  romi: number | null;
  cac: number | null;
  clv: number | null;
  clv_to_cac: number | null;
  break_even_customers: number | null;
  market_penetration: number;
}

export interface Assumption {
  key: string;
  label: string;
  value: number | string | null;
  unit: string;
  source: string;
  evidence_id: string | null;
  confidence: string;
  note: string;
}

export interface MarketModel {
  currency: string;
  period: string;
  market_name: string;
  market_size: number;
  segments: { key: string; name: string; share: number; wtp_multiplier: number; cross_price_elasticity: number;
    conversion_multiplier: number; repeat_rate: number; price_elasticity: number; needs: string[] }[];
  channels: { key: string; name: string; budget: number; cpm: number; audience_size: number; engagement_rate: number;
    lead_rate: number; conversion_rate: number; commission_rate: number; organic_impressions: number; affinity: Record<string, number> }[];
  competitors: { key: string; name: string; price: number; base_price: number | null; attributes: Record<string, number> }[];
  offer: { name: string; price: number; reference_price: number; unit_cost: number; fixed_costs: number; attributes: Record<string, number> };
  price_response: { mode: string; points: { price: number; share: number }[]; evidence_id: string | null };
  word_of_mouth_rate: number;
  positioning_axes: string[];
  assumptions: Assumption[];
}

export interface ScenarioResults {
  kpis: KPIs;
  funnel: { stage: string; value: number; unit: string }[];
  channels: { key: string; name: string; spend: number; reach: number; engaged: number; leads: number; customers: number;
    revenue: number; cac: number | null; romi: number | null; commission: number }[];
  segments: { key: string; name: string; customers: number; share_of_customers: number; revenue: number; clv: number;
    reach_to_customer: number }[];
  comparison?: Record<string, { baseline: number; scenario: number; delta: number; pct: number | null }>;
  waterfall?: { label: string; value?: number; delta?: number; type: string }[];
  lever_descriptions?: string[];
  break_even_price?: number | null;
  positioning?: { axes: string[]; points: { name: string; self: boolean; x: number | null; y: number | null }[] };
}

export interface Scenario {
  id: string;
  name: string;
  kind: "baseline" | "scenario";
  baseline_id: string | null;
  description: string;
  model: MarketModel;
  levers: Json[];
  results: ScenarioResults;
  status: string;
  created_at: string;
}

export interface Decision {
  id: string;
  title: string;
  decision: string;
  rationale: string;
  scenario_id: string | null;
  evidence_ids: string[];
  status: string;
  created_by: string;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
}

export interface JourneyStage {
  key: string;
  name: string;
  kind: "funnel" | "outcome";
  conversion?: number;
  rate?: number;
  steps?: number;
  description?: string;
  emotion: number | null;
  mentions: number;
  negative_share: number | null;
  top_positive?: string[];
  top_negative?: string[];
  assumption_source?: string;
  notes?: string;
}

export interface PainPoint {
  id: string;
  stage_key: string;
  title: string;
  theme: string;
  description: string;
  mentions: number;
  frequency: number;
  severity: number;
  reach: number;
  score: number;
  evidence_ids: string[];
  quotes: string[];
  status: string;
}

export interface JourneySim {
  entrants: number;
  funnel: { key: string; name: string; entering: number; conversion: number; continuing: number }[];
  customers: number;
  wom_customers: number;
  total_customers: number;
  revenue: number;
  sharers: number;
  recommenders: number;
  returners: number;
  wom_entrants?: number;
  future_repeat_revenue?: number;
  journey_conversion?: number;
}

export interface Intervention {
  id: string;
  pain_point_id: string | null;
  stage_key: string;
  title: string;
  description: string;
  kind: string;
  params: Json;
  uplift_low: number;
  uplift_mid: number;
  uplift_high: number;
  effort: string;
  confidence: string;
  status: string;
  simulation: { before?: JourneySim; levels?: Record<"low" | "mid" | "high", { after: JourneySim; delta_customers: number;
    delta_revenue: number; pct_customers: number | null }>; assumptions?: string[] };
}

export interface Journey {
  id: string;
  name: string;
  template: string;
  stages: JourneyStage[];
  settings: { entrants?: number; price?: number; entrants_source?: string } & Json;
  voc: { summary?: string; heatmap?: { stages: string[]; themes: string[]; counts: number[][] }; coverage?: number;
    rating_correlation?: number | null } & Json;
  status: string;
  touchpoints: { id: string; stage_key: string; name: string; channel: string }[];
  pain_points: PainPoint[];
  interventions: Intervention[];
  simulation: JourneySim;
}

export interface Experiment {
  id: string;
  name: string;
  source_type: string;
  source_id: string | null;
  hypothesis: string;
  primary_metric: string;
  baseline_rate: number;
  mde: number;
  alpha: number;
  power: number;
  sample_size_per_arm: number;
  expected_daily_traffic: number;
  duration_days: number | null;
  variants: { name: string; description?: string }[];
  status: string;
  results: Json & { summary?: string; notes?: string[] };
  evidence_id: string | null;
  created_by: string;
  created_at: string;
}

export interface StepRun {
  index: number;
  agent: string;
  status: string;
  agent_run_id: string | null;
  summary: string[];
  error: string;
}

export interface WorkflowRun {
  id: string;
  workflow: string;
  status: string;
  steps: string[];
  current_step: number;
  error: string;
  created_at: string;
  finished_at: string | null;
  has_package: boolean;
  step_runs?: StepRun[];
  package_preview?: { objectives: string[]; hypotheses: string[]; constructs: string[]; question_count: number;
    sample_size: number; qa: Check[] };
}

export interface AgentResult {
  task_id: string;
  status: string;
  inputs_used: string[];
  actions_taken: string[];
  tools_used: string[];
  evidence: string[];
  assumptions: string[];
  uncertainties: string[];
  outputs: Json;
  recommended_next_step: string;
  llm_calls?: Json[];
}

export interface AgentRun {
  id: string;
  agent: string;
  status: string;
  provider: string;
  model: string;
  attempt: number;
  error: string;
  result: AgentResult;
  workflow_run_id: string | null;
  created_at: string;
  finished_at: string | null;
}

export interface AgentRegistry {
  agents: { key: string; name: string; module: string; description: string; tools: string[]; requires_approval: boolean;
    covers: string[] }[];
  spec_agents: { spec_agent: string; module: string; status: string; implemented_by: string | null; reason?: string }[];
  counts: { executable: number; spec_total: number; spec_covered: number; deferred: number };
}

export interface ProviderStatus {
  mode: "claude" | "offline";
  model: string | null;
  effort: string | null;
  note: string;
}

export interface AuditEntry {
  id: string;
  actor_type: string;
  actor_id: string;
  action: string;
  entity_type: string;
  entity_id: string;
  details: Json;
  created_at: string;
}

export interface GraphData {
  nodes: { id: string; kind: string; label: string; status?: string; strength?: string; origin?: string }[];
  edges: { from: string; to: string }[];
}
