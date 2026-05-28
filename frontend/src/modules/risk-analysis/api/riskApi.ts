import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { AnalyzedRequirement, DisplayRequirement, RiskEntry, RiskResponse } from '@/shared/types'

export function toAnalyzedRequirements(requirements: DisplayRequirement[]): AnalyzedRequirement[] {
  return requirements.map((item) => ({
    requirement_id: item.requirement_id,
    module: item.module,
    description: item.description || item.raw_requirement,
    input_fields: item.input_fields,
    data_ranges: item.data_ranges,
    conditions: item.conditions,
    business_rules: item.business_rules,
    expected_action: item.expected_action,
  }))
}

export async function getRiskData(requirements: DisplayRequirement[]) {
  const analyzedRequirements = toAnalyzedRequirements(requirements)
  return withLiveFallback<RiskEntry[]>(
    async () => {
      const response = await postJson<RiskResponse>('/risk', {
        analyzed_requirements: analyzedRequirements,
      })
      return response.risk_analysis.map((entry) => {
        const score = entry.risk_score ?? entry.score ?? entry.impact * entry.likelihood
        const level = entry.risk_level ?? entry.level ?? (score >= 15 ? 'High' : score >= 8 ? 'Medium' : 'Low')
        return {
          ...entry,
          target_id: entry.target_id ?? entry.requirement_id,
          target_type: entry.target_type ?? 'requirement',
          score,
          level,
          reason: entry.reason ?? entry.risk_reason ?? '',
        }
      })
    },
    [] as RiskEntry[],
    'B: POST /risk',
  )
}
