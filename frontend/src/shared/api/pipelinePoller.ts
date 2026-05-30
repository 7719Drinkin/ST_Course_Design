/** Cascading pipeline poller — stage N+1 starts only after stage N receives data. */

import { useAppStore } from '@/app/store/appStore'
import { postJson } from '@/shared/api/apiClient'
import type {
  CoverageGoal,
  CoverageItem,
  CoverageResponse,
  FSMResult,
  GenerateResponse,
  OracleResult,
  RiskEntry,
  RiskResponse,
  StrategyResponse,
  TestCase,
} from '@/shared/types'

type OracleBackendResponse = {
  session_id: string
  oracle_results: OracleResult[]
}

const POLL_INTERVAL = 2000
const MAX_POLLS = 150

let activeTimers: ReturnType<typeof setInterval>[] = []

export function stopAllPolling() {
  activeTimers.forEach((t) => clearInterval(t))
  activeTimers = []
  clearTabTitle()
  useAppStore.getState().setPipelineActive(false)
}

function registerTimer(timer: ReturnType<typeof setInterval>) {
  activeTimers.push(timer)
}

function clearTabTitle() {
  document.title = 'AutoTestDesign'
}

function pollTabTitle() {
  document.title = '\u27F3 AutoTestDesign'
}

/**
 * Stage 1: poll POST /risk until data arrives, then cascade to stage 2.
 */
export function startPollRisk() {
  const store = useAppStore.getState()
  store.setPipelineActive(true)
  store.setStagePolling(1, true)
  pollTabTitle()

  let polls = 0

  const timer = setInterval(async () => {
    if (++polls > MAX_POLLS) {
      store.setStagePolling(1, false)
      clearInterval(timer)
      return
    }
    try {
      const response = await postJson<RiskResponse>('/risk', {
        session_id: 'SESSION-CURRENT',
      })
      if (response.risk_analysis?.length > 0) {
        store.setRiskEntries(normalizeRiskEntries(response.risk_analysis))
        store.setStagePolling(1, false)
        clearInterval(timer)
        startPollCoverage()
      }
    } catch {
      // backend unreachable, retry next interval
    }
  }, POLL_INTERVAL)
  registerTimer(timer)
}

/**
 * Stage 2: poll POST /coverage + POST /strategy in parallel.
 * When both return data, cascade to stage 3.
 */
function startPollCoverage() {
  const store = useAppStore.getState()
  store.setStagePolling(2, true)

  let coverageDone = false
  let strategyDone = false
  let polls = 0

  const timer = setInterval(async () => {
    if (++polls > MAX_POLLS) {
      store.setStagePolling(2, false)
      clearInterval(timer)
      return
    }
    try {
      if (!coverageDone) {
        const response = await postJson<CoverageResponse>('/coverage', {
          session_id: 'SESSION-CURRENT',
        })
        if (response.coverage_goals?.length > 0) {
          store.setCoverageGoals(response.coverage_goals)
          coverageDone = true
        }
      }
    } catch { /* retry */ }

    try {
      if (!strategyDone) {
        const response = await postJson<StrategyResponse>('/strategy', {
          session_id: 'SESSION-CURRENT',
        })
        if (response.coverage_items?.length > 0) {
          store.setCoverageItems(normalizeCoverageItems(response.coverage_items))
          store.setStrategies(response.coverage_items)
          strategyDone = true
        }
      }
    } catch { /* retry */ }

    if (coverageDone && strategyDone) {
      store.setStagePolling(2, false)
      clearInterval(timer)
      startPollCaseLab()
    }
  }, POLL_INTERVAL)
  registerTimer(timer)
}

/**
 * Stage 3: poll POST /generate + /fsm + /oracle in parallel.
 * When all three return data, auto-polling ends.
 */
function startPollCaseLab() {
  const store = useAppStore.getState()
  store.setStagePolling(3, true)

  let generateDone = false
  let fsmDone = false
  let oracleDone = false
  let polls = 0

  const timer = setInterval(async () => {
    if (++polls > MAX_POLLS) {
      store.setStagePolling(3, false)
      clearInterval(timer)
      return
    }

    try {
      if (!generateDone) {
        const response = await postJson<GenerateResponse>('/generate', {
          session_id: 'SESSION-CURRENT',
        })
        if (response.test_cases?.length > 0) {
          store.setTestCases(response.test_cases.map((c: TestCase) => ({
            ...c,
            status: c.status ?? 'Draft',
          })))
          generateDone = true
        }
      }
    } catch { /* retry */ }

    try {
      if (!fsmDone) {
        const response = await postJson<{ fsm: FSMResult; test_cases: TestCase[] }>('/fsm', {
          session_id: 'SESSION-CURRENT',
        })
        if (response.fsm && (response.fsm as FSMResult).states?.length > 0) {
          store.setFsm(response.fsm)
          fsmDone = true
        }
      }
    } catch { /* retry */ }

    try {
      if (!oracleDone) {
        const response = await postJson<OracleBackendResponse>('/oracle', {
          session_id: 'SESSION-CURRENT',
        })
        if (response.oracle_results?.length > 0) {
          store.setOracleResults(response.oracle_results)
          oracleDone = true
        }
      }
    } catch { /* retry */ }

    if (generateDone && fsmDone && oracleDone) {
      store.setStagePolling(3, false)
      clearInterval(timer)
      clearTabTitle()
      store.setPipelineActive(false)
    }
  }, POLL_INTERVAL)
  registerTimer(timer)
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

function normalizeRiskEntries(entries: RiskEntry[]): RiskEntry[] {
  return entries.map((entry) => {
    const score = entry.risk_score ?? entry.score ?? entry.impact * entry.likelihood
    const level = entry.risk_level ?? entry.level ?? (score >= 15 ? 'High' : score >= 8 ? 'Medium' : 'Low')
    return {
      ...entry,
      target_id: entry.target_id ?? entry.requirement_id,
      target_type: entry.target_type ?? 'requirement' as const,
      score,
      level,
      reason: entry.reason ?? entry.risk_reason ?? '',
    }
  })
}

function normalizeCoverageItems(items: CoverageItem[]): CoverageItem[] {
  return items.map((item) => ({
    ...item,
    techniques: item.techniques?.length ? item.techniques : item.technique ? [item.technique] : ['EP' as const],
    status: item.status ?? 'ai_generated' as const,
  }))
}
