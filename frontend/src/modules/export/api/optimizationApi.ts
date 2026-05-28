import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { CoverageItem, OptimizeMode, OptimizeResult, RiskEntry, TestCase } from '@/shared/types'

export async function getOptimizeResult(
  mode: OptimizeMode = 'risk_priority',
  testCases: TestCase[] = [],
  coverageItems: CoverageItem[] = [],
  riskResults: RiskEntry[] = [],
) {
  const beforeCount = testCases.length
  return withLiveFallback(
    async () => {
      const response = await postJson<{
        session_id: string
        optimization_result: OptimizeResult
      }>('/optimize', {
        session_id: 'SESSION-CURRENT',
        test_cases: testCases,
        coverage_items: coverageItems,
        risk_results: riskResults.map((item) => ({
          target_id: item.target_id ?? item.requirement_id,
          target_type: item.target_type ?? 'requirement',
          impact: item.impact,
          likelihood: item.likelihood,
          risk_score: item.risk_score ?? item.score,
          risk_level: item.risk_level ?? item.level,
          test_priority: item.test_priority ?? 'P2',
          reason: item.reason ?? item.risk_reason ?? '',
          evidence: item.evidence ?? [],
        })),
        objective: mode,
      })
      return response.optimization_result
    },
    { before_count: beforeCount, after_count: beforeCount, objective: mode, removed_test_ids: [] },
    'E: POST /optimize',
  )
}
