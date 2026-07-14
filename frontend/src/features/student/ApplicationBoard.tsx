import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Plus } from 'lucide-react'
import { useState } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, PageHeader, Panel, primaryButton, secondaryButton } from '../../components/Ui'

type Application = { id: string; job_id: string; stage: string }
type Job = { id: string; title: string; company: string }
const stages = ['saved', 'applied', 'assessment', 'interview', 'offered', 'closed'] as const
const labels: Record<string, string> = { saved: '待投递', applied: '已投递', assessment: '笔试测评', interview: '面试', offered: '录用', closed: '已结束' }
const nextStage: Record<string, string | undefined> = { saved: 'applied', applied: 'assessment', assessment: 'interview', interview: 'offered', offered: 'closed' }

export function ApplicationBoard({ token }: { token: string }) {
  const queryClient = useQueryClient(); const [jobId, setJobId] = useState('')
  const applications = useQuery({ queryKey: ['applications'], queryFn: () => apiFetch<Application[]>('/applications', {}, token) })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: () => apiFetch<Job[]>('/jobs', {}, token) })
  const create = useMutation({ mutationFn: () => apiFetch('/applications', { method: 'POST', body: JSON.stringify({ job_id: jobId }) }, token), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['applications'] }) })
  const advance = useMutation({ mutationFn: ({ id, stage }: { id: string; stage: string }) => apiFetch(`/applications/${id}/stage`, { method: 'PATCH', body: JSON.stringify({ stage }) }, token), onSuccess: () => queryClient.invalidateQueries({ queryKey: ['applications'] }) })
  const jobMap = new Map(jobs.data?.map((job) => [job.id, job]))
  return <><PageHeader title="投递管理" description="记录每个岗位的真实进展，所有阶段变化都会保留历史。" action={<div className="flex gap-2"><select aria-label="选择岗位" value={jobId} onChange={(e) => setJobId(e.target.value)} className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm"><option value="">选择岗位</option>{jobs.data?.map((job) => <option key={job.id} value={job.id}>{job.title}</option>)}</select><button className={primaryButton} disabled={!jobId} onClick={() => create.mutate()}><Plus size={16} />加入看板</button></div>} /><div className="grid min-w-0 gap-4 xl:grid-cols-6">{stages.map((stage) => { const items = applications.data?.filter((item) => item.stage === stage) ?? []; return <Panel key={stage} title={`${labels[stage]} · ${items.length}`} className="min-w-0"><div className="space-y-3">{items.map((item) => { const job = jobMap.get(item.job_id); return <article key={item.id} className="border-l-2 border-teal-700 bg-slate-50 p-3"><p className="break-words text-sm font-medium">{job?.title ?? '岗位'}</p><p className="mt-1 text-xs text-slate-500">{job?.company}</p>{nextStage[stage] ? <button className={`${secondaryButton} mt-3 h-8 w-full px-2 text-xs`} onClick={() => advance.mutate({ id: item.id, stage: nextStage[stage]! })}>推进到{labels[nextStage[stage]!]}</button> : null}</article> })}{items.length === 0 ? <p className="py-5 text-center text-xs text-slate-400">暂无记录</p> : null}</div></Panel> })}</div>{applications.data?.length === 0 ? <div className="mt-6"><EmptyState title="还没有投递记录" description="选择岗位加入看板，开始记录求职过程。" /></div> : null}</>
}

