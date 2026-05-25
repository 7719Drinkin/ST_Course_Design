import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { AnalysisResult, RegenerateResult } from '@/shared/types'

const EMPTY_REGENERATE_RESULT: RegenerateResult = {
  created: [],
  updated: [],
  unchanged: [],
  deprecated: [],
}

export async function regenerateFromRevision(revisionId: string) {
  return withLiveFallback(
    () => postJson<RegenerateResult>('/regenerate', { revision_id: revisionId }),
    EMPTY_REGENERATE_RESULT,
    'B/E: POST /regenerate',
  )
}

export async function getAnalysisResults(sessionId = 'SESSION-CURRENT') {
  return withLiveFallback(
    () => postJson<AnalysisResult[]>('/analysis', { session_id: sessionId }),
    [] as AnalysisResult[],
    'B/E: POST /analysis',
  )
}
