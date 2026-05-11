/**
 * Shared types aligned with docs/integration_interfaces.md
 */

export type RiskLevel = 'High' | 'Medium' | 'Low'
export type Technique = 'EP' | 'BVA' | 'DT' | 'FSM'
export type Verdict = 'Pass' | 'Fail'
export type OptimizeMode = 'risk_priority' | 'normal'

/**
 * Merged ingest + parse display shape for Step 1 table.
 * Combines §3.1 IngestResponse + §3.2 ParseResponse + §4.1 B parse output.
 */
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
}

/**
 * E's test case output — integration_interfaces.md §5
 */
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
}

/**
 * A's FSM output — integration_interfaces.md §3.3
 */
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

/**
 * B's Oracle output — pending (Day 13-14)
 */
export interface OracleResult {
  test_id: string
  llm_verdict: Verdict
  rule_verdict: Verdict
  confidence: number
  needs_review: boolean
}

/**
 * B's Risk Engine output — pending (Day 3-4)
 */
export interface RiskEntry {
  requirement_id: string
  impact: number
  likelihood: number
  score: number
  level: RiskLevel
}

/**
 * E's optimize output — pending (Day 12-13)
 */
export interface OptimizeResult {
  before_count: number
  after_count: number
  mode: OptimizeMode
  reduction_rate: number
}

/**
 * Generic API result wrapper.
 * isLive=true  → data from real backend
 * isLive=false → data from local mock fallback; pendingFrom describes who owns the endpoint
 */
export interface ApiResult<T> {
  data: T
  isLive: boolean
  pendingFrom?: string
}
