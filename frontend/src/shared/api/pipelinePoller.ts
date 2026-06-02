/** Cascading pipeline poller — stage N+1 starts only after stage N receives data. */

import { useAppStore } from '@/app/store/appStore'
import { postJson } from '@/shared/api/apiClient'
import type {
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

type PipelineStatusResponse = {
  run_id: string
  status: 'idle' | 'running' | 'completed' | 'failed' | string
  current_stage: string
  completed_stages: string[]
  failed_stage: string
  error: string
  started_at: string
  updated_at: string
}

type PipelineTerminalStatus = 'failed' | 'completed' | null

const POLL_INTERVAL = 2000
const MAX_POLLS = 150

let activeTimers: ReturnType<typeof setInterval>[] = []

export function stopAllPolling() {
  activeTimers.forEach((t) => clearInterval(t))
  activeTimers = []
  clearTabTitle()
  const store = useAppStore.getState()
  store.resetStagePolling()
  store.setPipelineActive(false)
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
  stopAllPolling()
  const store = useAppStore.getState()
  store.resetStagePolling()
  store.setPipelineActive(true)
  store.setStagePolling(1, true)
  pollTabTitle()

  let polls = 0
  let inFlight = false

  const timer = setInterval(async () => {
    if (inFlight) return
    inFlight = true
    if (++polls > MAX_POLLS) {
      store.setStagePolling(1, false)
      clearInterval(timer)
      inFlight = false
      return
    }
    try {
      try {
        const response = await postJson<RiskResponse>('/risk', {
          session_id: 'SESSION-CURRENT',
        })
        if (response.risk_analysis?.length > 0) {
          store.setRiskEntries(normalizeRiskEntries(response.risk_analysis))
          if (response.prompts_used?.length > 0) {
            store.setPromptEvidence(response.prompts_used)
          }
          store.setStagePolling(1, false)
          clearInterval(timer)
          startPollCoverage()
        }
      } catch {
        // backend unreachable, retry next interval
      }
      await stopIfPipelineFailed()
    } finally {
      inFlight = false
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
  let inFlight = false

  const timer = setInterval(async () => {
    if (inFlight) return
    inFlight = true
    if (++polls > MAX_POLLS) {
      store.setStagePolling(2, false)
      clearInterval(timer)
      inFlight = false
      return
    }
    try {
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
            strategyDone = true
          }
        }
      } catch { /* retry */ }

      if (await stopIfPipelineFailed()) return

      if (coverageDone && strategyDone) {
        store.setStagePolling(2, false)
        clearInterval(timer)
        startPollCaseLab()
      }
    } finally {
      inFlight = false
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
  let inFlight = false

  const pollGenerate = async () => {
    try {
      if (!generateDone) {
        const response = await postJson<GenerateResponse>('/generate', {
          session_id: 'SESSION-CURRENT',
        })
        if (response.test_cases?.length > 0) {
          const fsmCases = useAppStore.getState().testCases.filter((t) => t.technique === 'FSM')
          const generatedCases = response.test_cases.map((c: TestCase) => ({
            ...c,
            status: c.status ?? 'Draft',
          }))
          store.setTestCases([...generatedCases, ...fsmCases])
          generateDone = true
        }
      }
    } catch { /* retry */ }
  }

  const pollFsm = async () => {
    try {
      if (!fsmDone) {
        const response = await postJson<{ fsm: FSMResult; test_cases: TestCase[] }>('/fsm', {
          session_id: 'SESSION-CURRENT',
        })
        if (response.fsm && (response.fsm as FSMResult).states?.length > 0) {
          store.setFsm(response.fsm)
          if (response.test_cases?.length > 0) {
            const existing = useAppStore.getState().testCases.filter((t) => t.technique !== 'FSM')
            store.setTestCases([...existing, ...response.test_cases.map((c) => ({ ...c, status: c.status ?? 'Draft' }))])
          }
          fsmDone = true
        }
      }
    } catch { /* retry */ }
  }

  const pollOracle = async () => {
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
  }

  const syncCaseLabSnapshot = async () => {
    await pollGenerate()
    await pollFsm()
    await pollOracle()
  }

  const timer = setInterval(async () => {
    if (inFlight) return
    inFlight = true
    if (++polls > MAX_POLLS) {
      store.setStagePolling(3, false)
      clearInterval(timer)
      inFlight = false
      return
    }

    try {
      await syncCaseLabSnapshot()

      if (await stopIfPipelineTerminal(syncCaseLabSnapshot)) return

      if (generateDone && fsmDone && oracleDone) {
        store.setStagePolling(3, false)
        clearInterval(timer)
        clearTabTitle()
        store.setPipelineActive(false)
      }
    } finally {
      inFlight = false
    }
  }, POLL_INTERVAL)
  registerTimer(timer)
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

async function stopIfPipelineFailed(beforeStop?: () => Promise<void>): Promise<boolean> {
  const terminalStatus = await readPipelineTerminalStatus()
  if (terminalStatus !== 'failed') {
    return false
  }
  if (beforeStop) {
    await beforeStop()
  }
  stopAllPolling()
  return true
}

async function stopIfPipelineTerminal(beforeStop?: () => Promise<void>): Promise<boolean> {
  const terminalStatus = await readPipelineTerminalStatus()
  if (!terminalStatus) {
    return false
  }
  if (beforeStop) {
    await beforeStop()
  }
  stopAllPolling()
  return true
}

async function readPipelineTerminalStatus(): Promise<PipelineTerminalStatus> {
  try {
    const status = await postJson<PipelineStatusResponse>('/pipeline/status', {
      session_id: 'SESSION-CURRENT',
    }, 4000)
    if (status.status === 'failed' || status.status === 'completed') {
      return status.status
    }
  } catch {
    // status endpoint may be temporarily unavailable; keep normal polling behavior.
  }
  return null
}

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
