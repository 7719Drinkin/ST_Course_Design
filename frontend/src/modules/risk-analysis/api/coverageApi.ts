import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type {
  AnalyzedRequirement,
  CoverageGoal,
  CoverageResponse,
  RiskEntry,
} from '@/shared/types'

export async function getCoverageGoals(
  analyzedRequirements: AnalyzedRequirement[],
  riskAnalysis: RiskEntry[],
) {
  return withLiveFallback(
    async () => {
      const response = await postJson<CoverageResponse>('/coverage', {
        analyzed_requirements: analyzedRequirements,
        risk_analysis: riskAnalysis,
      })
      return response.coverage_goals
    },
    [] as CoverageGoal[],
    'B: POST /coverage',
  )
}
