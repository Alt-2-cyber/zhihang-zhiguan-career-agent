import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError } from '../../app/api'
import { streamAgentEvents } from './api'
import type { AgentEvent } from './types'

describe('chat SSE API', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('parses chunked authenticated events after the supplied cursor', async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('id: 8\nevent: tool.star'))
        controller.enqueue(
          encoder.encode(
            'ted\ndata: {"tool":"profile.get"}\n\n: heartbeat\n\nid: 9\nevent: answer.delta\ndata: {"content":"你好"}\n\n',
          ),
        )
        controller.close()
      },
    })
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(stream, { status: 200, headers: { 'content-type': 'text/event-stream' } }),
    )
    vi.stubGlobal('fetch', fetchMock)
    const events: AgentEvent[] = []

    await streamAgentEvents('/chat/runs/run-1/events', 'token-1', 7, (event) => events.push(event))

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/chat/runs/run-1/events?after=7',
      expect.objectContaining({ method: 'GET', headers: expect.any(Headers) }),
    )
    const headers = fetchMock.mock.calls[0][1].headers as Headers
    expect(headers.get('Authorization')).toBe('Bearer token-1')
    expect(events).toEqual([
      { sequence: 8, event_type: 'tool.started', payload: { tool: 'profile.get' } },
      { sequence: 9, event_type: 'answer.delta', payload: { content: '你好' } },
    ])
  })

  it('isolates malformed events and decodes UTF-8 split across chunks', async () => {
    const bytes = new TextEncoder().encode(
      'id: bad\nevent: answer.delta\ndata: {}\n\nid: 2\nevent: answer.delta\ndata: {bad}\n\nid: 3\nevent: answer.delta\ndata: {"content":"岗位分析"}\n\n',
    )
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(bytes.slice(0, bytes.length - 5))
        controller.enqueue(bytes.slice(bytes.length - 5))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, { status: 200 })))
    const events: AgentEvent[] = []

    await streamAgentEvents('/chat/runs/run-1/events', 'token', 0, (event) => events.push(event))

    expect(events).toEqual([
      { sequence: 3, event_type: 'answer.delta', payload: { content: '岗位分析' } },
    ])
  })

  it('decodes structured API errors before reading a stream', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { code: 'forbidden', message: '无权访问' } }), {
          status: 403,
          headers: { 'content-type': 'application/json' },
        }),
      ),
    )

    await expect(streamAgentEvents('/chat/runs/run-1/events', 'token', 0, () => undefined)).rejects.toEqual(
      new ApiError('无权访问', 403, 'forbidden'),
    )
  })
})
