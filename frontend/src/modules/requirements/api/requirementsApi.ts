import { postFile, postJsonNoContent } from '@/shared/api/apiClient'
import { postJson } from '@/shared/api/apiClient'
import type { DisplayRequirement, ParseResponse } from '@/shared/types'

const ALLOWED_EXTENSIONS = ['.txt', '.md', '.pdf', '.docx']

export function isAllowedFileType(name: string): boolean {
  const ext = name.slice(name.lastIndexOf('.')).toLowerCase()
  return ALLOWED_EXTENSIONS.includes(ext)
}

export async function ingestText(content: string): Promise<void> {
  await postJsonNoContent('/ingest', { content })
}

export async function ingestFile(file: File): Promise<void> {
  await postFile('/ingest/file', file)
}

export async function parseRequirements(
  requirementText: string,
  source = '输入内容',
): Promise<DisplayRequirement[]> {
  const response = await postJson<ParseResponse>('/parse', {
    requirement_text: requirementText,
  })
  const parsedById = new Map(response.requirements.map((item) => [item.requirement_id, item]))
  return response.analyzed_requirements.map((item) => {
    const parsed = parsedById.get(item.requirement_id)
    const missingFields = [
      item.input_fields.length === 0 ? 'input_fields' : '',
      item.conditions.length === 0 ? 'conditions' : '',
      item.expected_action ? '' : 'expected_action',
    ].filter(Boolean)
    return {
      requirement_id: item.requirement_id,
      module: item.module,
      raw_requirement: parsed?.raw_text || item.description || parsed?.description || '',
      description: item.description || parsed?.description || '',
      source,
      input_fields: item.input_fields,
      data_ranges: item.data_ranges,
      conditions: item.conditions,
      business_rules: item.business_rules,
      expected_action: item.expected_action,
      confidence: missingFields.length === 0 ? 1 : 0.65,
      missing_fields: missingFields,
    }
  })
}
