export type IngestRequirementRow = {
  requirement_id: string
  raw_requirement: string
  source: string
}

export type IngestResponse = {
  requirements: IngestRequirementRow[]
  errors: string[]
}

export type ParseApiRow = {
  requirement_id: string
  input_fields: string[]
  data_ranges: string[]
  conditions: string[]
  expected_action: string
  confidence: number
  missing_fields: string[]
  source_context_ids?: string[]
  prompt_template_id?: string
  retrieved_context_ids?: string[]
  model_name?: string
  output_schema_version?: string
}
