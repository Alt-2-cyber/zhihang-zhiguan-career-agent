import { useMutation, useQuery } from '@tanstack/react-query'
import { FileText, Paperclip, RefreshCw, X } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { readAiTask, retryAiTask, uploadChatAttachment } from './api'

type Item = { id: string; taskId: string; name: string; status: 'queued' | 'running' | 'ready' | 'failed' }

function AttachmentItem({
  item,
  token,
  onStatus,
  onTaskId,
  onRemove,
}: {
  item: Item
  token: string
  onStatus: (status: Item['status']) => void
  onTaskId: (taskId: string) => void
  onRemove: () => void
}) {
  const onStatusRef = useRef(onStatus)
  onStatusRef.current = onStatus
  const onTaskIdRef = useRef(onTaskId)
  onTaskIdRef.current = onTaskId
  const task = useQuery({
    queryKey: ['ai-task', item.taskId],
    queryFn: () => readAiTask(item.taskId, token),
    enabled: item.status !== 'ready',
    refetchInterval: (query) => ['queued', 'running'].includes(query.state.data?.status ?? '') ? 1_000 : false,
  })
  const retry = useMutation({
    mutationFn: () => retryAiTask(item.taskId, token),
    onSuccess: () => {
      onStatus('queued')
      void task.refetch()
    },
  })
  useEffect(() => {
    const embeddingTaskId = task.data?.result?.embedding_task_id
    if (task.data?.status === 'succeeded' && typeof embeddingTaskId === 'string') {
      onTaskIdRef.current(embeddingTaskId)
    } else if (task.data?.status === 'succeeded') onStatusRef.current('ready')
    if (task.data?.status === 'failed') onStatusRef.current('failed')
    if (task.data?.status === 'running') onStatusRef.current('running')
  }, [task.data?.result?.embedding_task_id, task.data?.status])
  return (
    <div className="flex min-w-0 items-center gap-2 rounded-md bg-slate-100 px-2 py-1.5 text-xs">
      <FileText className="shrink-0 text-slate-500" size={14} />
      <span className="min-w-0 flex-1 truncate">{item.name}</span>
      <span className={item.status === 'failed' ? 'text-red-700' : item.status === 'ready' ? 'text-emerald-700' : 'text-amber-700'}>
        {item.status === 'ready' ? '解析完成' : item.status === 'failed' ? '解析失败' : '处理中'}
      </span>
      {item.status === 'failed' ? (
        <button type="button" aria-label={`重试${item.name}`} title="重试" onClick={() => retry.mutate()}>
          <RefreshCw size={14} />
        </button>
      ) : null}
      <button type="button" aria-label={`移除${item.name}`} title="移除" onClick={onRemove}>
        <X size={14} />
      </button>
    </div>
  )
}

export function AttachmentComposer({
  sessionId,
  token,
  disabled,
  disabledReason,
  onReadyChange,
  onBusyChange,
}: {
  sessionId: string
  token: string
  disabled?: boolean
  disabledReason?: string
  onReadyChange: (ids: string[]) => void
  onBusyChange?: (busy: boolean) => void
}) {
  const [items, setItems] = useState<Item[]>([])
  const upload = useMutation({
    mutationFn: (file: File) => uploadChatAttachment(sessionId, file, token),
    onSuccess: (result) => setItems((current) => [
      ...current,
      { id: result.id, taskId: result.task_id, name: result.original_name, status: 'queued' },
    ]),
  })
  useEffect(() => onReadyChange(items.filter((item) => item.status === 'ready').map((item) => item.id)), [items, onReadyChange])
  useEffect(() => onBusyChange?.(upload.isPending || items.some((item) => item.status !== 'ready')), [items, onBusyChange, upload.isPending])
  const updateStatus = (id: string, status: Item['status']) => setItems((current) => current.map((item) => item.id === id && item.status !== status ? { ...item, status } : item))
  const updateTaskId = (id: string, taskId: string) => setItems((current) => current.map((item) => item.id === id && item.taskId !== taskId ? { ...item, taskId, status: 'queued' } : item))
  return (
    <div className="min-w-0">
      <label
        className={`grid size-9 cursor-pointer place-items-center rounded-lg border border-transparent bg-[#f1f6ed] text-[#526051] transition hover:border-[#9fbe74] hover:bg-[#e7f5d8] hover:text-[#102015] ${disabled || upload.isPending ? 'pointer-events-none opacity-50' : ''}`}
        title={disabled ? disabledReason : '添加附件'}
      >
        <span className="sr-only">添加对话附件</span>
        <Paperclip size={16} />
        <input
          aria-label="添加对话附件"
          type="file"
          accept=".pdf,.docx,.txt"
          className="sr-only"
          disabled={disabled || upload.isPending}
          onChange={(event) => {
            const file = event.target.files?.[0]
            if (file) upload.mutate(file)
            event.target.value = ''
          }}
        />
      </label>
      {items.length ? (
        <div className="absolute bottom-full left-0 mb-2 w-[min(80vw,420px)] space-y-1 border border-slate-200 bg-white p-2 shadow-lg">
          {items.map((item) => (
            <AttachmentItem
              key={item.id}
              item={item}
              token={token}
              onStatus={(status) => updateStatus(item.id, status)}
              onTaskId={(taskId) => updateTaskId(item.id, taskId)}
              onRemove={() => setItems((current) => current.filter((candidate) => candidate.id !== item.id))}
            />
          ))}
        </div>
      ) : null}
    </div>
  )
}
