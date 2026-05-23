import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { RiskEntry } from '@/shared/types'

export async function getRiskData(requirementIds?: string[]) {
  return withLiveFallback(
    () => postJson<RiskEntry[]>('/risk', { requirement_ids: requirementIds ?? [] }),
    [] as RiskEntry[],
    'B: POST /risk',
  )
}
