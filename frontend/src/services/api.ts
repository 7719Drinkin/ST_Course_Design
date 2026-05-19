/**
 * API service — calls reference backend (backend/main.py) with empty fallback.
 */

import type {
  ApiResult,
  CoverageItem,
  DashboardPayload,
  DisplayRequirement,
  ExportRevisionRecord,
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

const DESIGN_SESSION_ID = 'DS-CURRENT-WORKSPACE'

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

async function httpGet<T>(path: string, timeoutMs = 8000): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { signal: AbortSignal.timeout(timeoutMs) })
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

type ParseApiRow = {
  requirement_id: string
  input_fields: string[]
  data_ranges: string[]
  conditions: string[]
  expected_action: string
  confidence: number
  missing_fields: string[]
  source_context_ids?: string[]
  prompt_template_id?: string
  retrieved_context_ids?: string[]
  model_name?: string
  output_schema_version?: string
}

function mergeParseRow(
  req: { requirement_id: string; raw_requirement: string; source: string },
  parsed: ParseApiRow,
): DisplayRequirement {
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
    source_context_ids: parsed.source_context_ids ?? [],
    prompt_template_id: parsed.prompt_template_id ?? '',
    retrieved_context_ids: parsed.retrieved_context_ids ?? [],
    model_name: parsed.model_name ?? '',
    output_schema_version: parsed.output_schema_version ?? '',
  }
}

export function mapRevisionsForExport(revisions: RevisionLog[]): ExportRevisionRecord[] {
  return revisions.map((r) => ({
    revision_id: r.id,
    session_id: DESIGN_SESSION_ID,
    target_type: r.entity_type,
    target_id: r.entity_id,
    before: { [r.field]: r.old_value },
    after: { [r.field]: r.new_value },
    timestamp: r.timestamp,
  }))
}

const EMPTY_DASHBOARD: DashboardPayload = {
  summary: {
    total_requirements: 0,
    generated_tests: 0,
    high_risk_count: 0,
    ci_status: 'idle',
  },
  ragas: { enabled: false, answer_relevancy: null, faithfulness: null },
}

const EMPTY_FSM: FSMResult = {
  states: [],
  transitions: [],
  coverage: { all_states: [], all_transitions: [] },
  mermaid: '',
}

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
          httpPost<ParseApiRow>('/parse', {
            requirement_id: req.requirement_id,
            raw_requirement: req.raw_requirement,
          }),
        ),
      )

      return ingestRes.requirements.map((req, i) => mergeParseRow(req, parseResults[i]))
    },
    [],
    'A: POST /ingest · B: POST /parse',
  )
}

export async function getDashboard(): Promise<ApiResult<DashboardPayload>> {
  return tryLive(() => httpGet<DashboardPayload>('/dashboard'), EMPTY_DASHBOARD, 'GET /dashboard')
}

export async function getRiskData(requirementIds?: string[]): Promise<ApiResult<RiskEntry[]>> {
  return tryLive(
    () => httpPost<RiskEntry[]>('/risk', { requirement_ids: requirementIds ?? [] }),
    [],
    'B: POST /risk',
  )
}

export async function getCoverageItems(requirementIds?: string[]): Promise<ApiResult<CoverageItem[]>> {
  return tryLive(
    () => httpPost<CoverageItem[]>('/coverage', { requirement_ids: requirementIds ?? [] }),
    [],
    'B: POST /coverage',
  )
}

export async function generateFSM(requirementIds: string[]): Promise<ApiResult<FSMResult>> {
  return tryLive(
    () => httpPost<FSMResult>('/fsm', { requirement_ids: requirementIds }),
    EMPTY_FSM,
    'A: POST /fsm',
  )
}

export async function getTestCases(requirementIds?: string[]): Promise<ApiResult<TestCase[]>> {
  return tryLive(
    async () => {
      const cases = await httpPost<TestCase[]>('/generate', { requirement_ids: requirementIds ?? [] })
      return cases.map((c) => ({ ...c, status: c.status ?? 'Draft' }))
    },
    [],
    'E: POST /generate',
  )
}

export async function getOracleResults(testIds?: string[]): Promise<ApiResult<OracleResult[]>> {
  return tryLive(
    () => httpPost<OracleResult[]>('/oracle', { test_ids: testIds ?? [] }),
    [],
    'B: POST /oracle',
  )
}

export async function getOptimizeResult(
  mode: OptimizeMode = 'risk_priority',
  testIds?: string[],
): Promise<ApiResult<OptimizeResult>> {
  const beforeCount = testIds?.length ?? 0
  return tryLive(
    () =>
      httpPost<OptimizeResult>('/optimize', {
        mode,
        test_ids: testIds ?? [],
      }),
    { before_count: beforeCount, after_count: beforeCount, mode, reduction_rate: 0, removed_test_ids: [] },
    'E: POST /optimize',
  )
}

export async function exportApproved(
  format: 'json' | 'csv' | 'xlsx',
  testCases: TestCase[],
  revisions: RevisionLog[],
  extras?: { risk_scores: RiskEntry[]; coverage_items: CoverageItem[] },
): Promise<Blob> {
  const res = await fetch(`${BASE}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      format,
      test_cases: testCases,
      risk_scores: extras?.risk_scores ?? [],
      coverage_items: extras?.coverage_items ?? [],
      revisions: mapRevisionsForExport(revisions),
    }),
  })
  if (!res.ok) throw new Error(`Export failed: ${res.status}`)
  return res.blob()
}

export function getExportUrl(format: 'json' | 'csv' | 'xlsx'): string {
  return `${BASE}/export/${format}`
}
