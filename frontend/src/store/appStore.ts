import { create } from 'zustand'
import type {
  CoverageItem,
  DisplayRequirement,
  FSMResult,
  OptimizeResult,
  OracleResult,
  RevisionLog,
  RiskEntry,
  TestCase,
} from '../types'

type AppState = {
  currentStep: number
  setCurrentStep: (step: number) => void

  requirements: DisplayRequirement[]
  setRequirements: (data: DisplayRequirement[]) => void
  updateRequirement: (id: string, patch: Partial<DisplayRequirement>) => void

  riskEntries: RiskEntry[]
  setRiskEntries: (data: RiskEntry[]) => void
  updateRiskLevel: (requirementId: string, level: RiskEntry['level']) => void

  coverageItems: CoverageItem[]
  setCoverageItems: (data: CoverageItem[]) => void

  testCases: TestCase[]
  setTestCases: (data: TestCase[]) => void
  updateTestCase: (testId: string, patch: Partial<TestCase>) => void

  oracleResults: OracleResult[]
  setOracleResults: (data: OracleResult[]) => void

  fsm: FSMResult | null
  setFsm: (data: FSMResult | null) => void

  optimizeResult: OptimizeResult | null
  setOptimizeResult: (data: OptimizeResult | null) => void

  revisions: RevisionLog[]
  addRevision: (entry: Omit<RevisionLog, 'id' | 'timestamp'>) => void

  highlightedRequirementId: string | null
  setHighlightedRequirementId: (id: string | null) => void
}

let revisionCounter = 0

export const useAppStore = create<AppState>((set, get) => ({
  currentStep: 0,
  setCurrentStep: (step) => set({ currentStep: step }),

  requirements: [],
  setRequirements: (data) => set({ requirements: data }),
  updateRequirement: (id, patch) => {
    const prev = get().requirements.find((r) => r.requirement_id === id)
    if (!prev) return
    Object.entries(patch).forEach(([field, newValue]) => {
      const oldValue = String((prev as unknown as Record<string, unknown>)[field] ?? '')
      if (String(newValue) !== oldValue) {
        get().addRevision({
          step: 0,
          entity_type: 'requirement',
          entity_id: id,
          field,
          old_value: oldValue,
          new_value: String(newValue),
        })
      }
    })
    set({
      requirements: get().requirements.map((r) =>
        r.requirement_id === id ? { ...r, ...patch } : r,
      ),
    })
  },

  riskEntries: [],
  setRiskEntries: (data) => set({ riskEntries: data }),
  updateRiskLevel: (requirementId, level) => {
    const prev = get().riskEntries.find((e) => e.requirement_id === requirementId)
    if (prev && prev.level !== level) {
      get().addRevision({
        step: 1,
        entity_type: 'risk',
        entity_id: requirementId,
        field: 'level',
        old_value: prev.level,
        new_value: level,
      })
    }
    set({
      riskEntries: get().riskEntries.map((e) =>
        e.requirement_id === requirementId ? { ...e, level } : e,
      ),
    })
  },

  coverageItems: [],
  setCoverageItems: (data) => set({ coverageItems: data }),

  testCases: [],
  setTestCases: (data) => set({ testCases: data }),
  updateTestCase: (testId, patch) => {
    const prev = get().testCases.find((t) => t.test_id === testId)
    if (!prev) return
    Object.entries(patch).forEach(([field, newValue]) => {
      const oldValue = String((prev as unknown as Record<string, unknown>)[field] ?? '')
      if (String(newValue) !== oldValue) {
        get().addRevision({
          step: 2,
          entity_type: 'test_case',
          entity_id: testId,
          field,
          old_value: oldValue,
          new_value: String(newValue),
        })
      }
    })
    set({
      testCases: get().testCases.map((t) =>
        t.test_id === testId ? { ...t, ...patch } : t,
      ),
    })
  },

  oracleResults: [],
  setOracleResults: (data) => set({ oracleResults: data }),

  fsm: null,
  setFsm: (data) => set({ fsm: data }),

  optimizeResult: null,
  setOptimizeResult: (data) => set({ optimizeResult: data }),

  revisions: [],
  addRevision: (entry) => {
    revisionCounter += 1
    set({
      revisions: [
        ...get().revisions,
        {
          ...entry,
          id: `REV-${revisionCounter}`,
          timestamp: new Date().toISOString(),
        },
      ],
    })
  },

  highlightedRequirementId: null,
  setHighlightedRequirementId: (id) => set({ highlightedRequirementId: id }),
}))
