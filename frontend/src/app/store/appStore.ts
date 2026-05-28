import { create } from 'zustand'
import type {
  AnalysisResult,
  CoverageItem,
  DisplayRequirement,
  FSMResult,
  FsmPathCoverage,
  OptimizeResult,
  OracleResult,
  PromptEvidence,
  RegenerateResult,
  RevisionLog,
  RiskEntry,
  StrategyItem,
  Technique,
  TestCase,
} from '@/shared/types'

type RevisionEntity = RevisionLog['entity_type']

type AppState = {
  currentStep: number
  setCurrentStep: (step: number) => void
  sourceName: string | null
  setSourceName: (name: string | null) => void

  requirements: DisplayRequirement[]
  setRequirements: (data: DisplayRequirement[]) => void
  updateRequirement: (id: string, patch: Partial<DisplayRequirement>, reason?: string) => void

  riskEntries: RiskEntry[]
  setRiskEntries: (data: RiskEntry[]) => void
  updateRiskEntry: (requirementId: string, patch: Partial<RiskEntry>, reason?: string) => void

  coverageItems: CoverageItem[]
  setCoverageItems: (data: CoverageItem[]) => void
  updateCoverageItem: (coverageItemId: string, patch: Partial<CoverageItem>, reason?: string) => void
  addCoverageItem: (item: CoverageItem) => void

  strategies: StrategyItem[]
  setStrategies: (data: StrategyItem[]) => void
  updateStrategy: (strategyId: string, patch: Partial<StrategyItem>, reason?: string) => void

  testCases: TestCase[]
  setTestCases: (data: TestCase[]) => void
  updateTestCase: (testId: string, patch: Partial<TestCase>, reason?: string) => void

  oracleResults: OracleResult[]
  setOracleResults: (data: OracleResult[]) => void

  fsm: FSMResult | null
  setFsm: (data: FSMResult | null) => void
  fsmPathCoverage: Record<string, FsmPathCoverage>
  setFsmPathCoverage: (pathKey: string, status: FsmPathCoverage) => void

  promptEvidence: PromptEvidence[]
  setPromptEvidence: (data: PromptEvidence[]) => void
  addPromptEvidence: (item: PromptEvidence) => void

  regenerateResult: RegenerateResult | null
  setRegenerateResult: (data: RegenerateResult | null) => void

  analysisResults: AnalysisResult[]
  setAnalysisResults: (data: AnalysisResult[]) => void

  optimizeResult: OptimizeResult | null
  setOptimizeResult: (data: OptimizeResult | null) => void

  revisions: RevisionLog[]
  addRevision: (entry: Omit<RevisionLog, 'id' | 'timestamp'>) => void

  highlightedRequirementId: string | null
  setHighlightedRequirementId: (id: string | null) => void
}

let revisionCounter = 0

const TECHNIQUE_OPTIONS: Technique[] = ['EP', 'BVA', 'DT']

export { TECHNIQUE_OPTIONS }

function stringifyRevisionValue(value: unknown) {
  if (value === undefined || value === null) return ''
  if (Array.isArray(value)) return value.join(', ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function collectPatchRevisions<T extends { [key: string]: unknown }>(
  prev: T,
  patch: Partial<T>,
  entity: {
    step: number
    entity_type: RevisionEntity
    entity_id: string
    reason?: string
  },
  addRevision: AppState['addRevision'],
) {
  Object.entries(patch).forEach(([field, newValue]) => {
    const oldValue = stringifyRevisionValue(prev[field])
    const nextValue = stringifyRevisionValue(newValue)
    if (nextValue !== oldValue) {
      addRevision({
        ...entity,
        field,
        old_value: oldValue,
        new_value: nextValue,
      })
    }
  })
}

export const useAppStore = create<AppState>((set, get) => ({
  currentStep: 0,
  setCurrentStep: (step) => set({ currentStep: step }),
  sourceName: null,
  setSourceName: (name) => set({ sourceName: name }),

  requirements: [],
  setRequirements: (data) => set({ requirements: data }),
  updateRequirement: (id, patch, reason = '设计者修订结构化需求') => {
    const prev = get().requirements.find((r) => r.requirement_id === id)
    if (!prev) return
    collectPatchRevisions(prev as unknown as Record<string, unknown>, patch, {
      step: 0,
      entity_type: 'requirement',
      entity_id: id,
      reason,
    }, get().addRevision)
    set({
      requirements: get().requirements.map((r) =>
        r.requirement_id === id ? { ...r, ...patch } : r,
      ),
    })
  },

  riskEntries: [],
  setRiskEntries: (data) => set({ riskEntries: data }),
  updateRiskEntry: (requirementId, patch, reason = '设计者调整风险评分') => {
    const prev = get().riskEntries.find((e) => e.requirement_id === requirementId)
    if (!prev) return
    collectPatchRevisions(prev as unknown as Record<string, unknown>, patch, {
      step: 1,
      entity_type: 'risk_result',
      entity_id: requirementId,
      reason,
    }, get().addRevision)
    set({
      riskEntries: get().riskEntries.map((e) =>
        e.requirement_id === requirementId ? { ...e, ...patch } : e,
      ),
    })
  },

  coverageItems: [],
  setCoverageItems: (data) => set({ coverageItems: data }),
  updateCoverageItem: (coverageItemId, patch, reason = '设计者修订覆盖项') => {
    const prev = get().coverageItems.find((c) => c.coverage_item_id === coverageItemId)
    if (!prev) return
    collectPatchRevisions(prev as unknown as Record<string, unknown>, patch, {
      step: 2,
      entity_type: 'coverage_item',
      entity_id: coverageItemId,
      reason,
    }, get().addRevision)
    set({
      coverageItems: get().coverageItems.map((c) =>
        c.coverage_item_id === coverageItemId ? { ...c, ...patch } : c,
      ),
    })
  },
  addCoverageItem: (item) => {
    get().addRevision({
      step: 2,
      entity_type: 'coverage_item',
      entity_id: item.coverage_item_id,
      field: 'created',
      old_value: '',
      new_value: item.description,
      reason: '设计者新增有效覆盖项',
    })
    set({
      coverageItems: [
        ...get().coverageItems,
        { ...item, designer_added: true, status: item.status ?? 'human_added' },
      ],
    })
  },

  strategies: [],
  setStrategies: (data) => set({ strategies: data }),
  updateStrategy: (strategyId, patch, reason = '设计者修订覆盖策略') => {
    const prev = get().strategies.find((s) => s.strategy_id === strategyId)
    if (!prev) return
    collectPatchRevisions(prev as unknown as Record<string, unknown>, patch, {
      step: 2,
      entity_type: 'strategy',
      entity_id: strategyId,
      reason,
    }, get().addRevision)
    set({
      strategies: get().strategies.map((s) =>
        s.strategy_id === strategyId ? { ...s, ...patch } : s,
      ),
    })
  },

  testCases: [],
  setTestCases: (data) => set({ testCases: data }),
  updateTestCase: (testId, patch, reason = '设计者复核测试用例') => {
    const prev = get().testCases.find((t) => t.test_id === testId)
    if (!prev) return
    collectPatchRevisions(prev as unknown as Record<string, unknown>, patch, {
      step: 3,
      entity_type: 'test_case',
      entity_id: testId,
      reason,
    }, get().addRevision)
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
  fsmPathCoverage: {},
  setFsmPathCoverage: (pathKey, status) => {
    const prev = get().fsmPathCoverage[pathKey] ?? 'pending'
    if (prev !== status) {
      get().addRevision({
        step: 3,
        entity_type: 'fsm',
        entity_id: pathKey,
        field: 'fsm_path_coverage',
        old_value: prev,
        new_value: status,
        reason: '设计者确认 FSM 覆盖路径',
      })
    }
    set({ fsmPathCoverage: { ...get().fsmPathCoverage, [pathKey]: status } })
  },

  promptEvidence: [],
  setPromptEvidence: (data) => set({ promptEvidence: data }),
  addPromptEvidence: (item) => set({ promptEvidence: [...get().promptEvidence, item] }),

  regenerateResult: null,
  setRegenerateResult: (data) => set({ regenerateResult: data }),

  analysisResults: [],
  setAnalysisResults: (data) => set({ analysisResults: data }),

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
          id: `REV-${String(revisionCounter).padStart(4, '0')}`,
          timestamp: new Date().toISOString(),
        },
      ],
    })
  },

  highlightedRequirementId: null,
  setHighlightedRequirementId: (id) => set({ highlightedRequirementId: id }),
}))
