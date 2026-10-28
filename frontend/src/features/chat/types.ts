export type ChatRole = 'student' | 'counselor' | 'admin'
export type ChatMode = 'confirm' | 'auto'
export type ChatSessionStatus = 'active' | 'archived'

export type ChatSession = {
  id: string
  owner_id: string
  role: ChatRole
  subject_student_id: string | null
  mode: ChatMode
  title: string
  summary: string | null
  summary_source_message_ids?: string[]
  status: ChatSessionStatus
  created_at: string
  updated_at: string
}

export type Citation = {
  label?: string
  title?: string
  url?: string
  source?: string
  excerpt?: string
  [key: string]: unknown
}

export type ChatMessage = {
  id: string
  sender: 'user' | 'assistant' | 'tool'
  content: string
  attachment_ids: string[]
  citations: Citation[]
  provider?: string | null
  created_at: string
  optimistic?: boolean
}

export type ActiveAgentRun = {
  run_id: string
  status: 'queued' | 'running'
  events_url: string
  user_message_id: string
  error_code?: string | null
  created_at: string
  started_at?: string | null
}

export type ChatSessionDetail = ChatSession & {
  messages: ChatMessage[]
  active_run?: ActiveAgentRun | null
}
export type ChatSessionPage = { items: ChatSession[]; next_cursor: string | null }

export type AgentRunAccepted = {
  message_id: string
  run_id: string
  events_url: string
  status: 'queued'
}

export type AgentEventType =
  | 'run.queued'
  | 'run.started'
  | 'run.completed'
  | 'run.failed'
  | 'run.cancelled'
  | 'step.started'
  | 'step.succeeded'
  | 'step.failed'
  | 'tool.started'
  | 'tool.succeeded'
  | 'tool.failed'
  | 'tool.awaiting_confirmation'
  | 'answer.delta'
  | 'answer.reset'
  | 'answer.replace'
  | 'answer.completed'

export type AgentEvent = {
  sequence: number
  event_type: AgentEventType | (string & {})
  payload: Record<string, unknown>
}

export type AgentStepView = {
  id: string
  agent: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  errorCode?: string
}

export type ToolCallView = {
  id: string
  name: string
  stepId?: string
  status: 'running' | 'succeeded' | 'failed' | 'waiting_confirmation'
  errorCode?: string
}

export type ActionStatus = 'pending' | 'executing' | 'succeeded' | 'failed' | 'rejected' | 'expired' | 'undone'

export type ActionProposalView = {
  id: string
  toolCallId: string
  tool: string
  title: string
  risk: string
  status: ActionStatus
}

export type AgentRunView = {
  runId: string
  status: 'idle' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  lastSequence: number
  provider: string | null
  answer: string
  answerMessageId: string | null
  errorCode: string | null
  errorMessage: string | null
  steps: Record<string, AgentStepView>
  tools: Record<string, ToolCallView>
  actions: Record<string, ActionProposalView>
}

export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue }

export type AgentStepDetail = {
  id: string
  step_key: string
  agent: string
  instruction: string
  status: string
  dependencies: string[]
  conclusion: string | null
  error_code: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  tool_call_ids: string[]
}

export type ToolCallDetail = {
  id: string
  step_key: string | null
  name: string
  version: string
  risk: string
  status: string
  arguments: { [key: string]: JsonValue }
  result: JsonValue
  error_code: string | null
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
}

export type AgentRunDetails = {
  run_id: string
  status: string
  provider: string
  started_at: string | null
  completed_at: string | null
  duration_ms: number | null
  steps: AgentStepDetail[]
  tools: ToolCallDetail[]
}

export type ActionOutcome = {
  status: string
  tool_call_id: string
  proposal_id: string
  result?: Record<string, unknown> | null
}

export type ChatContextRef = {
  type:
    | 'student'
    | 'profile'
    | 'plan'
    | 'task'
    | 'job'
    | 'resume'
    | 'application'
    | 'intervention'
    | 'learning_task'
    | 'workplace_session'
    | 'job_intelligence'
    | 'employment_record'
    | 'quality_feedback'
  id: string
}

export type AITask = {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  result?: { text?: string; artifact_id?: string; [key: string]: unknown }
  error?: { code?: string; message?: string } | null
}

export type ChatAttachmentUpload = {
  id: string
  task_id: string
  parse_status: string
  original_name: string
}

export type AiProviderStatus = {
  name: string
  model: string
  configured: boolean
}

export type AiCapabilityService = {
  ready: boolean
  model?: string
  asr_model?: string
  tts_model?: string
  privacy?: string
}

export type AiCapabilities = {
  deployment_mode?: 'full' | 'server-demo'
  agent: {
    mode: string
    strict_online: boolean
    local_fallback_enabled: boolean
    providers: AiProviderStatus[]
  }
  services: {
    embedding: AiCapabilityService
    ocr: AiCapabilityService
    speech: AiCapabilityService
    emotion?: AiCapabilityService
  }
  features?: {
    online_agent: boolean
    resume_text_extraction: boolean
    pdf_ocr: boolean
    semantic_search: boolean
    speech_transcription: boolean
    speech_synthesis: boolean
    camera_emotion: boolean
    chat_attachments: boolean
    public_job_search: boolean
  }
  limitations?: string[]
}
