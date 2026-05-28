import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { DisplayRequirement, OracleResult, TestCase } from '@/shared/types'

type OracleBackendResponse = {
  session_id: string
  oracle_results: OracleResult[]
}

export async function getOracleResults(testCases: TestCase[], requirements: DisplayRequirement[]) {
  return withLiveFallback(
    async () => {
      const response = await postJson<OracleBackendResponse>('/oracle', {
        session_id: 'SESSION-CURRENT',
        test_cases: testCases,
        requirements: requirements.map((item) => ({
          requirement_id: item.requirement_id,
          raw_text: item.raw_requirement,
          description: item.description,
          source: item.source,
        })),
      })
      return response.oracle_results
    },
    [] as OracleResult[],
    'B: POST /oracle',
  )
}
