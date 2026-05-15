/**
 * API service — calls reference backend (backend/main.py) with mock fallback.
 */

import type {
  ApiResult,
  CoverageItem,
  DisplayRequirement,
  FSMResult,
  OptimizeMode,
  OptimizeResult,
  OracleResult,
  RevisionLog,
  RiskEntry,
  TestCase,
} from '../types'

const BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000'

async function httpPost<T>(path: string, body: unknown, timeoutMs = 8000): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

async function tryLive<T>(fn: () => Promise<T>, fallback: T, pendingFrom: string): Promise<ApiResult<T>> {
  try {
    const data = await fn()
    return { data, isLive: true }
  } catch {
    return { data: fallback, isLive: false, pendingFrom }
  }
}

// ── Mock fallbacks ────────────────────────────────────────────────────────────

const MOCK_REQUIREMENTS: DisplayRequirement[] = [
  {
    requirement_id: 'REQ-AUT-008',
    raw_requirement:
      'The system shall create a borrowing record when an existing member borrows an existing book with availableCopies greater than 0.',
    source: 'aut_15_requirements',
    input_fields: ['book.id', 'member.id', 'availableCopies'],
    data_ranges: ['availableCopies: integer > 0'],
    conditions: ['Book exists', 'Member exists', 'availableCopies > 0'],
    expected_action: 'Return 201, create borrowing record, decrement availableCopies by 1',
    confidence: 0.85,
    missing_fields: [],
  },
]

const MOCK_TEST_CASES: TestCase[] = [
  {
    test_id: 'TC-AUT-008-001',
    requirement_id: 'REQ-AUT-008',
    technique: 'DT',
    title: 'Borrow existing available book',
    preconditions: ['Book exists', 'Member exists', 'availableCopies > 0'],
    input_data: { 'book.id': 1, 'member.id': 1 },
    test_steps: ['POST /api/borrow'],
    expected_result: '201 Created',
    risk_level: 'High',
    standard_ref: 'ISO/IEC/IEEE 29119-4 §6.4',
    status: 'Draft',
    coverage_item_id: 'CI-REQ-AUT-008',
  },
]

const MOCK_FSM: FSMResult = {
  states: ['Available', 'Borrowed', 'Returned', 'Rejected'],
  transitions: [],
  coverage: { all_states: ['Available', 'Borrowed'], all_transitions: ['Available->Borrowed'] },
  mermaid: 'stateDiagram-v2\n    [*] --> Available',
}

const MOCK_ORACLE: OracleResult[] = [
  { test_id: 'TC-AUT-008-001', llm_verdict: 'Pass', rule_verdict: 'Pass', confidence: 0.95, needs_review: false },
]

const MOCK_RISK: RiskEntry[] = [
  { requirement_id: 'REQ-AUT-008', impact: 5, likelihood: 5, score: 25, level: 'High' },
]

const MOCK_COVERAGE: CoverageItem[] = [
  {
    coverage_item_id: 'CI-REQ-AUT-008',
    requirement_id: 'REQ-AUT-008',
    description: 'Cover: Borrow an available book',
    techniques: ['DT', 'BVA', 'FSM'],
    strategy_rationale: 'High-priority borrowing flow',
  },
]

// ── API ───────────────────────────────────────────────────────────────────────

export async function ingestAndParse(content: string): Promise<ApiResult<DisplayRequirement[]>> {
  return tryLive(
    async () => {
      const ingestRes = await httpPost<{
        requirements: Array<{ requirement_id: string; raw_requirement: string; source: string }>
        errors: string[]
      }>('/ingest', { source_type: 'text', content })

      const parseResults = await Promise.all(
        ingestRes.requirements.map((req) =>
          httpPost<{
            requirement_id: string
            input_fields: string[]
            data_ranges: string[]
            conditions: string[]
            expected_action: string
            confidence: number
            missing_fields: string[]
          }>('/parse', {
            requirement_id: req.requirement_id,
            raw_requirement: req.raw_requirement,
          }),
        ),
      )

      return ingestRes.requirements.map((req, i) => {
        const parsed = parseResults[i]
        return {
          requirement_id: req.requirement_id,
          raw_requirement: req.raw_requirement,
          source: req.source,
          input_fields: parsed.input_fields,
          data_ranges: parsed.data_ranges,
          conditions: parsed.conditions,
          expected_action: parsed.expected_action,
          confidence: parsed.confidence,
          missing_fields: parsed.missing_fields,
        }
      })
    },
    MOCK_REQUIREMENTS,
    'A: POST /ingest · B: POST /parse',
  )
}

export async function getRiskData(requirementIds?: string[]): Promise<ApiResult<RiskEntry[]>> {
  return tryLive(
    () => httpPost<RiskEntry[]>('/risk', { requirement_ids: requirementIds ?? [] }),
    MOCK_RISK,
    'B: POST /risk',
  )
}

export async function getCoverageItems(requirementIds?: string[]): Promise<ApiResult<CoverageItem[]>> {
  return tryLive(
    () => httpPost<CoverageItem[]>('/coverage', { requirement_ids: requirementIds ?? [] }),
    MOCK_COVERAGE,
    'B: POST /coverage',
  )
}

export async function generateFSM(requirementIds: string[]): Promise<ApiResult<FSMResult>> {
  return tryLive(
    () => httpPost<FSMResult>('/fsm', { requirement_ids: requirementIds }),
    MOCK_FSM,
    'A: POST /fsm',
  )
}

export async function getTestCases(requirementIds?: string[]): Promise<ApiResult<TestCase[]>> {
  return tryLive(
    async () => {
      const cases = await httpPost<TestCase[]>('/generate', { requirement_ids: requirementIds ?? [] })
      return cases.map((c) => ({ ...c, status: c.status ?? 'Draft' }))
    },
    MOCK_TEST_CASES,
    'E: POST /generate',
  )
}

export async function getOracleResults(testIds?: string[]): Promise<ApiResult<OracleResult[]>> {
  return tryLive(
    () => httpPost<OracleResult[]>('/oracle', { test_ids: testIds ?? [] }),
    MOCK_ORACLE,
    'B: POST /oracle',
  )
}

export async function getOptimizeResult(
  mode: OptimizeMode = 'risk_priority',
  testIds?: string[],
): Promise<ApiResult<OptimizeResult>> {
  return tryLive(
    () =>
      httpPost<OptimizeResult>('/optimize', {
        mode,
        test_ids: testIds ?? [],
      }),
    { before_count: 3, after_count: 2, mode, reduction_rate: 33, removed_test_ids: [] },
    'E: POST /optimize',
  )
}

export async function exportApproved(
  format: 'json' | 'csv' | 'xlsx',
  testCases: TestCase[],
  revisions: RevisionLog[],
): Promise<Blob> {
  const res = await fetch(`${BASE}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ format, test_cases: testCases, revisions }),
  })
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  return res.blob()
}

export function getExportUrl(format: 'json' | 'csv' | 'xlsx'): string {
  return `${BASE}/export/${format}`
}
