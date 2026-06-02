import { create } from 'zustand'
import { saveRevisionLog } from '@/modules/test-design/api/revisionsApi'
import type {
  AnalysisResult,
  CoverageGoal,
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
type RevisionSyncStatus = 'pending' | 'saving' | 'saved' | 'failed'
type PendingRevision = { entity: Omit<RevisionLog, 'id' | 'timestamp' | 'syncStatus'>; id: string }

type AppState = {
  currentStep: number
  setCurrentStep: (step: number) => void
  sourceName: string | null
  setSourceName: (name: string | null) => void

  stagePolling: Record<number, boolean>
  setStagePolling: (index: number, polling: boolean) => void
  resetStagePolling: () => void

  pipelineActive: boolean
  setPipelineActive: (active: boolean) => void

  regenerateTriggered: boolean
  setRegenerateTriggered: (v: boolean) => void

  pendingRevisions: PendingRevision[]
  addPendingRevision: (entry: Omit<RevisionLog, 'id' | 'timestamp' | 'syncStatus'>) => void
  commitPendingRevisions: () => Promise<void>
  clearPendingRevisions: () => void

  requirements: DisplayRequirement[]
  setRequirements: (data: DisplayRequirement[]) => void
  updateRequirement: (id: string, patch: Partial<DisplayRequirement>, reason?: string, immediate?: boolean) => void

  riskEntries: RiskEntry[]
  setRiskEntries: (data: RiskEntry[]) => void
  updateRiskEntry: (requirementId: string, patch: Partial<RiskEntry>, reason?: string, immediate?: boolean) => void

  coverageItems: CoverageItem[]
  setCoverageItems: (data: CoverageItem[]) => void
  updateCoverageItem: (coverageItemId: string, patch: Partial<CoverageItem>, reason?: string, immediate?: boolean) => void
  addCoverageItem: (item: CoverageItem) => void

  coverageGoals: CoverageGoal[]
  setCoverageGoals: (data: CoverageGoal[]) => void

  strategies: StrategyItem[]
  setStrategies: (data: StrategyItem[]) => void
  updateStrategy: (strategyId: string, patch: Partial<StrategyItem>, reason?: string, immediate?: boolean) => void

  testCases: TestCase[]
  setTestCases: (data: TestCase[]) => void
  updateTestCase: (testId: string, patch: Partial<TestCase>, reason?: string, immediate?: boolean) => void
  replaceTestCase: (testId: string, next: TestCase, reason?: string) => void

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
  entity: { step: number; entity_type: RevisionEntity; entity_id: string; reason?: string },
  addRevisionFn: (entry: Omit<RevisionLog, 'id' | 'timestamp'>) => void,
) {
  Object.entries(patch).forEach(([field, newValue]) => {
    const oldValue = stringifyRevisionValue(prev[field])
    const nextValue = stringifyRevisionValue(newValue)
    if (nextValue !== oldValue) {
      addRevisionFn({ ...entity, field, old_value: oldValue, new_value: nextValue })
    }
  })
}

export const useAppStore = create<AppState>((set, get) => ({
  currentStep: 0,
  setCurrentStep: (step) => set({ currentStep: step }),
  sourceName: null,
  setSourceName: (name) => set({ sourceName: name }),

  stagePolling: { 0: false, 1: false, 2: false, 3: false, 4: false, 5: false },
  setStagePolling: (index, polling) =>
    set({ stagePolling: { ...get().stagePolling, [index]: polling } }),
  resetStagePolling: () =>
    set({ stagePolling: { 0: false, 1: false, 2: false, 3: false, 4: false, 5: false } }),

  pipelineActive: false,
  setPipelineActive: (active) => set({ pipelineActive: active }),

  regenerateTriggered: false,
  setRegenerateTriggered: (v) => set({ regenerateTriggered: v }),

  pendingRevisions: [],
  addPendingRevision: (entry) =>
    set({ pendingRevisions: [...get().pendingRevisions, { entity: entry, id: `P-${Date.now()}` }] }),
  commitPendingRevisions: async () => {
    const pending = get().pendingRevisions
    if (pending.length === 0) return
    for (const p of pending) {
      revisionCounter += 1
      const rev: RevisionLog = {
        ...p.entity,
        id: `REV-${String(revisionCounter).padStart(3, '0')}`,
        timestamp: new Date().toISOString(),
        syncStatus: 'saving',
      }
      set({ revisions: [...get().revisions, rev] })
      try {
        const response = await saveRevisionLog(rev)
        if (!response?.revision.revision_id) throw new Error('revision is not supported by backend')
        const savedId = response.revision.revision_id
        set({ revisions: get().revisions.map((r) => r.id === rev.id ? { ...r, id: savedId, syncStatus: 'saved' as RevisionSyncStatus } : r) })
      } catch {
        set({ revisions: get().revisions.map((r) => r.id === rev.id ? { ...r, syncStatus: 'failed' as RevisionSyncStatus } : r) })
      }
    }
    set({ pendingRevisions: [] })
  },
  clearPendingRevisions: () => set({ pendingRevisions: [] }),

  requirements: [],
  setRequirements: (data) => set({ requirements: data }),
  updateRequirement: (id, patch, reason = '设计者修订结构化需求', immediate = false) => {
    const prev = get().requirements.find((r) => r.requirement_id === id)
    if (!prev) return
    const target = immediate ? get().addRevision : get().addPendingRevision
    collectPatchRevisions(prev as unknown as Record<string, unknown>, patch, {
      step: 0, entity_type: 'requirement', entity_id: id, reason,
    }, target)
    set({ requirements: get().requirements.map((r) => r.requirement_id === id ? { ...r, ...patch } : r) })
  },

  riskEntries: [],
  setRiskEntries: (data) => set({ riskEntries: data }),
  updateRiskEntry: (requirementId, patch, reason = '设计者调整风险评分', immediate = true) => {
    const prev = get().riskEntries.find((e) => e.requirement_id === requirementId)
    if (!prev) return
    const merged = { ...prev, ...patch }
    if (patch.impact !== undefined || patch.likelihood !== undefined) {
      const score = merged.impact * merged.likelihood
      const level = score >= 15 ? 'High' as const : score >= 8 ? 'Medium' as const : 'Low' as const
      patch = { ...patch, score, level }
    }
    const target = immediate ? get().addRevision : get().addPendingRevision
    collectPatchRevisions(prev as unknown as Record<string, unknown>, patch, {
      step: 1, entity_type: 'risk_result', entity_id: requirementId, reason,
    }, target)
    set({ riskEntries: get().riskEntries.map((e) => e.requirement_id === requirementId ? { ...e, ...patch } : e) })
  },

  coverageItems: [],
  setCoverageItems: (data) => set({ coverageItems: data }),
  updateCoverageItem: (coverageItemId, patch, reason = '设计者修订覆盖项', immediate = false) => {
    const prev = get().coverageItems.find((c) => c.coverage_item_id === coverageItemId)
    if (!prev) return
    const target = immediate ? get().addRevision : get().addPendingRevision
    collectPatchRevisions(prev as unknown as Record<string, unknown>, patch, {
      step: 2, entity_type: 'coverage_item', entity_id: coverageItemId, reason,
    }, target)
    set({ coverageItems: get().coverageItems.map((c) => c.coverage_item_id === coverageItemId ? { ...c, ...patch } : c) })
  },
  addCoverageItem: (item) => {
    get().addRevision({
      step: 2, entity_type: 'coverage_item', entity_id: item.coverage_item_id,
      field: 'created', old_value: '', new_value: item.description,
      reason: '设计者新增有效覆盖项',
    })
    set({ coverageItems: [...get().coverageItems, { ...item, designer_added: true, status: item.status ?? 'human_added' }] })
  },

  coverageGoals: [],
  setCoverageGoals: (data) => set({ coverageGoals: data }),

  strategies: [],
  setStrategies: (data) => set({ strategies: data }),
  updateStrategy: (strategyId, patch, reason = '设计者修订覆盖策略', immediate = false) => {
    const prev = get().strategies.find((s) => s.strategy_id === strategyId)
    if (!prev) return
    const target = immediate ? get().addRevision : get().addPendingRevision
    collectPatchRevisions(prev as unknown as Record<string, unknown>, patch, {
      step: 2, entity_type: 'strategy', entity_id: strategyId, reason,
    }, target)
    set({ strategies: get().strategies.map((s) => s.strategy_id === strategyId ? { ...s, ...patch } : s) })
  },

  testCases: [],
  setTestCases: (data) => set({ testCases: data }),
  updateTestCase: (testId, patch, reason = '设计者复核测试用例', immediate = false) => {
    const prev = get().testCases.find((t) => t.test_id === testId)
    if (!prev) return
    const target = immediate ? get().addRevision : get().addPendingRevision
    collectPatchRevisions(prev as unknown as Record<string, unknown>, patch, {
      step: 3, entity_type: 'test_case', entity_id: testId, reason,
    }, target)
    set({ testCases: get().testCases.map((t) => t.test_id === testId ? { ...t, ...patch } : t) })
  },
  replaceTestCase: (testId, next, reason = '设计者修订完整测试用例') => {
    const prev = get().testCases.find((t) => t.test_id === testId)
    if (!prev) return
    const revised = { ...next, test_id: testId }
    if (JSON.stringify(prev) === JSON.stringify(revised)) return
    get().addRevision({
      step: 3,
      entity_type: 'test_case',
      entity_id: testId,
      field: 'test_case',
      old_value: '完整测试用例修订前',
      new_value: '完整测试用例修订后',
      before: prev as unknown as Record<string, unknown>,
      after: revised as unknown as Record<string, unknown>,
      reason,
    })
    set({
      testCases: get().testCases.map((t) => t.test_id === testId ? revised : t),
      oracleResults: get().oracleResults.map((oracle) => (
        oracle.test_id === testId
          ? {
              ...oracle,
              needs_review: true,
              confidence: Math.min(oracle.confidence, 0.69),
              explanation: [
                oracle.explanation,
                'Designer changed the test case; rerun Oracle review before export.',
              ].filter(Boolean).join(' '),
            }
          : oracle
      )),
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
        step: 3, entity_type: 'fsm', entity_id: pathKey,
        field: 'fsm_path_coverage', old_value: prev, new_value: status,
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
    const revision: RevisionLog = {
      ...entry,
      id: `REV-${String(revisionCounter).padStart(3, '0')}`,
      timestamp: new Date().toISOString(),
      syncStatus: 'saving',
    }
    set({ revisions: [...get().revisions, revision] })
    void saveRevisionLog(revision).then((response) => {
      if (!response?.revision.revision_id) throw new Error('revision is not supported by backend')
      const savedId = response.revision.revision_id
      set({ revisions: get().revisions.map((r) => r.id === revision.id ? { ...r, id: savedId, syncStatus: 'saved' as RevisionSyncStatus } : r) })
    }).catch(() => {
      set({ revisions: get().revisions.map((r) => r.id === revision.id ? { ...r, syncStatus: 'failed' as RevisionSyncStatus } : r) })
    })
  },

  highlightedRequirementId: null,
  setHighlightedRequirementId: (id) => set({ highlightedRequirementId: id }),
}))
