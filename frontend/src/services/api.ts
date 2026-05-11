/**
 * API service layer
 *
 * Every function tries the real backend first (VITE_API_BASE, default localhost:8000).
 * On any network / HTTP error it falls back to local mock data and sets isLive=false.
 * pendingFrom identifies the team member responsible for the real endpoint.
 *
 * Mock data shapes strictly follow docs/integration_interfaces.md.
 */

import type {
  ApiResult,
  DisplayRequirement,
  FSMResult,
  OptimizeResult,
  OptimizeMode,
  OracleResult,
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

// ── Mock data ─────────────────────────────────────────────────────────────────
// All IDs and shapes follow integration_interfaces.md §2, §3, §4, §5, §6

const MOCK_REQUIREMENTS: DisplayRequirement[] = [
  {
    requirement_id: 'REQ-AUT-001',
    raw_requirement:
      'The system shall return a JSON array of all books when the client sends GET /api/books.',
    source: 'aut_15_requirements',
    input_fields: [],
    data_ranges: [],
    conditions: [],
    expected_action: 'Return 200 with JSON array of all books',
    confidence: 0.91,
    missing_fields: [],
  },
  {
    requirement_id: 'REQ-AUT-008',
    raw_requirement:
      'The system shall create a borrowing record when an existing member borrows an existing book with availableCopies greater than 0.',
    source: 'aut_15_requirements',
    input_fields: ['book.id', 'member.id', 'availableCopies'],
    data_ranges: ['availableCopies: integer > 0'],
    conditions: ['Book exists', 'Member exists', 'availableCopies > 0'],
    expected_action:
      'Return 201, create borrowing record, decrement availableCopies by 1',
    confidence: 0.85,
    missing_fields: [],
  },
  {
    requirement_id: 'REQ-AUT-012',
    raw_requirement:
      'The system shall reject a borrow request when availableCopies equals 0.',
    source: 'aut_15_requirements',
    input_fields: ['book.id', 'member.id'],
    data_ranges: ['availableCopies: integer == 0'],
    conditions: ['Book exists', 'Member exists', 'availableCopies == 0'],
    expected_action: 'Return 422, reject borrow request',
    confidence: 0.88,
    missing_fields: ['error_code'],
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
    test_steps: ['POST /api/borrow with { book.id: 1, member.id: 1 }'],
    expected_result: '201 Created; borrowing record created; availableCopies − 1',
    risk_level: 'High',
    standard_ref: 'ISO/IEC/IEEE 29119-4 §6.4 decision table testing',
  },
  {
    test_id: 'TC-AUT-008-002',
    requirement_id: 'REQ-AUT-008',
    technique: 'BVA',
    title: 'Borrow with availableCopies = 1 (lower boundary)',
    preconditions: ['Book exists', 'Member exists', 'availableCopies == 1'],
    input_data: { 'book.id': 2, 'member.id': 1, availableCopies: 1 },
    test_steps: ['POST /api/borrow with availableCopies at boundary value 1'],
    expected_result: '201 Created; availableCopies becomes 0',
    risk_level: 'High',
    standard_ref: 'ISO/IEC/IEEE 29119-4 §6.2 boundary value analysis',
  },
  {
    test_id: 'TC-AUT-012-001',
    requirement_id: 'REQ-AUT-012',
    technique: 'EP',
    title: 'Reject borrow when no copies available',
    preconditions: ['Book exists', 'Member exists', 'availableCopies == 0'],
    input_data: { 'book.id': 3, 'member.id': 1 },
    test_steps: ['POST /api/borrow with availableCopies == 0'],
    expected_result: '422 Unprocessable Entity; borrow rejected',
    risk_level: 'Medium',
    standard_ref: 'ISO/IEC/IEEE 29119-4 §6.1 equivalence partitioning',
  },
]

const MOCK_FSM: FSMResult = {
  states: ['Available', 'Borrowed', 'Returned', 'Rejected'],
  transitions: [
    {
      from: 'Available',
      to: 'Borrowed',
      event: 'POST /api/borrow',
      condition: 'book exists, member exists, availableCopies > 0',
    },
    {
      from: 'Borrowed',
      to: 'Returned',
      event: 'POST /api/return',
      condition: 'borrowing record exists',
    },
    {
      from: 'Available',
      to: 'Rejected',
      event: 'POST /api/borrow',
      condition: 'availableCopies == 0',
    },
  ],
  coverage: {
    all_states: ['Available', 'Borrowed', 'Returned', 'Rejected'],
    all_transitions: ['Available->Borrowed', 'Borrowed->Returned', 'Available->Rejected'],
  },
  mermaid: `stateDiagram-v2
    [*] --> Available
    Available --> Borrowed : POST /api/borrow [copies > 0]
    Available --> Rejected : POST /api/borrow [copies == 0]
    Borrowed --> Returned : POST /api/return`,
}

const MOCK_ORACLE: OracleResult[] = [
  {
    test_id: 'TC-AUT-008-001',
    llm_verdict: 'Pass',
    rule_verdict: 'Pass',
    confidence: 0.95,
    needs_review: false,
  },
  {
    test_id: 'TC-AUT-008-002',
    llm_verdict: 'Pass',
    rule_verdict: 'Fail',
    confidence: 0.56,
    needs_review: true,
  },
  {
    test_id: 'TC-AUT-012-001',
    llm_verdict: 'Fail',
    rule_verdict: 'Fail',
    confidence: 0.87,
    needs_review: false,
  },
]

const MOCK_RISK: RiskEntry[] = [
  { requirement_id: 'REQ-AUT-008', impact: 5, likelihood: 5, score: 25, level: 'High' },
  { requirement_id: 'REQ-AUT-012', impact: 4, likelihood: 3, score: 12, level: 'Medium' },
  { requirement_id: 'REQ-AUT-001', impact: 2, likelihood: 3, score: 6, level: 'Medium' },
]

const MOCK_OPTIMIZE: OptimizeResult = {
  before_count: MOCK_TEST_CASES.length,
  after_count: 2,
  mode: 'risk_priority',
  reduction_rate: Math.round((1 - 2 / MOCK_TEST_CASES.length) * 100),
}

// ── API functions ─────────────────────────────────────────────────────────────

/**
 * A: POST /ingest (Day 3-4) then POST /parse per req (A+B, Day 5)
 * Returns merged display shape.
 */
export async function ingestAndParse(
  content: string,
): Promise<ApiResult<DisplayRequirement[]>> {
  try {
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

    const merged: DisplayRequirement[] = ingestRes.requirements.map((req, i) => {
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

    return { data: merged, isLive: true }
  } catch {
    return {
      data: MOCK_REQUIREMENTS,
      isLive: false,
      pendingFrom: 'A (POST /ingest, Day 3-4) · B (POST /parse, Day 5)',
    }
  }
}

/**
 * A: POST /fsm (Day 6-7)
 */
export async function generateFSM(
  requirementIds: string[],
): Promise<ApiResult<FSMResult>> {
  try {
    const data = await httpPost<FSMResult>('/fsm', { requirement_ids: requirementIds })
    return { data, isLive: true }
  } catch {
    return {
      data: MOCK_FSM,
      isLive: false,
      pendingFrom: 'A (POST /fsm, Day 6-7)',
    }
  }
}

/**
 * E: POST /generate (Day 10-11)
 */
export async function getTestCases(
  requirementIds?: string[],
): Promise<ApiResult<TestCase[]>> {
  try {
    const data = await httpPost<TestCase[]>('/generate', {
      requirement_ids: requirementIds ?? [],
    })
    return { data, isLive: true }
  } catch {
    return {
      data: MOCK_TEST_CASES,
      isLive: false,
      pendingFrom: 'E (POST /generate, Day 10-11)',
    }
  }
}

/**
 * B: POST /oracle (Day 13-14)
 */
export async function getOracleResults(
  testIds?: string[],
): Promise<ApiResult<OracleResult[]>> {
  try {
    const data = await httpPost<OracleResult[]>('/oracle', { test_ids: testIds ?? [] })
    return { data, isLive: true }
  } catch {
    return {
      data: MOCK_ORACLE,
      isLive: false,
      pendingFrom: 'B (POST /oracle, Day 13-14)',
    }
  }
}

/**
 * B: POST /risk (Day 3-4)
 */
export async function getRiskData(
  requirementIds?: string[],
): Promise<ApiResult<RiskEntry[]>> {
  try {
    const data = await httpPost<RiskEntry[]>('/risk', {
      requirement_ids: requirementIds ?? [],
    })
    return { data, isLive: true }
  } catch {
    return {
      data: MOCK_RISK,
      isLive: false,
      pendingFrom: 'B (POST /risk, Day 3-4)',
    }
  }
}

/**
 * E: POST /optimize (Day 12-13)
 */
export async function getOptimizeResult(
  mode: OptimizeMode = 'risk_priority',
): Promise<ApiResult<OptimizeResult>> {
  try {
    const data = await httpPost<OptimizeResult>('/optimize', { mode })
    return { data, isLive: true }
  } catch {
    return {
      data: { ...MOCK_OPTIMIZE, mode },
      isLive: false,
      pendingFrom: 'E (POST /optimize, Day 12-13)',
    }
  }
}

/**
 * A: GET /export/{format} (Day 8-9)
 * Returns the download URL — no fallback needed, just open in browser.
 */
export function getExportUrl(format: 'json' | 'csv' | 'xlsx'): string {
  return `${BASE}/export/${format}`
}
