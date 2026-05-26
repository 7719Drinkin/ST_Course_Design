import { postFile, postJsonNoContent } from '@/shared/api/apiClient'
import type { SourceType } from '@/shared/types'

const ALLOWED_EXTENSIONS = ['.txt', '.md', '.pdf', '.docx', '.doc']

export function isAllowedFileType(name: string): boolean {
  const ext = name.slice(name.lastIndexOf('.')).toLowerCase()
  return ALLOWED_EXTENSIONS.includes(ext)
}

export async function ingestText(content: string, sourceType: SourceType = 'direct'): Promise<void> {
  await postJsonNoContent('/ingest', { source_type: sourceType, content })
}

export async function ingestFile(file: File): Promise<void> {
  await postFile('/ingest/file', file)
}
