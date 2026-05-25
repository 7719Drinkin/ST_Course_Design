import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { ConceptItem } from '@/shared/types'

export async function getConcepts(requirementIds?: string[]) {
  return withLiveFallback(
    () => postJson<ConceptItem[]>('/concepts', { requirement_ids: requirementIds ?? [] }),
    [] as ConceptItem[],
    'B/E: POST /concepts',
  )
}
