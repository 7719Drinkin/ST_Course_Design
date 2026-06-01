import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type {
  AnalysisResult,
  FSMResult,
  GenerateResponse,
  OracleResult,
  PromptEvidence,
  RegenerateResult,
  TestCase,
} from '@/shared/types'

export async function regenerateFromRevision(
  revisionId: string,
  currentState?: Record<string, unknown>,
) {
  const data = await postJson<RegenerateResult>('/regenerate', {
    session_id: 'SESSION-CURRENT',
    revision_id: revisionId,
    current_state: currentState,
  })
  return { data, isLive: true }
}

export async function getAnalysisResults(sessionId = 'SESSION-CURRENT') {
  return withLiveFallback(
    async () => {
      const response = await postJson<{
        session_id: string
        analysis_results: AnalysisResult[]
      }>('/analysis', { session_id: sessionId })
      return response.analysis_results
    },
    [] as AnalysisResult[],
    'B/E: POST /analysis',
  )
}

type FsmBackendResponse = {
  session_id: string
  fsm: FSMResult
  test_cases: TestCase[]
  prompt_evidence?: PromptEvidence[]
}

type OracleBackendResponse = {
  session_id: string
  oracle_results: OracleResult[]
  prompt_evidence?: PromptEvidence[]
}

type AnalysisBackendResponse = {
  session_id: string
  analysis_results: AnalysisResult[]
}

export async function refreshDesignArtifacts(sessionId = 'SESSION-CURRENT') {
  const [generate, fsm, oracle] = await Promise.all([
    postJson<GenerateResponse>('/generate', { session_id: sessionId }, 15000),
    postJson<FsmBackendResponse>('/fsm', { session_id: sessionId }, 15000),
    postJson<OracleBackendResponse>('/oracle', { session_id: sessionId }, 15000),
  ])
  const analysis = await postJson<AnalysisBackendResponse>('/analysis', { session_id: sessionId }, 15000)

  const byId = new Map<string, TestCase>()
  for (const item of generate.test_cases ?? []) {
    byId.set(item.test_id, { ...item, status: item.status ?? 'Draft' })
  }
  for (const item of fsm.test_cases ?? []) {
    byId.set(item.test_id, { ...item, status: item.status ?? 'Draft' })
  }

  return {
    testCases: [...byId.values()],
    fsm: fsm.fsm,
    oracleResults: oracle.oracle_results ?? [],
    analysisResults: analysis.analysis_results ?? [],
    promptEvidence: [
      ...(generate.prompts_used ?? []),
      ...(fsm.prompt_evidence ?? []),
      ...(oracle.prompt_evidence ?? []),
    ],
  }
}
