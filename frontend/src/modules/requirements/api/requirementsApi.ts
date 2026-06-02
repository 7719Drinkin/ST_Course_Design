import { postFile, postJsonNoContent } from '@/shared/api/apiClient'
import { postJson } from '@/shared/api/apiClient'
import type { AnalyzedRequirement, DisplayRequirement, ParseResponse } from '@/shared/types'

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
  }, 120000) // /parse runs pipeline inline, needs long timeout
  const parsedById = new Map(response.requirements.map((item) => [item.requirement_id, item]))
  return response.analyzed_requirements.map((item) => {
    const parsed = parsedById.get(item.requirement_id)
    const displayRequirement = {
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
      confidence: 1,
      missing_fields: [],
    }
    const missingFields = getRequirementMissingFields(displayRequirement)
    const completeness = calculateRequirementCompleteness(displayRequirement)
    return {
      ...displayRequirement,
      confidence: completeness.total === 0 ? 0 : Math.max(0.65, completeness.completed / completeness.total),
      missing_fields: missingFields,
    }
  })
}

type RequirementCompletenessInput = Pick<
  AnalyzedRequirement,
  'description' | 'input_fields' | 'data_ranges' | 'conditions' | 'business_rules' | 'expected_action'
> & {
  raw_requirement?: string
}

type RequirementField = 'input_fields' | 'data_ranges' | 'conditions' | 'business_rules' | 'expected_action'

const INPUT_FIELD_PATTERN =
  /(id|identifier|record|path parameter|request body|json body|submit|create|update|delete|borrow|return|book_id|member_id|record_id|图书\s*ID|会员\s*ID|借阅记录\s*ID|请求体|提交|创建|更新|删除|借阅|借书|归还)/

const CONDITION_PATTERN =
  /(if|only if|only when|when|exists|not exist|not found|missing|reject|duplicate|successful|already returned|available copies|condition|如果|只有|当|存在|不存在|缺失|拒绝|重复|成功|已归还|可借副本|条件|状态)/

const DATA_RANGE_PATTERN =
  /(range|boundary|format|yyyy-mm-dd|date|due date|borrow date|return date|greater than|less than|equal to|positive|zero|14 days|0|14|范围|边界|格式|日期|应还日期|借出日期|归还日期|大于|小于|等于|为\s*0|14\s*天)/

function normalizedRequirementText(item: RequirementCompletenessInput): string {
  return [
    item.raw_requirement,
    item.description,
    item.expected_action,
    ...(item.business_rules ?? []),
    ...(item.conditions ?? []),
  ].filter(Boolean).join(' ').toLowerCase()
}

function hasItems(value: unknown[] | undefined): boolean {
  return Array.isArray(value) && value.some((item) => String(item).trim())
}

function isFieldApplicable(item: RequirementCompletenessInput, field: RequirementField): boolean {
  const text = normalizedRequirementText(item)
  switch (field) {
    case 'business_rules':
    case 'expected_action':
      return true
    case 'input_fields':
      return hasItems(item.input_fields) || INPUT_FIELD_PATTERN.test(text)
    case 'conditions':
      return hasItems(item.conditions) || CONDITION_PATTERN.test(text)
    case 'data_ranges':
      return hasItems(item.data_ranges) || DATA_RANGE_PATTERN.test(text)
    default:
      return false
  }
}

function isFieldComplete(item: RequirementCompletenessInput, field: RequirementField): boolean {
  switch (field) {
    case 'input_fields':
      return hasItems(item.input_fields)
    case 'data_ranges':
      return hasItems(item.data_ranges)
    case 'conditions':
      return hasItems(item.conditions)
    case 'business_rules':
      return hasItems(item.business_rules)
    case 'expected_action':
      return Boolean(item.expected_action?.trim())
    default:
      return false
  }
}

export function getRequirementMissingFields(item: RequirementCompletenessInput): RequirementField[] {
  const fields: RequirementField[] = ['input_fields', 'data_ranges', 'conditions', 'business_rules', 'expected_action']
  return fields.filter((field) => isFieldApplicable(item, field) && !isFieldComplete(item, field))
}

export function calculateRequirementCompleteness(item: RequirementCompletenessInput) {
  const fields: RequirementField[] = ['input_fields', 'data_ranges', 'conditions', 'business_rules', 'expected_action']
  return fields.reduce(
    (acc, field) => {
      if (!isFieldApplicable(item, field)) return acc
      return {
        total: acc.total + 1,
        completed: acc.completed + (isFieldComplete(item, field) ? 1 : 0),
      }
    },
    { completed: 0, total: 0 },
  )
}
