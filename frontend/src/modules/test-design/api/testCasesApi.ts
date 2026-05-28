import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { CoverageItem, GenerateResponse, RiskEntry, TestCase } from '@/shared/types'

export async function getTestCases(coverageItems: CoverageItem[], riskAnalysis: RiskEntry[]) {
  return withLiveFallback(
    async () => {
      const response = await postJson<GenerateResponse>('/generate', {
        coverage_items: coverageItems,
        risk_analysis: riskAnalysis,
      })
      return response.test_cases.map((c) => ({ ...c, status: c.status ?? 'Draft' }))
    },
    [] as TestCase[],
    'B: POST /generate',
  )
}
