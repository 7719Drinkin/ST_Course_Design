import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { OptimizeMode, OptimizeResult } from '@/shared/types'

export async function getOptimizeResult(
  mode: OptimizeMode = 'risk_priority',
  testIds?: string[],
) {
  const beforeCount = testIds?.length ?? 0
  return withLiveFallback(
    () =>
      postJson<OptimizeResult>('/optimize', {
        objective: mode,
        mode,
        test_ids: testIds ?? [],
      }),
    { before_count: beforeCount, after_count: beforeCount, mode, reduction_rate: 0, removed_test_ids: [] },
    'E: POST /optimize',
  )
}
