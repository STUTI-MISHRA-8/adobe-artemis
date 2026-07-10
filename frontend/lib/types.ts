export type AEPLayer =
  | "schema"
  | "dataset"
  | "ingestion"
  | "modeling"
  | "activation"
  | "governance"
  | "reporting"
  | "general";

export type Priority = "high" | "medium" | "low";

export type FlagType =
  | "clear"
  | "implicit"
  | "ambiguous"
  | "contradiction"
  | "assumption"
  | "unclassified";

export interface Observation {
  obs_id: string;
  text: string;
  verbatim_quote: string;
  type: string;
  section_title: string;
  sec_id: string;
  aep_relevance: AEPLayer;
  business_value: string;
  risk_if_missed: string;
}

export interface Requirement {
  req_id: string;
  aep_layer: AEPLayer;
  priority: Priority;
  description: string;
  source_obs: string[];
  source_section: string;
  sec_id: string;
  flags: FlagType[];
  dependencies: string[];
}

export interface Task {
  task_id: string;
  req_id: string;
  title: string;
  description: string;
  aep_layer: AEPLayer;
  priority: Priority;
  phase: 1 | 2 | 3 | 4;
  dependencies: string[];
  source_section: string;
  acceptance_criteria: string;
}

export interface CoverageAudit {
  total_observations: number;
  mapped_observations: number;
  orphaned_observations: string[];
  coverage_percent: number;
}

export interface TraceNode {
  req_id: string;
  description: string;
  aep_layer: AEPLayer;
  source_section: string;
  observations: Observation[];
  tasks: Task[];
}

export interface DocSection {
  sec_id: string;
  title: string;
  content: string;
}

export interface AnalysisResult {
  job_id: string;
  filename: string;
  section_count: number;
  observation_count: number;
  requirement_count: number;
  task_count: number;
  coverage: CoverageAudit;
  requirements: Requirement[];
  tasks: Task[];
  trace: TraceNode[];
  sections: DocSection[];
}

export interface ProgressEvent {
  stage: "parsing" | "extracting" | "structuring" | "planning" | "done" | "error";
  message: string;
  percent: number;
}

export interface JobSummary {
  id: string;
  filename: string;
  status: string;
  created_at: string;
}

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  citations?: string[];
  followups?: string[];
  created_at?: string;
}

export interface WizardStep extends Task {
  status: "pending" | "done";
  is_ready: boolean;
  is_current: boolean;
  assigned_to: string | null;
}

export interface WizardState {
  steps: WizardStep[];
  total: number;
  done: number;
  percent_complete: number;
}

export interface TaskExecution {
  ok: boolean;
  status_code: number | null;
  response: unknown;
  endpoint: string | null;
  error: string | null;
  executed_at: string;
  simulated?: boolean;
}

export interface TaskPayload {
  api_name: string;
  method: string;
  endpoint: string;
  headers: Record<string, string>;
  body: unknown;
  notes: string;
  cached: boolean;
  last_execution?: TaskExecution | null;
}

export interface AepStatus {
  configured: boolean;
  sandbox: string | null;
}

export type TeamRole = "schema" | "dataset" | "ingestion" | "activation" | "pm" | "reviewer";

export interface TeamMember {
  id: string;
  job_id: string;
  name: string;
  role: TeamRole;
  color: string;
  created_at: string;
  assigned: number;
  done: number;
}
