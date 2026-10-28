import { useCallback, useEffect, useState } from 'react'

import { streamAgentEvents } from './api'
import type { ActionProposalView, ActionStatus, AgentEvent, AgentRunView, AgentStepView, ToolCallView } from './types'

const terminalEvents = new Set(['run.completed', 'run.failed', 'run.cancelled'])

function text(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

export function createRunView(runId = ''): AgentRunView {
  return {
    runId,
    status: runId ? 'queued' : 'idle',
    lastSequence: 0,
    provider: null,
    answer: '',
    answerMessageId: null,
    errorCode: null,
    errorMessage: null,
    steps: {},
    tools: {},
    actions: {},
  }
}

export function reduceAgentEvent(state: AgentRunView, event: AgentEvent): AgentRunView {
  if (event.sequence <= state.lastSequence) return state
  const next: AgentRunView = { ...state, lastSequence: event.sequence }
  const payload = event.payload

  if (event.event_type === 'run.started') next.status = 'running'
  if (event.event_type === 'run.completed') {
    next.status = 'completed'
    next.answerMessageId = text(payload.message_id) || null
    next.errorCode = null
    next.errorMessage = null
  }
  if (event.event_type === 'run.failed') {
    next.status = 'failed'
    next.errorCode = text(payload.error_code, 'agent_run_failed')
    next.errorMessage = text(payload.message) || null
  }
  if (event.event_type === 'run.cancelled') next.status = 'cancelled'
  if (typeof payload.provider === 'string') next.provider = payload.provider
  if (event.event_type === 'answer.delta') next.answer += text(payload.content)
  if (event.event_type === 'answer.reset') next.answer = ''
  if (event.event_type === 'answer.replace') next.answer = text(payload.content)

  if (event.event_type.startsWith('step.')) {
    const id = text(payload.step_id)
    if (id) {
      const previous = state.steps[id]
      const status = event.event_type.endsWith('started')
        ? 'running'
        : event.event_type.endsWith('succeeded')
          ? 'succeeded'
          : 'failed'
      const step: AgentStepView = {
        id,
        agent: text(payload.agent, previous?.agent ?? id),
        status,
        errorCode: text(payload.error_code) || previous?.errorCode,
      }
      next.steps = { ...state.steps, [id]: step }
    }
  }

  if (event.event_type.startsWith('tool.')) {
    const id = text(payload.tool_call_id)
    if (id) {
      const previous = state.tools[id]
      const status = event.event_type === 'tool.started'
        ? 'running'
        : event.event_type === 'tool.succeeded'
          ? 'succeeded'
          : event.event_type === 'tool.awaiting_confirmation'
            ? 'waiting_confirmation'
            : 'failed'
      const tool: ToolCallView = {
        id,
        name: text(payload.tool, previous?.name ?? '工具调用'),
        stepId: text(payload.step_id) || previous?.stepId,
        status,
        errorCode: text(payload.error_code) || previous?.errorCode,
      }
      next.tools = { ...state.tools, [id]: tool }
    }
  }

  if (event.event_type === 'tool.awaiting_confirmation') {
    const id = text(payload.proposal_id)
    if (id) {
      const action: ActionProposalView = {
        id,
        toolCallId: text(payload.tool_call_id),
        tool: text(payload.tool, '业务操作'),
        title: text(payload.title, 'Agent 建议执行此操作'),
        risk: text(payload.risk, 'write'),
        status: 'pending',
      }
      next.actions = { ...state.actions, [id]: action }
    }
  }
  return next
}

export function reduceActionStatus(state: AgentRunView, proposalId: string, status: ActionStatus): AgentRunView {
  const action = state.actions[proposalId]
  if (!action) return state
  return {
    ...state,
    actions: { ...state.actions, [proposalId]: { ...action, status } },
  }
}

type UseAgentRunOptions = {
  runId: string | null
  eventsUrl: string | null
  token: string
  onTerminal?: () => void
}

export function useAgentRun({ runId, eventsUrl, token, onTerminal }: UseAgentRunOptions) {
  const [view, setView] = useState<AgentRunView>(() => createRunView())

  useEffect(() => {
    setView(createRunView(runId ?? ''))
    if (!runId || !eventsUrl) return
    const controller = new AbortController()
    let stopped = false

    void (async () => {
      let cursor = 0
      for (let attempt = 0; !stopped; attempt += 1) {
        let terminal = false
        try {
          await streamAgentEvents(
            eventsUrl,
            token,
            cursor,
            (event) => {
              if (event.sequence <= cursor) return
              cursor = event.sequence
              terminal = terminalEvents.has(event.event_type)
              setView((current) => reduceAgentEvent(current, event))
            },
            controller.signal,
          )
          if (terminal) {
            onTerminal?.()
            return
          }
        } catch {
          if (controller.signal.aborted) return
          if (attempt >= 4) {
            setView((current) => ({
              ...current,
              status: 'failed',
              errorCode: 'stream_disconnected',
              errorMessage: '事件流连接中断，请刷新后重试。',
            }))
            return
          }
        }
        const delay = Math.min(8, 2 ** Math.min(attempt, 3)) * 1000
        await new Promise<void>((resolve) => window.setTimeout(resolve, delay))
      }
    })()

    return () => {
      stopped = true
      controller.abort()
    }
  }, [eventsUrl, onTerminal, runId, token])

  const setActionStatus = useCallback((proposalId: string, status: ActionStatus) => {
    setView((current) => reduceActionStatus(current, proposalId, status))
  }, [])

  return { view, setActionStatus }
}
