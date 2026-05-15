/**
 * Shared types aligned with docs/integration_interfaces.md
 * and docs/成员C/前端设计说明-作业要求对齐.md
 */

export type RiskLevel = 'High' | 'Medium' | 'Low'
export type Technique = 'EP' | 'BVA' | 'DT' | 'FSM'
export type Verdict = 'Pass' | 'Fail'
export type OptimizeMode = 'risk_priority' | 'normal'
export type TestCaseStatus = 'Draft' | 'Approved' | 'Rejected'

export interface DisplayRequirement {
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
}

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

export interface ApiResult<T> {
  data: T
  isLive: boolean
  pendingFrom?: string
}
