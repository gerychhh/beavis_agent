import { invoke } from '@tauri-apps/api/core'

export type ApiResult<T = unknown> = {
  ok: boolean
  data: T | null
  error: string | null
  code: string | null
  meta: Record<string, unknown>
}

export async function beavisCall<T = unknown>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<ApiResult<T>> {
  return await invoke<ApiResult<T>>('beavis_call', { method, params })
}
