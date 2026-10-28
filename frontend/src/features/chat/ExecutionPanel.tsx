import { useQuery } from '@tanstack/react-query'
import { AlertCircle, CheckCircle2, ChevronDown, ChevronRight, CircleDashed, Clock3, LoaderCircle, Wrench } from 'lucide-react'
import { useEffect, useState } from 'react'

import { ActionCard } from './ActionCard'
import { readAgentRunDetails } from './api'
import type { ActionProposalView, AgentRunView, AgentStepDetail, JsonValue, ToolCallDetail } from './types'

function StatusIcon({ status }: { status: string }) {
  if (status === 'succeeded' || status === 'completed') return <CheckCircle2 className="text-emerald-700" size={16} />
  if (status === 'failed') return <AlertCircle className="text-[#b24531]" size={16} />
  if (status === 'running') return <LoaderCircle className="animate-spin text-[#38642f]" size={16} />
  return <CircleDashed className="text-[#748073]" size={16} />
}

function formatDuration(value: number | null) {
  if (value === null) return '进行中'
  if (value < 1000) return `${value} 毫秒`
  const seconds = value / 1000
  return `${Number.isInteger(seconds) ? seconds : seconds.toFixed(1)} 秒`
}

function formatTime(value: string | null) {
  if (!value) return '暂无'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(new Date(value))
}

function Timing({ startedAt, completedAt, durationMs }: { startedAt: string | null; completedAt: string | null; durationMs: number | null }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#647460]">
      <span>开始 {formatTime(startedAt)}</span>
      <span>结束 {formatTime(completedAt)}</span>
      <span className="inline-flex items-center gap-1 font-bold text-[#30442f]"><Clock3 size={13} />{formatDuration(durationMs)}</span>
    </div>
  )
}

function DetailField({ label, children }: { label: string; children: React.ReactNode }) {
  return <div><dt className="text-xs font-bold tracking-[0.08em] text-[#647460]">{label}</dt><dd className="mt-1 break-words text-sm leading-6 text-[#102015]">{children}</dd></div>
}

function JsonBlock({ value }: { value: JsonValue | { [key: string]: JsonValue } }) {
  return <pre className="mt-1 max-h-48 overflow-auto whitespace-pre-wrap break-all border border-[#102015] bg-[#102015] p-3 text-xs leading-5 text-[#d9ff8d]">{JSON.stringify(value, null, 2)}</pre>
}

function ErrorDetail({ code, message }: { code: string | null; message: string | null }) {
  if (!code && !message) return null
  return (
    <div className="border-l-2 border-[#ff7358] bg-[#fff0eb] px-3 py-2 text-xs text-[#8c2f1f]">
      {code ? <div className="font-mono font-semibold">{code}</div> : null}
      {message ? <div className="mt-1 leading-5">{message}</div> : null}
    </div>
  )
}

function AgentAudit({ step, tools }: { step: AgentStepDetail; tools: ToolCallDetail[] }) {
  const related = tools.filter((tool) => step.tool_call_ids.includes(tool.id))
  return (
    <dl className="space-y-3">
      <DetailField label="该 Agent 接到的任务">{step.instruction}</DetailField>
      <DetailField label="调用的工具">
        {related.length ? related.map((tool) => `${tool.name}（${tool.status}）`).join('、') : '本步骤未调用工具'}
      </DetailField>
      <DetailField label="最终分析结论">{step.conclusion ?? '暂无分析结论'}</DetailField>
      <ErrorDetail code={step.error_code} message={step.error_message} />
      <Timing startedAt={step.started_at} completedAt={step.completed_at} durationMs={step.duration_ms} />
    </dl>
  )
}

function ToolAudit({ tool }: { tool: ToolCallDetail }) {
  return (
    <dl className="space-y-3">
      <DetailField label="工具信息">版本 {tool.version} · 风险级别 {tool.risk}</DetailField>
      <div><dt className="text-xs font-medium text-slate-500">输入参数（已脱敏）</dt><dd><JsonBlock value={tool.arguments} /></dd></div>
      <div><dt className="text-xs font-medium text-slate-500">返回结果（已脱敏）</dt><dd>{tool.result === null ? <p className="mt-1 text-sm text-slate-500">暂无返回结果</p> : <JsonBlock value={tool.result} />}</dd></div>
      <ErrorDetail code={tool.error_code} message={tool.error_message} />
      <Timing startedAt={tool.started_at} completedAt={tool.completed_at} durationMs={tool.duration_ms} />
    </dl>
  )
}

function DetailBody({ loading, failed, children }: { loading: boolean; failed: boolean; children?: React.ReactNode }) {
  if (loading) return <p className="px-3 py-4 text-center text-xs text-[#647460]">正在加载执行详情...</p>
  if (failed) return <p className="px-3 py-4 text-center text-xs text-[#8c2f1f]">执行详情加载失败，请稍后重试。</p>
  return <div className="border-t border-[#102015]/15 bg-[#f8fbf5] px-3 py-3 shadow-inner">{children}</div>
}

type Expanded = { type: 'step' | 'tool'; id: string } | null

export function ExecutionPanel({
  run,
  token,
  actionBusy,
  onConfirm,
  onReject,
  onUndo,
  onRetry,
}: {
  run: AgentRunView
  token: string
  actionBusy?: boolean
  onConfirm: (action: ActionProposalView) => void
  onReject: (action: ActionProposalView) => void
  onUndo: (action: ActionProposalView) => void
  onRetry: () => void
}) {
  const [expanded, setExpanded] = useState<Expanded>(null)
  useEffect(() => setExpanded(null), [run.runId])
  const detailsQuery = useQuery({
    queryKey: ['agent-run-details', run.runId],
    queryFn: () => readAgentRunDetails(run.runId, token),
    enabled: Boolean(expanded && run.runId),
    refetchInterval: expanded && (run.status === 'queued' || run.status === 'running') ? 2000 : false,
  })
  const steps = Object.values(run.steps)
  const tools = Object.values(run.tools)
  const actions = Object.values(run.actions)
  const toggle = (next: Exclude<Expanded, null>) => setExpanded((current) => current?.type === next.type && current.id === next.id ? null : next)

  return (
    <aside className="h-full min-h-0 overflow-y-auto border-l border-[#102015] bg-[#e9eee5] p-4" aria-label="Agent 执行详情">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-extrabold text-[#102015]">执行过程</h2>
        <span className="border border-[#102015]/15 bg-white/60 px-2 py-1 text-[11px] font-bold text-[#526051]">{run.provider ?? '等待模型'}</span>
      </div>
      {!steps.length && !tools.length ? <p className="mt-8 text-center text-sm text-[#647460]">发送消息后显示多 Agent 协作过程</p> : null}
      {steps.length ? <div className="mt-5"><h3 className="text-[10px] font-extrabold tracking-[0.14em] text-[#647460]">专业 AGENT</h3><div className="mt-2 overflow-hidden border border-[#102015]/20 bg-white">{steps.map((step) => {
        const open = expanded?.type === 'step' && expanded.id === step.id
        const detail = detailsQuery.data?.steps.find((item) => item.step_key === step.id)
        return <div key={step.id} className="border-b border-[#102015]/10 last:border-b-0"><button type="button" aria-label={`查看 ${step.agent} Agent 详情`} aria-expanded={open} className="flex min-h-11 w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[#e3f6ce]" onClick={() => toggle({ type: 'step', id: step.id })}><StatusIcon status={step.status} /><span className="min-w-0 flex-1 truncate font-bold text-[#102015]">{step.agent}</span><span className="text-[11px] text-[#647460]">{step.status}</span>{open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}</button>{open ? <DetailBody loading={detailsQuery.isPending} failed={detailsQuery.isError}>{detail ? <AgentAudit step={detail} tools={detailsQuery.data?.tools ?? []} /> : null}</DetailBody> : null}</div>
      })}</div></div> : null}
      {tools.length ? <div className="mt-5"><h3 className="text-[10px] font-extrabold tracking-[0.14em] text-[#647460]">工具调用</h3><div className="mt-2 overflow-hidden border border-[#102015]/20 bg-white">{tools.map((tool) => {
        const open = expanded?.type === 'tool' && expanded.id === tool.id
        const detail = detailsQuery.data?.tools.find((item) => item.id === tool.id)
        return <div key={tool.id} className="border-b border-[#102015]/10 last:border-b-0"><button type="button" aria-label={`查看 ${tool.name} 工具详情`} aria-expanded={open} className="flex min-h-11 w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[#e3f6ce]" onClick={() => toggle({ type: 'tool', id: tool.id })}><Wrench className="text-[#38642f]" size={15} /><span className="min-w-0 flex-1 truncate font-bold text-[#102015]">{tool.name}</span><span className="text-[11px] text-[#647460]">{tool.status}</span>{open ? <ChevronDown size={15} /> : <ChevronRight size={15} />}</button>{open ? <DetailBody loading={detailsQuery.isPending} failed={detailsQuery.isError}>{detail ? <ToolAudit tool={detail} /> : null}</DetailBody> : null}</div>
      })}</div></div> : null}
      {actions.length ? <div className="mt-5 space-y-3"><h3 className="text-[10px] font-extrabold tracking-[0.14em] text-[#647460]">待办操作</h3>{actions.map((action) => <ActionCard key={action.id} action={action} busy={actionBusy} onConfirm={() => onConfirm(action)} onReject={() => onReject(action)} onUndo={() => onUndo(action)} />)}</div> : null}
      {run.status === 'failed' ? <button type="button" className="mt-5 h-9 w-full border border-[#102015]/30 bg-white text-sm font-bold text-[#102015] hover:bg-[#c7ff4c]" onClick={onRetry}>重试失败任务</button> : null}
    </aside>
  )
}
