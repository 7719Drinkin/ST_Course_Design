/**
 * Shared frontend types aligned with docs/前端展示对接文档.md.
 */

export type RiskLevel = 'High' | 'Medium' | 'Low'
export type TestPriority = 'P1' | 'P2' | 'P3'
export type Technique = 'EP' | 'BVA' | 'DT' | 'FSM'
export type CoverageStatus = 'ai_generated' | 'human_revised' | 'human_added' | 'rejected'
export type TestCaseStatus = 'Draft' | 'Approved' | 'Rejected'
export type OptimizeMode = 'set_cover' | 'risk_priority'
export type FsmPathCoverage = 'covered' | 'uncovered' | 'pending'
export type AnalysisStatus = 'covered' | 'missing' | 'improved' | 'needs_review'
type Verdict = 'Pass' | 'Fail'

export interface PromptRecord {
  prompt_name: string
  target_id?: string | null
  input: Record<string, unknown>
  output: Record<string, unknown>
  note?: string
  created_at?: string
}

export interface PromptEvidence {
  evidence_id?: string
  session_id?: string
  prompt_template_id?: string
  prompt_name?: string
  target_id?: string | null
  prompt_inputs?: Record<string, unknown>
  input?: Record<string, unknown>
  output?: Record<string, unknown>
  source_context_ids?: string[]
  retrieved_context_ids?: string[]
  model_name?: string
  output_schema_version?: string
  output_summary?: string
  note?: string
  created_at?: string
}

export interface ParsedRequirement {
  requirement_id: string
  module: string
  raw_text: string
  description: string
}

export interface AnalyzedRequirement {
  requirement_id: string
  module: string
  description: string
  input_fields: string[]
  data_ranges: string[]
  conditions: string[]
  business_rules: string[]
  expected_action: string
}

export interface ParseResponse {
  requirements: ParsedRequirement[]
  analyzed_requirements: AnalyzedRequirement[]
  prompts_used: PromptRecord[]
}

export interface DisplayRequirement extends Partial<PromptEvidence> {
  requirement_id: string
  module: string
  raw_requirement: string
  description: string
  source: string
  input_fields: string[]
  data_ranges: string[]
  conditions: string[]
  business_rules: string[]
  expected_action: string
  confidence: number
  missing_fields: string[]
  designer_confirmed?: boolean
}

export interface RiskEntry {
  requirement_id: string
  target_id?: string
  target_type?: 'requirement' | 'coverage_item'
  impact: number
  likelihood: number
  score: number
  risk_score?: number
  level: RiskLevel
  risk_level?: RiskLevel
  test_priority?: TestPriority
  reason?: string
  risk_reason?: string
  evidence?: string[]
}

export interface RiskResponse {
  risk_analysis: RiskEntry[]
  prompts_used: PromptRecord[]
}

export interface CoverageGoal {
  coverage_goal_id: string
  requirement_id: string
  goal: string
  related_inputs: string[]
  related_conditions: string[]
  expected_action: string
}

export interface CoverageItem {
  coverage_item_id: string
  coverage_goal_id?: string
  requirement_id: string
  description: string
  technique?: Technique
  techniques: Technique[]
  conditions?: string[]
  data_ranges?: string[]
  input_fields?: string[]
  expected_action?: string
  strategy?: string
  strategy_rationale?: string
  technique_reason?: string
  status: CoverageStatus
  source?: 'llm' | 'algorithm' | 'designer'
  designer_added?: boolean
}

export interface CoverageResponse {
  coverage_goals: CoverageGoal[]
  prompts_used: PromptRecord[]
}

export interface StrategyResponse {
  coverage_items: CoverageItem[]
  prompts_used: PromptRecord[]
}

export interface StrategyItem {
  strategy_id: string
  coverage_item_id: string
  technique: Technique
  standard_ref: string
  reason: string
  algorithm_params: Record<string, unknown>
  designer_confirmed?: boolean
}

export interface TestCase {
  test_id: string
  requirement_id: string
  coverage_item_id?: string
  strategy_id?: string
  spec_id?: string
  technique: Technique
  title: string
  preconditions: string[]
  input_data: Record<string, unknown>
  test_steps: string[]
  expected_result: string
  risk_level?: RiskLevel
  standard_ref: string
  priority?: TestPriority
  status: TestCaseStatus
}

export interface TestDesignSpec {
  spec_id: string
  coverage_item_id: string
  requirement_id: string
  technique: Exclude<Technique, 'FSM'>
  design_points: object[]
  standard_ref: string
}

export interface GenerateResponse {
  test_design_specs: TestDesignSpec[]
  test_cases: TestCase[]
  prompts_used: PromptRecord[]
}

interface FSMTransition {
  from: string
  to: string
  event: string
  condition: string
  action?: string
}

export interface FSMResult {
  states: string[]
  transitions: FSMTransition[]
  coverage_paths: string[]
  coverage?: {
    all_states: string[]
    all_transitions: string[]
  }
  mermaid: string
}

export interface OracleResult {
  test_id: string
  expected_result_suggestion?: string
  explanation?: string
  llm_verdict?: Verdict
  rule_verdict?: Verdict
  confidence: number
  needs_review: boolean
}

export interface RegenerateResult {
  session_id?: string
  created: Record<string, unknown>
  updated: Record<string, unknown>
  unchanged: Record<string, unknown>
  deprecated: Record<string, unknown>
  prompt_evidence?: PromptEvidence[]
}

export interface AnalysisResult {
  requirement_id: string
  coverage_item_id: string
  test_id: string
  status: AnalysisStatus
  gap: string
  improvement: string
}

export interface OptimizeResult {
  before_count: number
  after_count: number
  mode?: OptimizeMode
  objective: OptimizeMode
  reduction_rate?: number
  kept_test_ids?: string[]
  removed_test_ids?: string[]
  coverage_preservation?: string[]
  warnings?: string[]
}

export interface RevisionLog {
  id: string
  step: number
  entity_type:
    | 'requirement'
    | 'parsed_requirement'
    | 'risk_result'
    | 'risk'
    | 'coverage'
    | 'coverage_item'
    | 'strategy'
    | 'test_case'
    | 'fsm'
    | 'analysis'
  entity_id: string
  field: string
  old_value: string
  new_value: string
  reason?: string
  timestamp: string
}

export interface ExportRevisionRecord {
  revision_id: string
  session_id: string
  target_type: string
  target_id: string
  before: Record<string, string>
  after: Record<string, string>
  reason: string
  created_by: string
  created_at: string
  timestamp: string
}

export interface DashboardSummary {
  total_requirements: number
  generated_tests: number
  high_risk_count: number
  revision_count: number
  approved_count: number
  ci_status: string
}

export interface ApiResult<T> {
  data: T
  isLive: boolean
  pendingFrom?: string
}
