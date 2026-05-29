import { postBlob } from '@/shared/api/apiClient'
import type {
  AnalysisResult,
  CoverageItem,
  DisplayRequirement,
  ExportRevisionRecord,
  OptimizeResult,
  PromptEvidence,
  RevisionLog,
  RiskEntry,
  StrategyItem,
  TestCase,
} from '@/shared/types'

const DESIGN_SESSION_ID = 'SESSION-CURRENT'

type ExportFormat = 'json' | 'csv' | 'xlsx'

type ExportSnapshot = {
  requirements: DisplayRequirement[]
  riskEntries: RiskEntry[]
  coverageItems: CoverageItem[]
  strategies: StrategyItem[]
  testCases: TestCase[]
  revisions: RevisionLog[]
  optimizeResult?: OptimizeResult | null
  promptEvidence?: PromptEvidence[]
  analysisResults?: AnalysisResult[]
}

export function mapRevisionsForExport(revisions: RevisionLog[]): ExportRevisionRecord[] {
  return revisions.map((r) => ({
    revision_id: r.id,
    session_id: DESIGN_SESSION_ID,
    target_type: r.entity_type,
    target_id: r.entity_id,
    before: { [r.field]: r.old_value },
    after: { [r.field]: r.new_value },
    reason: r.reason ?? 'designer revision',
    created_by: 'designer',
    created_at: r.timestamp,
    timestamp: r.timestamp,
  }))
}

export async function exportApproved(
  format: ExportFormat,
  snapshot?: ExportSnapshot,
): Promise<Blob> {
  return postBlob('/export', {
    session_id: DESIGN_SESSION_ID,
    format,
    include_revisions: true,
    include_prompt_evidence: true,
    test_case_status: 'approved_only',
    requirements: snapshot?.requirements,
    risk_results: snapshot?.riskEntries.map(mapRiskResult),
    coverage_items: snapshot?.coverageItems.map(mapCoverageItem),
    strategies: snapshot?.strategies,
    test_cases: snapshot?.testCases,
    revisions: snapshot ? mapRevisionsForExport(snapshot.revisions) : undefined,
    optimization_result: snapshot?.optimizeResult,
    prompt_evidence: snapshot?.promptEvidence?.map(mapPromptEvidence),
    analysis_results: snapshot?.analysisResults,
  })
}

function mapPromptEvidence(item: PromptEvidence, index: number) {
  return {
    evidence_id: item.evidence_id ?? `PE-AUT-${String(index + 1).padStart(3, '0')}`,
    session_id: item.session_id ?? DESIGN_SESSION_ID,
    prompt_name: item.prompt_name ?? item.prompt_template_id ?? 'frontend_prompt_evidence',
    target_id: item.target_id ?? null,
    input: item.input ?? item.prompt_inputs ?? {},
    output: item.output ?? { output_summary: item.output_summary ?? '' },
    note: item.note ?? '',
    created_at: item.created_at ?? new Date().toISOString(),
  }
}

function mapCoverageItem(item: CoverageItem) {
  return {
    ...item,
    technique: item.technique ?? item.techniques?.[0] ?? 'EP',
  }
}

function mapRiskResult(item: RiskEntry) {
  return {
    target_id: item.target_id ?? item.requirement_id,
    target_type: item.target_type ?? 'requirement',
    impact: item.impact,
    likelihood: item.likelihood,
    risk_score: item.risk_score ?? item.score,
    risk_level: item.risk_level ?? item.level,
    test_priority: item.test_priority ?? 'P2',
    reason: item.reason ?? item.risk_reason ?? '',
    evidence: item.evidence ?? [],
  }
}
