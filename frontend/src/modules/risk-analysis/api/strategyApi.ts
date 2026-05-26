import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { StrategyItem } from '@/shared/types'

export async function getStrategies(coverageItemIds?: string[]) {
  return withLiveFallback(
    () => postJson<StrategyItem[]>('/strategy', { coverage_item_ids: coverageItemIds ?? [] }),
    [] as StrategyItem[],
    'B/E: POST /strategy',
  )
}
