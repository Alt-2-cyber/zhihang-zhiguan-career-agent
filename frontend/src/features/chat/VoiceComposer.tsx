import { useMutation, useQuery } from '@tanstack/react-query'
import { Mic, Square } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { readAiTask, uploadChatRecording } from './api'
import { useAudioRecorder } from './useAudioRecorder'

const isPending = (status?: string) => status === 'queued' || status === 'running'

export function VoiceComposer({
  sessionId,
  token,
  disabled,
  disabledReason,
  onTranscript,
}: {
  sessionId: string
  token: string
  disabled?: boolean
  disabledReason?: string
  onTranscript: (text: string) => void
}) {
  const [taskId, setTaskId] = useState<string | null>(null)
  const appliedRef = useRef<string | null>(null)
  const upload = useMutation({
    mutationFn: (blob: Blob) => uploadChatRecording(sessionId, blob, token),
    onSuccess: (result) => {
      appliedRef.current = null
      setTaskId(result.task_id)
    },
  })
  const recorder = useAudioRecorder((blob) => upload.mutate(blob))
  const task = useQuery({
    queryKey: ['ai-task', taskId],
    queryFn: () => readAiTask(taskId!, token),
    enabled: Boolean(taskId),
    refetchInterval: (query) => isPending(query.state.data?.status) ? 1_000 : false,
  })
  useEffect(() => {
    const text = task.data?.status === 'succeeded' ? task.data.result?.text : undefined
    if (taskId && text !== undefined && appliedRef.current !== taskId) {
      appliedRef.current = taskId
      onTranscript(text)
    }
  }, [onTranscript, task.data, taskId])

  const busy = disabled || upload.isPending || isPending(task.data?.status)
  const statusText = disabledReason
    ?? (recorder.recording
      ? '正在录音'
      : upload.isPending
        ? '正在上传'
        : isPending(task.data?.status)
          ? '正在转写'
          : task.data?.status === 'failed'
            ? '转写失败，可重新录音'
            : recorder.error)
  return (
    <div className="flex min-w-0 items-center gap-2">
      {recorder.recording ? (
        <button type="button" className="grid size-9 shrink-0 place-items-center rounded-lg border border-[#ff7358]/45 bg-[#fff0eb] text-[#a74747] transition hover:border-[#b24531] hover:bg-[#ffe3dc]" aria-label="停止录音" title="停止录音" onClick={recorder.stop}>
          <Square size={15} />
        </button>
      ) : (
        <button type="button" className="grid size-9 shrink-0 place-items-center rounded-lg border border-transparent bg-[#f1f6ed] text-[#526051] transition hover:border-[#9fbe74] hover:bg-[#e7f5d8] hover:text-[#102015] disabled:cursor-not-allowed disabled:opacity-50" aria-label="开始录音" title={disabledReason ?? '开始录音'} disabled={busy} onClick={() => void recorder.start()}>
          <Mic size={16} />
        </button>
      )}
      <span className="truncate text-xs text-slate-500">{statusText}</span>
    </div>
  )
}
