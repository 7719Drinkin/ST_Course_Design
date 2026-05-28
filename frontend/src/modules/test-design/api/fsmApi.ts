import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { CoverageItem, DisplayRequirement, FSMResult, TestCase } from '@/shared/types'

const EMPTY_FSM: FSMResult = {
  states: [],
  transitions: [],
  coverage_paths: [],
  mermaid: '',
}

type FsmBackendResponse = {
  session_id: string
  fsm: FSMResult
  test_cases: TestCase[]
}

export async function generateFSM(requirements: DisplayRequirement[], coverageItems: CoverageItem[]) {
  return withLiveFallback(
    async () => {
      const response = await postJson<FsmBackendResponse>('/fsm', {
        session_id: 'SESSION-CURRENT',
        requirements: requirements.map((item) => ({
          requirement_id: item.requirement_id,
          raw_text: item.raw_requirement,
          description: item.description,
          source: item.source,
        })),
        parsed_requirements: requirements.map((item) => ({
          requirement_id: item.requirement_id,
          module: item.module,
          raw_text: item.raw_requirement,
          description: item.description,
        })),
        coverage_items: coverageItems,
      })
      return response.fsm
    },
    EMPTY_FSM,
    'A: POST /fsm',
  )
}
