/**
 * Shared types aligned with docs/integration_interfaces.md (Day3–Day7)
 */

export type RiskLevel = 'High' | 'Medium' | 'Low'
export type Technique = 'EP' | 'BVA' | 'DT' | 'FSM'
export type Verdict = 'Pass' | 'Fail'
export type OptimizeMode = 'risk_priority' | 'normal'
export type TestCaseStatus = 'Draft' | 'Approved' | 'Rejected'

export interface ParseTransparency {
  source_context_ids: string[]
  prompt_template_id: string
  retrieved_context_ids: string[]
  model_name: string
  output_schema_version: string
}

export interface DisplayRequirement extends Partial<ParseTransparency> {
  requirement_id: string
  raw_requirement: string
  source: string
  input_fields: string[]
  data_ranges: string[]
  conditions: string[]
  expected_action: string
  confidence: number
  missing_fields: string[]
  designer_confirmed?: boolean
}

export interface CoverageItem {
  coverage_item_id: string
  requirement_id: string
  description: string
  techniques: Technique[]
  strategy_rationale?: string
  designer_added?: boolean
}

export type FsmPathCoverage = 'covered' | 'uncovered' | 'pending'

export interface TestCase {
  test_id: string
  requirement_id: string
  technique: Technique
  title: string
  preconditions: string[]
  input_data: Record<string, unknown>
  test_steps: string[]
  expected_result: string
  risk_level: RiskLevel
  standard_ref: string
  status?: TestCaseStatus
  coverage_item_id?: string
}

export interface FSMTransition {
  from: string
  to: string
  event: string
  condition: string
}

export interface FSMResult {
  states: string[]
  transitions: FSMTransition[]
  coverage: {
    all_states: string[]
    all_transitions: string[]
  }
  mermaid: string
}

export interface OracleResult {
  test_id: string
  llm_verdict: Verdict
  rule_verdict: Verdict
  confidence: number
  needs_review: boolean
}

export interface RiskEntry {
  requirement_id: string
  impact: number
  likelihood: number
  score: number
  level: RiskLevel
}

export interface OptimizeResult {
  before_count: number
  after_count: number
  mode: OptimizeMode
  reduction_rate: number
  removed_test_ids?: string[]
}

export interface RevisionLog {
  id: string
  step: number
  entity_type: 'requirement' | 'risk' | 'coverage' | 'test_case'
  entity_id: string
  field: string
  old_value: string
  new_value: string
  timestamp: string
}

export interface ExportRevisionRecord {
  revision_id: string
  session_id: string
  target_type: string
  target_id: string
  before: Record<string, string>
  after: Record<string, string>
  timestamp: string
}

export interface DashboardSummary {
  total_requirements: number
  generated_tests: number
  high_risk_count: number
  ci_status: string
}

export interface DashboardPayload {
  summary: DashboardSummary
  ragas: {
    enabled: boolean
    answer_relevancy: number | null
    faithfulness: number | null
  }
}

export interface ApiResult<T> {
  data: T
  isLive: boolean
  pendingFrom?: string
}
