export type ApiErrorPayload = {
  error?: {
    code?: string
    message?: string
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code = 'request_failed',
  ) {
    super(message)
  }
}

export async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
  timeoutMs = 30_000,
): Promise<T> {
  const headers = new Headers(init.headers)
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) headers.set('Authorization', `Bearer ${token}`)

  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(`/api${path}`, { ...init, headers, signal: controller.signal })
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload
      throw new ApiError(
        payload.error?.message ?? '请求失败，请稍后重试',
        response.status,
        payload.error?.code,
      )
    }
    return (await response.json()) as T
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('请求超时，请检查网络后重试', 408, 'request_timeout')
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

export async function apiFetchBlob(path: string, token?: string): Promise<Blob> {
  const headers = new Headers()
  if (token) headers.set('Authorization', `Bearer ${token}`)
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 30_000)
  try {
    const response = await fetch(`/api${path}`, { headers, signal: controller.signal })
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload
      throw new ApiError(payload.error?.message ?? '音频加载失败，请稍后重试', response.status, payload.error?.code)
    }
    return await response.blob()
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('请求超时，请检查网络后重试', 408, 'request_timeout')
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}

