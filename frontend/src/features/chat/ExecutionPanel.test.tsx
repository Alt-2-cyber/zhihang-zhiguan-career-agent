import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as chatApi from './api'
import { ExecutionPanel } from './ExecutionPanel'
import type { AgentRunView } from './types'

vi.mock('./api', () => ({ readAgentRunDetails: vi.fn() }))

const run: AgentRunView = {
  runId: 'run-1',
  status: 'completed',
  lastSequence: 8,
  provider: 'zhipu:glm-4-flash',
  answer: '',
  answerMessageId: null,
  errorCode: null,
  errorMessage: null,
  steps: {
    application: { id: 'application', agent: 'application', status: 'failed', errorCode: 'application_unavailable' },
  },
  tools: {
    'tool-1': { id: 'tool-1', name: 'applications.list', stepId: 'application', status: 'succeeded' },
  },
  actions: {},
}

const details = {
  run_id: 'run-1',
  status: 'completed',
  provider: 'zhipu:glm-4-flash',
  started_at: '2026-07-15T01:00:00Z',
  completed_at: '2026-07-15T01:00:05Z',
  duration_ms: 5000,
  steps: [{
    id: 'step-db-1',
    step_key: 'application',
    agent: 'application',
    instruction: '检查本周投递状态',
    status: 'failed',
    dependencies: ['job'],
    conclusion: '发现两条投递需要跟进',
    error_code: 'application_unavailable',
    error_message: '投递服务暂时不可用',
    started_at: '2026-07-15T01:00:00Z',
    completed_at: '2026-07-15T01:00:05Z',
    duration_ms: 5000,
    tool_call_ids: ['tool-1'],
  }],
  tools: [{
    id: 'tool-1',
    step_key: 'application',
    name: 'applications.list',
    version: '1',
    risk: 'read',
    status: 'succeeded',
    arguments: { student_id: '[REDACTED]' },
    result: { count: 2, phone: '[PHONE]' },
    error_code: null,
    error_message: null,
    started_at: '2026-07-15T01:00:01Z',
    completed_at: '2026-07-15T01:00:03Z',
    duration_ms: 2000,
  }],
}

function renderPanel() {
  return render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <ExecutionPanel
        run={run}
        token="token-1"
        onConfirm={vi.fn()}
        onReject={vi.fn()}
        onUndo={vi.fn()}
        onRetry={vi.fn()}
      />
    </QueryClientProvider>,
  )
}

describe('ExecutionPanel audit details', () => {
  afterEach(cleanup)
  beforeEach(() => {
    vi.resetAllMocks()
    vi.mocked(chatApi.readAgentRunDetails).mockResolvedValue(details)
  })

  it('loads and expands a specialist Agent audit on demand', async () => {
    const user = userEvent.setup()
    renderPanel()

    expect(chatApi.readAgentRunDetails).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: '查看 application Agent 详情' }))

    expect(await screen.findByText('检查本周投递状态')).toBeInTheDocument()
    expect(screen.getByText('applications.list')).toBeInTheDocument()
    expect(screen.getByText('发现两条投递需要跟进')).toBeInTheDocument()
    expect(screen.getByText('application_unavailable')).toBeInTheDocument()
    expect(screen.getByText('投递服务暂时不可用')).toBeInTheDocument()
    expect(screen.getByText('5 秒')).toBeInTheDocument()
    expect(chatApi.readAgentRunDetails).toHaveBeenCalledWith('run-1', 'token-1')
  })

  it('expands sanitized tool arguments and results', async () => {
    const user = userEvent.setup()
    renderPanel()

    await user.click(screen.getByRole('button', { name: '查看 applications.list 工具详情' }))

    expect(await screen.findByText(/"student_id": "\[REDACTED\]"/)).toBeInTheDocument()
    expect(screen.getByText(/"phone": "\[PHONE\]"/)).toBeInTheDocument()
    expect(screen.getByText('2 秒')).toBeInTheDocument()
  })
})
