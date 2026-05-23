import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { TestCase } from '@/shared/types'

export async function getTestCases(requirementIds?: string[]) {
  return withLiveFallback(
    async () => {
      const cases = await postJson<TestCase[]>('/generate', {
        requirement_ids: requirementIds ?? [],
      })
      return cases.map((c) => ({ ...c, status: c.status ?? 'Draft' }))
    },
    [] as TestCase[],
    'E: POST /generate',
  )
}
