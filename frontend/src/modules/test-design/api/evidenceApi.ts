import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { AnalysisResult, RegenerateResult } from '@/shared/types'

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
