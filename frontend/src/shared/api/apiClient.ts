import type { ApiResult } from '@/shared/types'

const API_BASE: string =
  (import.meta.env.VITE_API_BASE as string | undefined) ?? 'http://localhost:8000'

export async function postJson<T>(path: string, body: unknown, timeoutMs = 8000): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

export async function postJsonNoContent(path: string, body: unknown, timeoutMs = 8000): Promise<void> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(timeoutMs),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function postFile(path: string, file: File, timeoutMs = 8000): Promise<void> {
  const formData = new FormData()
  formData.append('file', file)
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    body: formData,
    signal: AbortSignal.timeout(timeoutMs),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
}

export async function postBlob(path: string, body: unknown, timeoutMs?: number): Promise<Blob> {
  const requestInit: RequestInit = {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }
  if (timeoutMs !== undefined) {
    requestInit.signal = AbortSignal.timeout(timeoutMs)
  }
  const res = await fetch(`${API_BASE}${path}`, requestInit)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.blob()
}

export async function withLiveFallback<T>(
  request: () => Promise<T>,
  fallback: T,
  pendingFrom: string,
): Promise<ApiResult<T>> {
  try {
    const data = await request()
    return { data, isLive: true }
  } catch {
    return { data: fallback, isLive: false, pendingFrom }
  }
}
