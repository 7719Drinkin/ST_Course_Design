import { postBlob } from '@/shared/api/apiClient'
import type {
  CoverageItem,
  ExportRevisionRecord,
  RevisionLog,
  RiskEntry,
  TestCase,
} from '@/shared/types'

const DESIGN_SESSION_ID = 'DS-CURRENT-WORKSPACE'

type ExportFormat = 'json' | 'csv' | 'xlsx'

type ExportExtras = {
  risk_scores: RiskEntry[]
  coverage_items: CoverageItem[]
}

export function mapRevisionsForExport(revisions: RevisionLog[]): ExportRevisionRecord[] {
  return revisions.map((r) => ({
    revision_id: r.id,
    session_id: DESIGN_SESSION_ID,
    target_type: r.entity_type,
    target_id: r.entity_id,
    before: { [r.field]: r.old_value },
    after: { [r.field]: r.new_value },
    timestamp: r.timestamp,
  }))
}

export async function exportApproved(
  format: ExportFormat,
  testCases: TestCase[],
  revisions: RevisionLog[],
  extras?: ExportExtras,
): Promise<Blob> {
  return postBlob('/export', {
    format,
    test_cases: testCases,
    risk_scores: extras?.risk_scores ?? [],
    coverage_items: extras?.coverage_items ?? [],
    revisions: mapRevisionsForExport(revisions),
  })
}
