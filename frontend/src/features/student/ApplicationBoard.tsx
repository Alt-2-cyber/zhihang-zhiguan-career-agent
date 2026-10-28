import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LoaderCircle, Plus, RefreshCw } from 'lucide-react'
import { useState } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, Notice, PageHeader, Panel, primaryButton, secondaryButton } from '../../components/Ui'
import { AskAgentButton } from '../chat/AskAgentButton'

type Application = { id: string; job_id: string; stage: string }
type Job = { id: string; title: string; company: string }
type RefreshSummary = { checked: number; succeeded: number; failed: number; items_imported: number }
const stages = ['saved', 'applied', 'assessment', 'interview', 'offered', 'closed'] as const
const labels: Record<string, string> = { saved: '待投递', applied: '已投递', assessment: '笔试测评', interview: '面试', offered: '录用', closed: '已结束' }
const nextStage: Record<string, string | undefined> = { saved: 'applied', applied: 'assessment', assessment: 'interview', interview: 'offered', offered: 'closed' }

export function ApplicationBoard({ token }: { token: string }) {
  const queryClient = useQueryClient(); const [jobId, setJobId] = useState('')
  const applications = useQuery({ queryKey: ['applications'], queryFn: () => apiFetch<Application[]>('/applications', {}, token) })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: () => apiFetch<Job[]>('/jobs', {}, token) })
  const refreshJobs = useMutation({
    mutationFn: () => apiFetch<RefreshSummary>('/intelligence/sources/refresh?force=true', { method: 'POST' }, token, 120_000),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
        queryClient.invalidateQueries({ queryKey: ['job-intelligence'] }),
      ])
    },
  })
  const create = useMutation({ mutationFn: () => apiFetch('/applications', { method: 'POST', body: JSON.stringify({ job_id: jobId }) }, token), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['applications'] }) })
  const advance = useMutation({ mutationFn: ({ id, stage }: { id: string; stage: string }) => apiFetch(`/applications/${id}/stage`, { method: 'PATCH', body: JSON.stringify({ stage }) }, token), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['applications'] }) })
  const jobMap = new Map(jobs.data?.map((job) => [job.id, job]))
  return <>
    <PageHeader
      title="投递管理"
      description="记录每个岗位的真实进展，所有阶段变化都会保留历史。"
      action={
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            className={secondaryButton}
            aria-label="抓取公开岗位"
            title="从已登记的公开招聘来源同步岗位"
            disabled={refreshJobs.isPending}
            onClick={() => refreshJobs.mutate()}
          >
            {refreshJobs.isPending ? <LoaderCircle className="animate-spin" size={16} /> : <RefreshCw size={16} />}
            {refreshJobs.isPending ? '正在抓取' : '抓取公开岗位'}
          </button>
          <select aria-label="选择岗位" value={jobId} onChange={(e) => setJobId(e.target.value)} className="h-10 w-64 max-w-full shrink-0 rounded-md border border-slate-300 bg-white px-3 text-sm">
            <option value="">选择岗位</option>
            {jobs.data?.map((job) => <option key={job.id} value={job.id}>{job.title} · {job.company}</option>)}
          </select>
          <button type="button" className={primaryButton} disabled={!jobId || create.isPending} onClick={() => create.mutate()}>
            {create.isPending ? <LoaderCircle className="animate-spin" size={16} /> : <Plus size={16} />}
            加入看板
          </button>
        </div>
      }
    />
    {refreshJobs.isError ? <div className="mb-5"><Notice tone="danger">岗位抓取失败：{refreshJobs.error.message}。请检查公开来源状态后重试。</Notice></div> : null}
    {refreshJobs.data ? <div className="mb-5"><Notice tone={refreshJobs.data.failed ? 'warning' : 'success'}>
      本次检查 {refreshJobs.data.checked} 个来源，成功 {refreshJobs.data.succeeded} 个，失败 {refreshJobs.data.failed} 个，实际导入 {refreshJobs.data.items_imported} 条岗位。结果已写入岗位库，不会自动投递。
    </Notice></div> : null}
    <div className="mb-5"><Notice>点击“抓取公开岗位”会调用已登记的公开招聘来源适配器；页面只导入岗位和来源链接，不绕过登录、验证码或站点限制。</Notice></div>
    <div className="grid min-w-0 gap-4 xl:grid-cols-6">{stages.map((stage) => { const items = applications.data?.filter((item) => item.stage === stage) ?? []; return <Panel key={stage} title={`${labels[stage]} · ${items.length}`} className="min-w-0"><div className="space-y-3">{items.map((item) => { const job = jobMap.get(item.job_id); return <article key={item.id} className="border-l-2 border-teal-700 bg-slate-50 p-3"><p className="break-words text-sm font-medium">{job?.title ?? '岗位'}</p><p className="mt-1 text-xs text-slate-500">{job?.company}</p><AskAgentButton role="student" context={{ type: 'application', id: item.id }} className="mt-3 h-8 w-full px-2 text-xs" />{nextStage[stage] ? <button type="button" className={`${secondaryButton} mt-2 h-8 w-full px-2 text-xs`} onClick={() => advance.mutate({ id: item.id, stage: nextStage[stage]! })}>推进到{labels[nextStage[stage]!]}</button> : null}</article> })}{items.length === 0 ? <p className="py-5 text-center text-xs text-slate-400">暂无记录</p> : null}</div></Panel> })}</div>
    {applications.data?.length === 0 ? <div className="mt-6"><EmptyState title="还没有投递记录" description="抓取或选择岗位后加入看板，开始记录求职过程。" /></div> : null}
  </>
}

