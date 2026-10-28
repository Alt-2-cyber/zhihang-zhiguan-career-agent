import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as chatApi from './api'
import { ChatPage } from './ChatPage'

vi.mock('./api', () => ({
  listChatSessions: vi.fn(),
  readChatSession: vi.fn(),
  createChatSession: vi.fn(),
  updateChatSession: vi.fn(),
  postChatMessage: vi.fn(),
  readAiCapabilities: vi.fn(),
  readAgentRunDetails: vi.fn(),
  streamAgentEvents: vi.fn(),
  confirmChatAction: vi.fn(),
  rejectChatAction: vi.fn(),
  retryAgentRun: vi.fn(),
  undoChatAction: vi.fn(),
  uploadChatRecording: vi.fn(),
  uploadChatAttachment: vi.fn(),
  readAiTask: vi.fn(),
  retryAiTask: vi.fn(),
  synthesizeChatMessage: vi.fn(),
  downloadAiMedia: vi.fn(),
}))

const session = {
  id: 'session-1',
  owner_id: 'student-1',
  role: 'student' as const,
  subject_student_id: 'student-1',
  mode: 'confirm' as const,
  title: '后端岗位规划',
  summary: null,
  status: 'active' as const,
  created_at: '2026-07-15T00:00:00Z',
  updated_at: '2026-07-15T00:00:00Z',
}

function renderPage(context?: { type: 'job' | 'student'; id: string }, role: 'student' | 'counselor' = 'student') {
  return render(
    <MemoryRouter initialEntries={[context ? { pathname: `/${role}/assistant`, state: { context } } : `/${role}/assistant`]}>
      <QueryClientProvider
        client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}
      >
        <ChatPage token="token-1" role={role} />
      </QueryClientProvider>
    </MemoryRouter>,
  )
}

describe('ChatPage', () => {
  afterEach(cleanup)
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(chatApi.listChatSessions).mockResolvedValue({ items: [session], next_cursor: null })
    vi.mocked(chatApi.readAiCapabilities).mockResolvedValue({
      agent: {
        mode: 'failover',
        strict_online: true,
        local_fallback_enabled: false,
        providers: [
          { name: 'deepseek', model: 'deepseek-v4-flash', configured: true },
          { name: 'zhipu', model: 'glm-4-flash', configured: true },
        ],
      },
      services: {
        embedding: { model: 'BAAI/bge-m3', ready: true },
        ocr: { model: 'PP-OCRv5', ready: true },
        speech: { asr_model: 'paraformer-zh', tts_model: 'MeloTTS-ZH', ready: true },
      },
    })
    vi.mocked(chatApi.readChatSession).mockResolvedValue({
      ...session,
      messages: [{ id: 'message-1', sender: 'assistant', content: '你好，我是就业助手', citations: [], attachment_ids: [], provider: 'local-rules', created_at: session.created_at }],
    })
    vi.mocked(chatApi.updateChatSession).mockResolvedValue({ ...session, mode: 'auto' })
    vi.mocked(chatApi.postChatMessage).mockResolvedValue({
      message_id: 'message-2',
      run_id: 'run-1',
      events_url: '/chat/runs/run-1/events',
      status: 'queued',
    })
    vi.mocked(chatApi.streamAgentEvents).mockImplementation(async (_path, _token, _after, onEvent) => {
      onEvent({ sequence: 1, event_type: 'step.started', payload: { agent: 'job', step_id: 'job' } })
      onEvent({ sequence: 2, event_type: 'tool.started', payload: { tool: 'jobs.get', tool_call_id: 'tool-1' } })
      onEvent({ sequence: 3, event_type: 'answer.delta', payload: { content: '岗位匹配度较高' } })
      onEvent({ sequence: 4, event_type: 'run.completed', payload: { message_id: 'message-3' } })
    })
  })

  it('shows sessions, switches permission mode, and streams an Agent run', async () => {
    const user = userEvent.setup()
    renderPage()

    expect(await screen.findByText('后端岗位规划')).toBeInTheDocument()
    expect(await screen.findByText('你好，我是就业助手')).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('执行权限'), 'auto')
    await waitFor(() => expect(chatApi.updateChatSession).toHaveBeenCalledWith('session-1', { mode: 'auto' }, 'token-1'))

    await user.type(screen.getByLabelText('发送给就业助手'), '分析当前岗位')
    await user.click(screen.getByRole('button', { name: '发送消息' }))

    expect(await screen.findByText('岗位匹配度较高')).toBeInTheDocument()
    expect(screen.getByText('job')).toBeInTheDocument()
    expect(screen.getByText('jobs.get')).toBeInTheDocument()
  })

  it('reconciles optimistic and streamed messages after the session refreshes', async () => {
    const persistedMessages = [
      { id: 'message-1', sender: 'assistant' as const, content: '你好，我是就业助手', citations: [], attachment_ids: [], provider: 'local-rules', created_at: session.created_at },
      { id: 'message-2', sender: 'user' as const, content: '分析当前岗位', citations: [], attachment_ids: [], provider: null, created_at: session.updated_at },
      { id: 'message-3', sender: 'assistant' as const, content: '岗位匹配度较高', citations: [], attachment_ids: [], provider: 'zhipu:glm-4-flash', created_at: session.updated_at },
    ]
    let reads = 0
    vi.mocked(chatApi.readChatSession).mockImplementation(async () => ({
      ...session,
      messages: reads++ === 0 ? [persistedMessages[0]] : persistedMessages,
    }))
    const user = userEvent.setup()
    renderPage()

    await user.type(await screen.findByLabelText('发送给就业助手'), '分析当前岗位')
    await user.click(screen.getByRole('button', { name: '发送消息' }))

    await waitFor(() => expect(chatApi.readChatSession).toHaveBeenCalledTimes(2))
    await waitFor(() => {
      expect(screen.getAllByText('分析当前岗位')).toHaveLength(1)
      expect(screen.getAllByText('岗位匹配度较高')).toHaveLength(1)
    })
  })

  it('renders the real citation label as a link', async () => {
    vi.mocked(chatApi.readChatSession).mockResolvedValue({
      ...session,
      messages: [{
        id: 'message-cited',
        sender: 'assistant',
        content: '综合建议\n\n已找到岗位资料\n\n参考资源\n1. 国家大学生就业服务平台：公开岗位信息',
        citations: [{ label: '国家大学生就业服务平台', excerpt: '公开岗位信息', url: 'https://example.test/jobs' }],
        attachment_ids: [],
        provider: 'zhipu:glm-4-flash',
        created_at: session.created_at,
      }],
    })

    renderPage()

    const citation = await screen.findByRole('link', { name: '国家大学生就业服务平台' })
    expect(screen.getByRole('heading', { name: '综合建议' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: '参考资源' })).toBeInTheDocument()
    expect(citation).toHaveAttribute('href', 'https://example.test/jobs')
    expect(screen.queryByText('业务数据')).not.toBeInTheDocument()
  })

  it('shows a launch context and sends only its typed reference', async () => {
    const user = userEvent.setup()
    renderPage({ type: 'job', id: 'job-1' })

    expect(await screen.findByText('岗位：job-1')).toBeInTheDocument()
    await user.type(await screen.findByLabelText('发送给就业助手'), '比较这个岗位')
    await user.click(screen.getByRole('button', { name: '发送消息' }))

    await waitFor(() => expect(chatApi.postChatMessage).toHaveBeenCalledWith(
      'session-1',
      { content: '比较这个岗位', attachment_ids: [], context_refs: [{ type: 'job', id: 'job-1' }] },
      'token-1',
      expect.any(String),
    ))
  })

  it('creates a student-scoped counselor session for a student launch context', async () => {
    const counselorSession = {
      ...session,
      id: 'session-counselor',
      owner_id: 'counselor-1',
      role: 'counselor' as const,
      subject_student_id: 'student-2',
      title: '学生帮扶对话',
    }
    vi.mocked(chatApi.createChatSession).mockResolvedValue(counselorSession)
    vi.mocked(chatApi.readChatSession).mockImplementation(async (id) => ({
      ...(id === counselorSession.id ? counselorSession : session),
      messages: [],
    }))

    renderPage({ type: 'student', id: 'student-2' }, 'counselor')

    await waitFor(() => expect(chatApi.createChatSession).toHaveBeenCalledWith(
      { title: '学生帮扶对话', mode: 'confirm', subject_student_id: 'student-2' },
      'token-1',
    ))
    expect(await screen.findByText('学生帮扶对话')).toBeInTheDocument()
    expect(screen.getByText('当前会话范围：指定学生')).toBeInTheDocument()
  })
})
