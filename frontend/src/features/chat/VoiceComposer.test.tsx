import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import * as chatApi from './api'
import { AttachmentComposer } from './AttachmentComposer'
import { MessageAudioButton } from './MessageAudioButton'
import { VoiceComposer } from './VoiceComposer'

vi.mock('./api', async () => {
  const actual = await vi.importActual<typeof import('./api')>('./api')
  return {
    ...actual,
    uploadChatRecording: vi.fn(),
    uploadChatAttachment: vi.fn(),
    readAiTask: vi.fn(),
    retryAiTask: vi.fn(),
    synthesizeChatMessage: vi.fn(),
    downloadAiMedia: vi.fn(),
  }
})

class MockMediaRecorder {
  state = 'inactive'
  ondataavailable: ((event: BlobEvent) => void) | null = null
  onstop: (() => void) | null = null
  constructor(readonly stream: MediaStream) {}
  start() { this.state = 'recording' }
  stop() {
    this.state = 'inactive'
    this.ondataavailable?.({ data: new Blob(['audio'], { type: 'audio/webm' }) } as BlobEvent)
    this.onstop?.()
  }
}

function wrapper(children: React.ReactNode) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>{children}</QueryClientProvider>
}

describe('chat media controls', () => {
  beforeEach(() => {
    vi.resetAllMocks()
    vi.stubGlobal('MediaRecorder', MockMediaRecorder)
    Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:chat-audio') })
    Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() })
  })
  afterEach(cleanup)

  it('records, uploads, and applies an editable transcript', async () => {
    const stopTrack = vi.fn()
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopTrack }] }) },
    })
    vi.mocked(chatApi.uploadChatRecording).mockResolvedValue({ task_id: 'task-asr', artifact_id: 'artifact-1', status: 'queued' })
    vi.mocked(chatApi.readAiTask).mockResolvedValue({ id: 'task-asr', status: 'succeeded', result: { text: '原始转写' }, error: null })
    const onTranscript = vi.fn()
    render(wrapper(<VoiceComposer sessionId="session-1" token="token" onTranscript={onTranscript} />))

    await userEvent.click(screen.getByRole('button', { name: '开始录音' }))
    await userEvent.click(screen.getByRole('button', { name: '停止录音' }))

    await waitFor(() => expect(onTranscript).toHaveBeenCalledWith('原始转写'))
    expect(stopTrack).toHaveBeenCalled()
  })

  it('keeps text messaging available when microphone permission is denied', async () => {
    Object.defineProperty(navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockRejectedValue(new DOMException('denied', 'NotAllowedError')) },
    })
    render(wrapper(<VoiceComposer sessionId="session-1" token="token" onTranscript={vi.fn()} />))

    await userEvent.click(screen.getByRole('button', { name: '开始录音' }))

    expect(await screen.findByText('麦克风权限被拒绝，请允许访问后重试')).toBeInTheDocument()
  })

  it('marks an attachment ready only after its parse task succeeds', async () => {
    vi.mocked(chatApi.uploadChatAttachment).mockResolvedValue({ id: 'attachment-1', task_id: 'task-ocr', parse_status: 'queued', original_name: 'resume.pdf' })
    vi.mocked(chatApi.readAiTask).mockImplementation(async (taskId) => taskId === 'task-ocr'
      ? { id: 'task-ocr', status: 'succeeded', result: { embedding_task_id: 'task-embed' }, error: null }
      : { id: 'task-embed', status: 'succeeded', result: {}, error: null })
    const onReadyChange = vi.fn()
    render(wrapper(<AttachmentComposer sessionId="session-1" token="token" onReadyChange={onReadyChange} />))
    const file = new File(['%PDF'], 'resume.pdf', { type: 'application/pdf' })

    await userEvent.upload(screen.getByLabelText('添加对话附件'), file)

    expect(await screen.findByText('resume.pdf')).toBeInTheDocument()
    await waitFor(() => expect(onReadyChange).toHaveBeenLastCalledWith(['attachment-1']))
    expect(chatApi.readAiTask).toHaveBeenCalledWith('task-embed', 'token')
    expect(screen.getByText('解析完成')).toBeInTheDocument()
  })

  it('synthesizes assistant text and revokes its object URL on cleanup', async () => {
    vi.mocked(chatApi.synthesizeChatMessage).mockResolvedValue({ task_id: 'task-tts', status: 'queued' })
    vi.mocked(chatApi.readAiTask).mockResolvedValue({ id: 'task-tts', status: 'succeeded', result: { artifact_id: 'audio-1' }, error: null })
    vi.mocked(chatApi.downloadAiMedia).mockResolvedValue(new Blob(['RIFF'], { type: 'audio/wav' }))
    const rendered = render(wrapper(<MessageAudioButton messageId="message-1" token="token" />))

    await userEvent.click(screen.getByRole('button', { name: '朗读回复' }))

    expect(await screen.findByLabelText('Agent 回复语音')).toHaveAttribute('src', 'blob:chat-audio')
    rendered.unmount()
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:chat-audio')
  })
})
