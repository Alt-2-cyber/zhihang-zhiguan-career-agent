import { describe, expect, it } from 'vitest'

import { createRunView, reduceActionStatus, reduceAgentEvent } from './useAgentRun'

describe('Agent run event reducer', () => {
  it('ignores duplicate sequences and merges step, tool, and answer progress', () => {
    let state = createRunView('run-1')
    state = reduceAgentEvent(state, {
      sequence: 1,
      event_type: 'step.started',
      payload: { step_id: 'job', agent: 'job' },
    })
    state = reduceAgentEvent(state, {
      sequence: 2,
      event_type: 'tool.started',
      payload: { tool_call_id: 'tool-1', tool: 'jobs.get', step_id: 'job' },
    })
    state = reduceAgentEvent(state, {
      sequence: 3,
      event_type: 'answer.delta',
      payload: { content: '匹配度较高' },
    })
    state = reduceAgentEvent(state, {
      sequence: 3,
      event_type: 'answer.delta',
      payload: { content: '不应重复' },
    })

    expect(state.lastSequence).toBe(3)
    expect(state.steps.job.status).toBe('running')
    expect(state.tools['tool-1'].name).toBe('jobs.get')
    expect(state.answer).toBe('匹配度较高')
  })

  it('records pending actions and terminal run state', () => {
    let state = createRunView('run-1')
    state = reduceAgentEvent(state, {
      sequence: 1,
      event_type: 'tool.awaiting_confirmation',
      payload: {
        tool_call_id: 'tool-1',
        proposal_id: 'proposal-1',
        tool: 'plan.task.create',
        status: 'pending_confirmation',
      },
    })
    state = reduceAgentEvent(state, {
      sequence: 2,
      event_type: 'run.completed',
      payload: { provider: 'local-rules', message_id: 'assistant-1' },
    })

    expect(state.actions['proposal-1'].status).toBe('pending')
    expect(state.status).toBe('completed')
    expect(state.provider).toBe('local-rules')
    expect(state.answerMessageId).toBe('assistant-1')
  })

  it('replaces the streamed draft with the validated final answer', () => {
    let state = createRunView('run-1')
    state = reduceAgentEvent(state, {
      sequence: 1,
      event_type: 'answer.delta',
      payload: { content: '正在生成的草稿' },
    })
    state = reduceAgentEvent(state, {
      sequence: 2,
      event_type: 'answer.replace',
      payload: { content: '完整的最终答案' },
    })

    expect(state.answer).toBe('完整的最终答案')
  })

  it('clears a stale failure if a later completion event is replayed', () => {
    let state = createRunView('run-1')
    state = reduceAgentEvent(state, {
      sequence: 1,
      event_type: 'run.failed',
      payload: { error_code: 'agent_run_stale', message: 'timeout' },
    })
    state = reduceAgentEvent(state, {
      sequence: 2,
      event_type: 'run.completed',
      payload: { provider: 'zhipu:glm-4-flash', message_id: 'assistant-1' },
    })

    expect(state.status).toBe('completed')
    expect(state.errorCode).toBeNull()
    expect(state.errorMessage).toBeNull()
  })

  it('updates an action after the user confirms it', () => {
    let state = createRunView('run-1')
    state = reduceAgentEvent(state, {
      sequence: 1,
      event_type: 'tool.awaiting_confirmation',
      payload: { tool_call_id: 'tool-1', proposal_id: 'proposal-1', tool: 'plan.task.create' },
    })

    state = reduceActionStatus(state, 'proposal-1', 'succeeded')

    expect(state.actions['proposal-1'].status).toBe('succeeded')
  })
})
