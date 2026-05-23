import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { FSMResult } from '@/shared/types'

const EMPTY_FSM: FSMResult = {
  states: [],
  transitions: [],
  coverage: { all_states: [], all_transitions: [] },
  mermaid: '',
}

export async function generateFSM(requirementIds: string[]) {
  return withLiveFallback(
    () => postJson<FSMResult>('/fsm', { requirement_ids: requirementIds }),
    EMPTY_FSM,
    'A: POST /fsm',
  )
}
