import { postJson } from '@/shared/api/apiClient'
import type { RevisionLog } from '@/shared/types'

const DESIGN_SESSION_ID = 'SESSION-CURRENT'

const TARGET_TYPE_MAP: Partial<Record<RevisionLog['entity_type'], string>> = {
  requirement: 'requirement',
  parsed_requirement: 'parsed_requirement',
  risk_result: 'risk_result',
  risk: 'risk_result',
  coverage_item: 'coverage_item',
  coverage: 'coverage_item',
  strategy: 'strategy',
  test_case: 'test_case',
}

export function backendRevisionTargetType(revision: RevisionLog): string | undefined {
  return TARGET_TYPE_MAP[revision.entity_type]
}

export function isBackendRevisionSupported(revision: RevisionLog): boolean {
  return Boolean(backendRevisionTargetType(revision))
}

export async function saveRevisionLog(revision: RevisionLog) {
  const targetType = backendRevisionTargetType(revision)
  if (!targetType) return undefined
  return postJson<RevisionSaveResponse>('/revisions', {
    session_id: DESIGN_SESSION_ID,
    target_type: targetType,
    target_id: revision.entity_id,
    before: { [revision.field]: revision.old_value },
    after: { [revision.field]: revision.new_value },
    reason: revision.reason ?? 'designer revision',
    created_by: 'designer',
  })
}

export type RevisionSaveResponse = {
  revision: {
    revision_id: string
    session_id?: string
    target_type?: string
    target_id?: string
    before?: Record<string, unknown>
    after?: Record<string, unknown>
    reason?: string
    created_by?: string
    created_at?: string
  }
  affected_ids: string[]
}
