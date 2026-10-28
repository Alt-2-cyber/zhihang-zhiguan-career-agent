import { ApiError } from '../../app/api'

export type InterviewQuestion = {
  provider?: string
  question_id: string
  question: string
  competency: string
}

const defaultInterviewQuestion = '请结合一个真实经历，说明你在目标岗位中承担的职责、关键行动和实际结果。'

export function displayInterviewText(
  value: string | null | undefined,
  fallback = defaultInterviewQuestion,
): string | null {
  const text = value?.trim()
  if (!text) return null
  const chineseCount = Array.from(text).filter((character) => /[\u3400-\u9fff]/u.test(character)).length
  const latinCount = Array.from(text).filter((character) => /[A-Za-z]/u.test(character)).length
  return chineseCount === 0 || latinCount > chineseCount ? fallback : text
}

export function displayInterviewQuestion(value: string | null | undefined): string | null {
  return displayInterviewText(value)
}

export type InterviewProgress = {
  core_current: number
  core_total: number
  follow_ups_used: number
  follow_ups_max: number
  turns_answered: number
  max_turns: number
  current_kind: 'core' | 'follow_up' | null
}

export type InterviewEvaluation = {
  content_completeness?: number
  job_relevance?: number
  answer_structure?: number
  evidence_quality?: number
  emotion_stability?: number
  feedback?: string[]
}

export type InterviewFinalReport = {
  turns_answered: number
  average_scores: Record<string, number>
  strengths: string[]
  improvements: string[]
  feedback: string[]
}

export type InterviewTurn = {
  id: string
  sequence: number
  question: string
  answer: string
  evaluation: InterviewEvaluation
  emotion?: EmotionSummary | null
  assistant_content?: string | null
  created_at?: string
}

export type EmotionObservation = {
  face_detected: boolean
  face_count: number
  face_boxes: Array<{
    x: number
    y: number
    width: number
    height: number
    confidence: number
  }>
  dominant_emotion: string
  dominant_emotion_label: string
  confidence: number
  presentation_score: number | null
  model: string
  device: string
  warning?: string | null
}

export type EmotionSummary = {
  sample_count: number
  face_presence_rate: number
  dominant_emotion: string
  mean_confidence: number
  stability_score: number | null
  model: string
  warning?: string | null
}

export type InterviewSession = {
  id: string
  status: 'active' | 'completed'
  provider?: string
  rubric_version?: string
  question: InterviewQuestion | null
  progress: InterviewProgress
  turns: InterviewTurn[]
  final_report: InterviewFinalReport | null
  job: { id: string; title: string; company: string } | null
}

export type InterviewStreamState = {
  session_id: string
  evaluation: InterviewEvaluation
  next_question: InterviewQuestion | null
  status: 'active' | 'completed'
  provider?: string | null
  speech_task_id?: string | null
  progress: InterviewProgress
  final_report: InterviewFinalReport | null
}

export type InterviewStreamEvent = {
  event: string
  data: Record<string, unknown>
}

function parseEvent(raw: string): InterviewStreamEvent | null {
  const lines = raw.split('\n')
  let event = 'message'
  const dataLines: string[] = []
  for (const line of lines) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    if (line.startsWith('data:')) dataLines.push(line.slice(5).trimStart())
  }
  if (!dataLines.length) return null
  try {
    const data = JSON.parse(dataLines.join('\n')) as unknown
    return data && typeof data === 'object' ? { event, data: data as Record<string, unknown> } : null
  } catch {
    return null
  }
}

export async function streamInterviewAnswer(
  sessionId: string,
  answer: string,
  token: string,
  onEvent: (event: InterviewStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const controller = new AbortController()
  const timeout = window.setTimeout(() => controller.abort(), 240_000)
  try {
    const response = await fetch(`/api/interviews/${sessionId}/answers/stream`, {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({ answer }),
      signal: signal ?? controller.signal,
    })
    if (!response.ok) {
      const payload = (await response.json().catch(() => ({}))) as { error?: { message?: string; code?: string } }
      throw new ApiError(payload.error?.message ?? '面试回答提交失败，请稍后重试', response.status, payload.error?.code)
    }
    if (!response.body) throw new ApiError('浏览器不支持流式面试响应', 502, 'stream_unavailable')
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
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('面试回答请求超时，请检查模型服务状态后重试', 408, 'request_timeout')
    }
    throw error
  } finally {
    window.clearTimeout(timeout)
  }
}
