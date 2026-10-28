import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Aperture, History, ListTree, X } from 'lucide-react'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'

import { ApiError } from '../../app/api'
import { EmptyState, LoadingState } from '../../components/Ui'
import {
  confirmChatAction,
  createChatSession,
  listChatSessions,
  postChatMessage,
  readAiCapabilities,
  readChatSession,
  rejectChatAction,
  retryAgentRun,
  undoChatAction,
  updateChatSession,
} from './api'
import { AiServiceStatus } from './AiServiceStatus'
import { Conversation } from './Conversation'
import { ExecutionPanel } from './ExecutionPanel'
import { SessionList } from './SessionList'
import type { ActionProposalView, ActionStatus, ChatContextRef, ChatMessage, ChatRole, ChatSession } from './types'
import { useAgentRun } from './useAgentRun'

function requestId() {
  return typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : `chat-${Date.now()}-${Math.random()}`
}

function submitErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === 'chat_run_active') return '上一条消息仍在处理中，请等待完成；如果超过 2 分钟，刷新后系统会自动释放卡住的任务。'
    if (error.code === 'request_timeout') return '发送请求超时，请检查后端服务是否正常运行。'
    if (error.code === 'chat_attachment_not_ready') return '附件还没有解析完成，请等解析完成后再发送。'
    return error.message
  }
  return '发送失败，请检查后端服务或稍后重试。'
}

export function ChatPage({ token, role }: { token: string; role: ChatRole }) {
  const location = useLocation()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const [attachmentIds, setAttachmentIds] = useState<string[]>([])
  const [attachmentBusy, setAttachmentBusy] = useState(false)
  const [composerVersion, setComposerVersion] = useState(0)
  const [optimistic, setOptimistic] = useState<ChatMessage[]>([])
  const [activeRun, setActiveRun] = useState<{ id: string; eventsUrl: string } | null>(null)
  const [sendError, setSendError] = useState<string | null>(null)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [executionOpen, setExecutionOpen] = useState(false)
  const scopedContextRef = useRef<string | null>(null)
  const context = useMemo<ChatContextRef | null>(() => {
    const candidate = (location.state as { context?: unknown } | null)?.context
    if (!candidate || typeof candidate !== 'object') return null
    const value = candidate as Partial<ChatContextRef>
    const allowed = new Set([
      'student',
      'profile',
      'plan',
      'task',
      'job',
      'resume',
      'application',
      'intervention',
      'learning_task',
      'workplace_session',
      'job_intelligence',
      'employment_record',
      'quality_feedback',
    ])
    return typeof value.id === 'string' && typeof value.type === 'string' && allowed.has(value.type)
      ? value as ChatContextRef
      : null
  }, [location.state])
  const contextLabel = context
    ? context.type === 'student'
      ? '学生记录'
      : `${({
          profile: '画像',
          plan: '计划',
          task: '任务',
          job: '岗位',
          resume: '简历',
          application: '投递',
          intervention: '帮扶',
          learning_task: '学习任务',
          workplace_session: '职场训练',
          job_intelligence: '岗位情报',
          employment_record: '就业记录',
          quality_feedback: '就业质量',
        } as const)[context.type]}：${context.id}`
    : null

  const sessionsQuery = useQuery({
    queryKey: ['chat-sessions', search],
    queryFn: () => listChatSessions(token, search),
  })
  const capabilitiesQuery = useQuery({
    queryKey: ['ai-capabilities'],
    queryFn: () => readAiCapabilities(token),
    refetchInterval: 15_000,
  })
  const sessions = sessionsQuery.data?.items ?? []
  useEffect(() => {
    if (!selectedId && sessions.length) setSelectedId(sessions[0].id)
  }, [selectedId, sessions])
  useEffect(() => {
    if (role === 'student' || context?.type !== 'student' || sessionsQuery.isLoading) return
    const key = `${role}:${context.id}`
    if (scopedContextRef.current === key) return
    const existing = sessions.find((item) => item.status === 'active' && item.subject_student_id === context.id)
    scopedContextRef.current = key
    if (existing) {
      setSelectedId(existing.id)
      setOptimistic([])
      setActiveRun(null)
      return
    }
    let cancelled = false
    void createChatSession(
      { title: '学生帮扶对话', mode: 'confirm', subject_student_id: context.id },
      token,
    ).then((created) => {
      if (cancelled) return
      setSelectedId(created.id)
      setOptimistic([])
      setActiveRun(null)
      void queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    }).catch(() => {
      if (!cancelled) scopedContextRef.current = null
    })
    return () => { cancelled = true }
  }, [context, queryClient, role, sessions, sessionsQuery.isLoading, token])

  const sessionQuery = useQuery({
    queryKey: ['chat-session', selectedId],
    queryFn: () => readChatSession(selectedId!, token),
    enabled: Boolean(selectedId),
  })
  const selected = sessionQuery.data
  useEffect(() => {
    const active = selected?.active_run
    if (!active) return
    if (activeRun?.id === active.run_id) return
    setActiveRun({ id: active.run_id, eventsUrl: active.events_url })
  }, [activeRun?.id, selected?.active_run])
  const invalidateSelected = useCallback(() => {
    if (selectedId) void queryClient.invalidateQueries({ queryKey: ['chat-session', selectedId] })
    void queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
  }, [queryClient, selectedId])
  const { view: run, setActionStatus } = useAgentRun({ runId: activeRun?.id ?? null, eventsUrl: activeRun?.eventsUrl ?? null, token, onTerminal: invalidateSelected })
  const runBusy = run.status === 'queued' || run.status === 'running'
  const composerDisabled = !selected || selected.status !== 'active' || attachmentBusy || runBusy
  const disabledReason = runBusy
    ? '上一条消息仍在处理中，请等待 Agent 完成后再发送。'
    : attachmentBusy
      ? '附件正在解析，完成后即可发送。'
      : !selected
        ? '会话正在加载，请稍后再发送。'
      : selected?.status !== 'active'
        ? '当前会话已归档，不能继续发送。'
        : null

  const createMutation = useMutation({
    mutationFn: () => createChatSession({ title: '新对话', mode: 'confirm' }, token),
    onSuccess: (created) => {
      setSelectedId(created.id)
      setOptimistic([])
      void queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    },
  })
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: Parameters<typeof updateChatSession>[1] }) => updateChatSession(id, payload, token),
    onSuccess: (updated) => {
      queryClient.setQueryData(['chat-session', updated.id], (current: object | undefined) => current ? { ...current, ...updated } : current)
      void queryClient.invalidateQueries({ queryKey: ['chat-sessions'] })
    },
  })
  const actionMutation = useMutation({
    mutationFn: ({ type, action }: { type: 'confirm' | 'reject' | 'undo'; action: ActionProposalView }) => {
      if (type === 'confirm') return confirmChatAction(action.id, token)
      if (type === 'reject') return rejectChatAction(action.id, token)
      return undoChatAction(action.id, token)
    },
    onSuccess: (outcome, variables) => {
      const status = outcome.status === 'pending_confirmation' ? 'pending' : outcome.status
      setActionStatus(variables.action.id, status as ActionStatus)
      invalidateSelected()
    },
  })

  const submit = async () => {
    const content = draft.trim()
    if (!content || !selectedId) return
    if (composerDisabled) {
      setSendError(disabledReason ?? '当前暂时不能发送，请稍后重试。')
      return
    }
    setSendError(null)
    const optimisticId = `optimistic-${requestId()}`
    setDraft('')
    setOptimistic((items) => [...items, {
      id: optimisticId,
      sender: 'user',
      content,
      attachment_ids: [],
      citations: [],
      created_at: new Date().toISOString(),
      optimistic: true,
    }])
    try {
      const accepted = await postChatMessage(selectedId, { content, attachment_ids: attachmentIds, context_refs: context ? [context] : [] }, token, requestId())
      setOptimistic((items) => items.map((item) => item.id === optimisticId
        ? { ...item, id: accepted.message_id }
        : item))
      setActiveRun({ id: accepted.run_id, eventsUrl: accepted.events_url })
      setAttachmentIds([])
      setComposerVersion((version) => version + 1)
    } catch (error) {
      setSendError(submitErrorMessage(error))
      setDraft(content)
      setOptimistic((items) => items.filter((item) => item.id !== optimisticId))
    }
  }

  const visibleMessages = useMemo(() => {
    const persisted = selected?.messages ?? []
    const persistedIds = new Set(persisted.map((message) => message.id))
    return [...persisted, ...optimistic.filter((message) => !persistedIds.has(message.id))]
  }, [optimistic, selected?.messages])
  const switchSession = (id: string) => {
    setSelectedId(id)
    setOptimistic([])
    setAttachmentIds([])
    setAttachmentBusy(false)
    setComposerVersion((version) => version + 1)
    setActiveRun(null)
    setSendError(null)
    setHistoryOpen(false)
  }
  const retry = async () => {
    if (!activeRun) return
    await retryAgentRun(activeRun.id, token)
    setActiveRun({ ...activeRun })
  }

  if (sessionsQuery.isLoading) return <LoadingState />
  if (sessionsQuery.isError) return <EmptyState title="就业助手暂不可用" description="会话列表加载失败，请稍后重试。" />

  return (
    <div className="-mx-4 -my-7 flex h-[calc(100vh-4rem)] min-h-[560px] flex-col border-y border-[#102015] bg-[#e9eee5] shadow-[8px_8px_0_rgba(16,32,21,0.14)] lg:-mx-9 lg:-my-9">
      <header className="flex h-[88px] shrink-0 items-center gap-3 border-b border-[#243c2b] bg-[#102015] px-4 text-white shadow-[inset_0_-1px_0_rgba(199,255,76,0.18)] sm:px-6">
        <button type="button" className="grid size-10 place-items-center rounded-md border border-white/25 text-white hover:border-[#c7ff4c] hover:bg-[#c7ff4c] hover:text-[#102015] lg:hidden" aria-label="打开对话历史" onClick={() => setHistoryOpen(true)}><History size={18} /></button>
        <span className="hidden size-10 shrink-0 place-items-center rounded-md bg-[#c7ff4c] text-[#102015] shadow-[3px_3px_0_rgba(255,255,255,0.23)] sm:grid"><Aperture size={20} /></span>
        <div className="min-w-0 flex-1">
          <p className="text-[10px] font-bold tracking-[0.16em] text-[#c7ff4c]">AGENT COMMAND CENTER</p>
          <h1 className="mt-1 truncate text-xl font-extrabold tracking-normal text-white">就业助手</h1>
          <p className="mt-1 hidden truncate text-xs text-[#c8d7c4] sm:block">{selected?.title ?? '主 Agent 编排专业 Agent，并通过系统工具处理求职事务'}</p>
        </div>
        {selected ? <label className="flex items-center gap-2 text-xs text-[#cfdbc9]"><span className="hidden sm:inline">执行权限</span><select aria-label="执行权限" className="h-10 rounded-md border border-white/20 bg-[#102015]/70 px-3 text-sm font-bold text-white outline-none hover:border-[#c7ff4c] focus:border-[#c7ff4c]" value={selected.mode} disabled={updateMutation.isPending} onChange={(event) => updateMutation.mutate({ id: selected.id, payload: { mode: event.target.value as ChatSession['mode'] } })}><option value="confirm">确认后执行</option><option value="auto">自动执行</option></select></label> : null}
        <button type="button" className="grid size-10 place-items-center rounded-md border border-white/25 text-white hover:border-[#c7ff4c] hover:bg-[#c7ff4c] hover:text-[#102015] xl:hidden" aria-label="打开执行详情" onClick={() => setExecutionOpen(true)}><ListTree size={18} /></button>
      </header>
      <AiServiceStatus capabilities={capabilitiesQuery.data} loading={capabilitiesQuery.isLoading} failed={capabilitiesQuery.isError} />
      {role !== 'student' && selected?.subject_student_id ? <div className="border-b border-[#102015]/15 bg-[#dce9d1] px-4 py-2 text-xs font-medium text-[#30442f]">当前会话范围：指定学生</div> : null}
      {contextLabel ? <div className="border-b border-[#102015]/15 bg-[#e3f6ce] px-4 py-2 text-xs text-[#30442f]">当前上下文：<span className="font-bold">{contextLabel}</span></div> : null}
      <div className="grid min-h-0 flex-1 overflow-hidden grid-cols-1 lg:grid-cols-[minmax(230px,260px)_minmax(420px,1fr)] xl:grid-cols-[minmax(230px,260px)_minmax(420px,1fr)_minmax(290px,330px)]">
        <div className="hidden h-full min-h-0 overflow-hidden lg:block"><SessionList sessions={sessions} selectedId={selectedId} search={search} busy={createMutation.isPending} onSearch={setSearch} onSelect={switchSession} onCreate={() => createMutation.mutate()} onArchive={(id) => updateMutation.mutate({ id, payload: { status: 'archived' } })} /></div>
        {selectedId && !sessionQuery.isLoading ? <Conversation key={`${selectedId}:${composerVersion}`} messages={visibleMessages} run={run} draft={draft} sessionId={selectedId} token={token} disabled={composerDisabled} disabledReason={disabledReason} sendError={sendError} capabilities={capabilitiesQuery.data} onDraftChange={(value) => { setDraft(value); if (sendError) setSendError(null) }} onAttachmentsChange={setAttachmentIds} onAttachmentBusyChange={setAttachmentBusy} onSubmit={() => void submit()} /> : <LoadingState />}
        <div className="hidden h-full min-h-0 overflow-hidden xl:block"><ExecutionPanel run={run} token={token} actionBusy={actionMutation.isPending} onConfirm={(action) => actionMutation.mutate({ type: 'confirm', action })} onReject={(action) => actionMutation.mutate({ type: 'reject', action })} onUndo={(action) => actionMutation.mutate({ type: 'undo', action })} onRetry={() => void retry()} /></div>
      </div>
      {historyOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button className="absolute inset-0 bg-[#102015]/70 backdrop-blur-sm" aria-label="关闭对话历史" onClick={() => setHistoryOpen(false)} />
          <div className="shell-sidebar relative h-full w-[min(85vw,320px)] shadow-2xl">
            <div className="flex h-14 items-center justify-between border-b border-white/10 px-4">
              <span className="text-sm font-bold text-white">对话历史</span>
              <button type="button" className="grid size-8 place-items-center rounded-md border border-white/15 text-[#cfdbc9] hover:bg-white/10" aria-label="关闭对话历史" onClick={() => setHistoryOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <div className="h-[calc(100%_-_3.5rem)]">
              <SessionList sessions={sessions} selectedId={selectedId} search={search} busy={createMutation.isPending} onSearch={setSearch} onSelect={switchSession} onCreate={() => createMutation.mutate()} onArchive={(id) => updateMutation.mutate({ id, payload: { status: 'archived' } })} />
            </div>
          </div>
        </div>
      ) : null}
      {executionOpen ? (
        <div className="fixed inset-0 z-50 xl:hidden">
          <button className="absolute inset-0 bg-[#102015]/70 backdrop-blur-sm" aria-label="关闭执行详情" onClick={() => setExecutionOpen(false)} />
          <div className="absolute inset-y-0 right-0 w-[min(88vw,360px)] bg-[#e9eee5] shadow-2xl">
            <div className="flex h-14 items-center justify-between border-b border-[#102015]/15 px-4">
              <span className="text-sm font-bold text-[#102015]">执行详情</span>
              <button type="button" className="grid size-8 place-items-center rounded-md border border-[#102015]/15 text-[#526051] hover:bg-[#c7ff4c] hover:text-[#102015]" aria-label="关闭执行详情" onClick={() => setExecutionOpen(false)}>
                <X size={16} />
              </button>
            </div>
            <div className="h-[calc(100%_-_3.5rem)]">
              <ExecutionPanel run={run} token={token} actionBusy={actionMutation.isPending} onConfirm={(action) => actionMutation.mutate({ type: 'confirm', action })} onReject={(action) => actionMutation.mutate({ type: 'reject', action })} onUndo={(action) => actionMutation.mutate({ type: 'undo', action })} onRetry={() => void retry()} />
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
