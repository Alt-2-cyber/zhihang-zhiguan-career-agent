import { useMutation, useQuery } from '@tanstack/react-query'
import { Volume2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { downloadAiMedia, readAiTask, synthesizeChatMessage } from './api'

export function MessageAudioButton({
  messageId,
  token,
  disabled,
  disabledReason,
}: {
  messageId: string
  token: string
  disabled?: boolean
  disabledReason?: string
}) {
  const [taskId, setTaskId] = useState<string | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const audioUrlRef = useRef<string | null>(null)
  const loadedRef = useRef<string | null>(null)
  const synthesize = useMutation({
    mutationFn: () => synthesizeChatMessage(messageId, token),
    onSuccess: (result) => setTaskId(result.task_id),
  })
  const task = useQuery({
    queryKey: ['ai-task', taskId],
    queryFn: () => readAiTask(taskId!, token),
    enabled: Boolean(taskId),
    refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1_000 : false,
  })
  useEffect(() => {
    const artifactId = task.data?.status === 'succeeded' ? task.data.result?.artifact_id : undefined
    if (!artifactId || loadedRef.current === artifactId) return
    let cancelled = false
    loadedRef.current = artifactId
    void downloadAiMedia(artifactId, token).then((blob) => {
      if (cancelled) return
      const next = URL.createObjectURL(blob)
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current)
      audioUrlRef.current = next
      setAudioUrl(next)
    })
    return () => { cancelled = true }
  }, [task.data, token])
  useEffect(() => () => { if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current) }, [])
  if (audioUrl) return <audio aria-label="Agent 回复语音" className="mt-2 h-8 max-w-full" controls src={audioUrl} />

  const busy = disabled || synthesize.isPending || ['queued', 'running'].includes(task.data?.status ?? '')
  return (
    <button
      type="button"
      className="mt-2 inline-flex items-center gap-1 text-xs text-slate-500 hover:text-teal-700 disabled:cursor-not-allowed disabled:opacity-50"
      aria-label="朗读回复"
      title={disabled ? disabledReason : undefined}
      disabled={busy}
      onClick={() => synthesize.mutate()}
    >
      <Volume2 size={14} />
      {disabled ? '语音未就绪' : task.data?.status === 'failed' ? '重试朗读' : '朗读'}
    </button>
  )
}
