import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { OracleResult } from '@/shared/types'

export async function getOracleResults(testIds?: string[]) {
  return withLiveFallback(
    () => postJson<OracleResult[]>('/oracle', { test_ids: testIds ?? [] }),
    [] as OracleResult[],
    'B: POST /oracle',
  )
}
