import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { CoverageItem } from '@/shared/types'

export async function getCoverageItems(requirementIds?: string[]) {
  return withLiveFallback(
    () => postJson<CoverageItem[]>('/coverage', { requirement_ids: requirementIds ?? [] }),
    [] as CoverageItem[],
    'B: POST /coverage',
  )
}
