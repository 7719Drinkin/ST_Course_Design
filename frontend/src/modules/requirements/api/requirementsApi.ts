import { postJson, withLiveFallback } from '@/shared/api/apiClient'
import type { DisplayRequirement } from '@/shared/types'
import type { IngestRequirementRow, IngestResponse, ParseApiRow } from './requirementsTypes'

function mergeParseRow(req: IngestRequirementRow, parsed: ParseApiRow): DisplayRequirement {
  return {
    requirement_id: req.requirement_id,
    raw_requirement: req.raw_requirement,
    source: req.source,
    input_fields: parsed.input_fields,
    data_ranges: parsed.data_ranges,
    conditions: parsed.conditions,
    expected_action: parsed.expected_action,
    confidence: parsed.confidence,
    missing_fields: parsed.missing_fields,
    source_context_ids: parsed.source_context_ids ?? [],
    prompt_template_id: parsed.prompt_template_id ?? '',
    retrieved_context_ids: parsed.retrieved_context_ids ?? [],
    model_name: parsed.model_name ?? '',
    output_schema_version: parsed.output_schema_version ?? '',
  }
}

export async function ingestAndParse(content: string) {
  return withLiveFallback(
    async () => {
      const ingestRes = await postJson<IngestResponse>('/ingest', {
        source_type: 'text',
        content,
      })

      const parseResults = await Promise.all(
        ingestRes.requirements.map((req) =>
          postJson<ParseApiRow>('/parse', {
            requirement_id: req.requirement_id,
            raw_requirement: req.raw_requirement,
          }),
        ),
      )

      return ingestRes.requirements.map((req, i) => mergeParseRow(req, parseResults[i]))
    },
    [] as DisplayRequirement[],
    'A: POST /ingest 路 B: POST /parse',
  )
}
