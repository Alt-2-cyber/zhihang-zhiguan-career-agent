import { ApiError, apiFetch, apiFetchBlob, type ApiErrorPayload } from '../../app/api'
import type {
  ActionOutcome,
  AgentEvent,
  AgentRunAccepted,
  AgentRunDetails,
  AiCapabilities,
  AITask,
  ChatAttachmentUpload,
  ChatContextRef,
  ChatMode,
  ChatSession,
  ChatSessionDetail,
  ChatSessionPage,
  ChatSessionStatus,
} from './types'

export function listChatSessions(token: string, query = '') {
  const suffix = query.trim() ? `?query=${encodeURIComponent(query.trim())}` : ''
  return apiFetch<ChatSessionPage>(`/chat/sessions${suffix}`, {}, token)
}

export function readChatSession(sessionId: string, token: string) {
  return apiFetch<ChatSessionDetail>(`/chat/sessions/${sessionId}`, {}, token)
}

export function createChatSession(
  payload: { title?: string; mode?: ChatMode; subject_student_id?: string | null },
  token: string,
) {
  return apiFetch<ChatSession>('/chat/sessions', { method: 'POST', body: JSON.stringify(payload) }, token)
}

export function updateChatSession(
  sessionId: string,
  payload: { title?: string; mode?: ChatMode; status?: ChatSessionStatus },
  token: string,
) {
  return apiFetch<ChatSession>(
    `/chat/sessions/${sessionId}`,
    { method: 'PATCH', body: JSON.stringify(payload) },
    token,
  )
}

export function postChatMessage(
  sessionId: string,
  payload: { content: string; attachment_ids?: string[]; context_refs?: ChatContextRef[] },
  token: string,
  idempotencyKey: string,
) {
  return apiFetch<AgentRunAccepted>(
    `/chat/sessions/${sessionId}/messages`,
    {
      method: 'POST',
      headers: { 'Idempotency-Key': idempotencyKey },
      body: JSON.stringify(payload),
    },
    token,
  )
}

function actionRequest(path: string, token: string, idempotent = false) {
  const idempotencyKey = typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID()
    : `action-${Date.now()}-${Math.random()}`
  return apiFetch<ActionOutcome>(
    path,
    {
      method: 'POST',
      headers: idempotent ? { 'Idempotency-Key': idempotencyKey } : undefined,
    },
    token,
  )
}

export const confirmChatAction = (proposalId: string, token: string) =>
  actionRequest(`/chat/actions/${proposalId}/confirm`, token, true)

export const rejectChatAction = (proposalId: string, token: string) =>
  actionRequest(`/chat/actions/${proposalId}/reject`, token)

export const undoChatAction = (proposalId: string, token: string) =>
  actionRequest(`/chat/actions/${proposalId}/undo`, token, true)

export const retryAgentRun = (runId: string, token: string) =>
  apiFetch<{ run_id: string; status: string }>(`/chat/runs/${runId}/retry`, { method: 'POST' }, token)

export const readAgentRunDetails = (runId: string, token: string) =>
  apiFetch<AgentRunDetails>(`/chat/runs/${runId}/details`, {}, token)

export function uploadChatRecording(sessionId: string, blob: Blob, token: string) {
  const body = new FormData()
  body.append('file', blob, 'message.webm')
  return apiFetch<{ task_id: string; artifact_id: string; status: string }>(
    `/chat/sessions/${sessionId}/transcriptions`,
    { method: 'POST', body },
    token,
  )
}

export function uploadChatAttachment(sessionId: string, file: File, token: string) {
  const body = new FormData()
  body.append('file', file)
  return apiFetch<ChatAttachmentUpload>(
    `/chat/sessions/${sessionId}/attachments`,
    { method: 'POST', body },
    token,
  )
}

export const readAiTask = (taskId: string, token: string) =>
  apiFetch<AITask>(`/ai/tasks/${taskId}`, {}, token)

export const retryAiTask = (taskId: string, token: string) =>
  apiFetch<AITask>(`/ai/tasks/${taskId}/retry`, { method: 'POST' }, token)

export const synthesizeChatMessage = (messageId: string, token: string) =>
  apiFetch<{ task_id: string; status: string }>(`/chat/messages/${messageId}/synthesis`, { method: 'POST' }, token)

export const downloadAiMedia = (artifactId: string, token: string) =>
  apiFetchBlob(`/ai/media/${artifactId}`, token)

export const readAiCapabilities = (token: string) =>
  apiFetch<AiCapabilities>('/ai/capabilities', {}, token)

function parseEvent(block: string): AgentEvent | null {
  let sequence = Number.NaN
  let eventType = ''
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (!line || line.startsWith(':')) continue
    const separator = line.indexOf(':')
    const field = separator < 0 ? line : line.slice(0, separator)
    const value = separator < 0 ? '' : line.slice(separator + 1).replace(/^ /, '')
    if (field === 'id') sequence = Number(value)
    if (field === 'event') eventType = value
    if (field === 'data') data.push(value)
  }
  if (!Number.isSafeInteger(sequence) || sequence < 1 || !eventType || !data.length) return null
  try {
    const payload = JSON.parse(data.join('\n')) as unknown
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return null
    return { sequence, event_type: eventType, payload: payload as Record<string, unknown> }
  } catch {
    return null
  }
}

export async function streamAgentEvents(
  path: string,
  token: string,
  after: number,
  onEvent: (event: AgentEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const headers = new Headers({ Accept: 'text/event-stream', Authorization: `Bearer ${token}` })
  const separator = path.includes('?') ? '&' : '?'
  const response = await fetch(`/api${path}${separator}after=${after}`, { method: 'GET', headers, signal })
  if (!response.ok) {
    const payload = (await response.json().catch(() => ({}))) as ApiErrorPayload
    throw new ApiError(payload.error?.message ?? '事件流连接失败', response.status, payload.error?.code)
  }
  if (!response.body) throw new ApiError('浏览器未提供事件流', 502, 'stream_unavailable')

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  try {
    while (true) {
      const { done, value } = await reader.read()
      buffer += decoder.decode(value, { stream: !done }).replace(/\r\n/g, '\n')
      let boundary = buffer.indexOf('\n\n')
      while (boundary >= 0) {
        const event = parseEvent(buffer.slice(0, boundary))
        buffer = buffer.slice(boundary + 2)
        if (event) onEvent(event)
        boundary = buffer.indexOf('\n\n')
      }
      if (done) break
    }
    const trailing = parseEvent(buffer)
    if (trailing) onEvent(trailing)
  } finally {
    reader.releaseLock()
  }
}
