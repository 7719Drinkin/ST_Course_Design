import { postBlob } from '@/shared/api/apiClient'
import type { ExportRevisionRecord, RevisionLog } from '@/shared/types'

const DESIGN_SESSION_ID = 'SESSION-CURRENT'

type ExportFormat = 'json' | 'csv' | 'xlsx'

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
): Promise<Blob> {
  return postBlob('/export', {
    session_id: DESIGN_SESSION_ID,
    format,
    include_revisions: true,
    include_prompt_evidence: true,
    test_case_status: 'all',
  })
}
