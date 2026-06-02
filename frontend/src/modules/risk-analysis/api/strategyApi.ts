import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type {
  AnalyzedRequirement,
  CoverageGoal,
  CoverageItem,
  RiskEntry,
  StrategyResponse,
} from '@/shared/types'

export async function getCoverageItems(
  coverageGoals: CoverageGoal[],
  analyzedRequirements: AnalyzedRequirement[],
  riskAnalysis: RiskEntry[],
) {
  return withLiveFallback(
    async () => {
      const response = await postJson<StrategyResponse>('/strategy', {
        coverage_goals: coverageGoals,
        analyzed_requirements: analyzedRequirements,
        risk_analysis: riskAnalysis,
      })
      return response.coverage_items.map((item) => ({
        ...item,
        techniques: item.technique ? [item.technique] : item.techniques ?? ['EP'],
        status: item.status ?? 'ai_generated',
      }))
    },
    [] as CoverageItem[],
    'B: POST /strategy',
  )
}
