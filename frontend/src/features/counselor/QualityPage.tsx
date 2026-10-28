import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Building2, CheckCircle2, ShieldAlert, UserCheck } from 'lucide-react'
import { useState } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, LoadingState, Notice, PageHeader, Panel, primaryButton, secondaryButton } from '../../components/Ui'
import { AskAgentButton } from '../chat/AskAgentButton'

type Employment = { id: string; student_name: string; company: string; job_title: string; onboard_date: string; status: string }
type PendingFeedback = { id: string; type: 'employee' | 'employer' | 'interview'; student_name: string; company: string; overall_score: number | null; content: string }
type Quality = {
  metrics: { employed: number; followups_due: number; pending_moderation: number }
  employments: Employment[]
  pending_feedback: PendingFeedback[]
  companies: { company: string; employment_count: number }[]
}

const typeLabel: Record<string, string> = { employee: '学生反馈', employer: '企业评价', interview: '面试经验' }

export function QualityPage({ token }: { token: string }) {
  const queryClient = useQueryClient()
  const [reason, setReason] = useState('内容合规，可用于就业质量分析')
  const query = useQuery({ queryKey: ['counselor-quality'], queryFn: () => apiFetch<Quality>('/employment/counselor/quality', {}, token) })
  const moderate = useMutation({
    mutationFn: ({ item, decision }: { item: PendingFeedback; decision: 'approved' | 'rejected' }) =>
      apiFetch('/employment/counselor/moderation', { method: 'POST', body: JSON.stringify({ feedback_type: item.type, feedback_id: item.id, decision, reason }) }, token),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ['counselor-quality'] }),
  })
  if (query.isLoading) return <LoadingState />
  if (!query.data) return <EmptyState title="就业质量数据暂不可用" description="请稍后刷新页面。" />
  const data = query.data
  return (
    <>
      <PageHeader title="就业质量" description="查看入职跟踪、企业反馈、学生经验和待审核内容，把就业结果反哺课程建设和重点帮扶。" action={<AskAgentButton role="counselor" context={{ type: 'quality_feedback', id: 'overview' }} />} />
      <section className="grid border border-slate-200 bg-white sm:grid-cols-3">
        {[
          { label: '已就业学生', value: data.metrics.employed, icon: UserCheck },
          { label: '到期回访', value: data.metrics.followups_due, icon: ShieldAlert },
          { label: '待审核反馈', value: data.metrics.pending_moderation, icon: CheckCircle2 },
        ].map((item, index) => <div key={item.label} className={`p-5 ${index ? 'border-t border-slate-200 sm:border-l sm:border-t-0' : ''}`}><div className="flex items-center justify-between"><p className="text-xs text-slate-500">{item.label}</p><item.icon className="text-teal-700" size={18} /></div><p className="mt-3 text-3xl font-semibold">{item.value}</p></div>)}
      </section>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel title="待审核反馈">
          {moderate.isError ? <Notice tone="danger">{moderate.error.message}</Notice> : null}
          {data.pending_feedback.length ? (
            <div className="space-y-4">
              <input aria-label="审核理由" value={reason} onChange={(event) => setReason(event.target.value)} className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm" />
              {data.pending_feedback.map((item) => <article key={`${item.type}-${item.id}`} className="rounded-md border border-slate-200 p-4"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium">{typeLabel[item.type]} · {item.student_name}</p><span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">{item.company}</span></div><p className="mt-2 text-sm leading-6 text-slate-700">{item.content}</p>{item.overall_score ? <p className="mt-2 text-xs text-slate-500">综合评分：{item.overall_score}</p> : null}<div className="mt-3 flex gap-2"><button className={primaryButton} disabled={reason.trim().length < 2 || moderate.isPending} onClick={() => moderate.mutate({ item, decision: 'approved' })}>通过</button><button className={secondaryButton} disabled={reason.trim().length < 2 || moderate.isPending} onClick={() => moderate.mutate({ item, decision: 'rejected' })}>退回</button></div></article>)}
            </div>
          ) : <EmptyState title="暂无待审核反馈" description="学生或企业提交后，会在这里按班级权限进入审核队列。" />}
        </Panel>
        <div className="space-y-6">
          <Panel title="企业录用分布">
            {data.companies.length ? <div className="space-y-3">{data.companies.map((company) => <div key={company.company} className="flex items-center justify-between rounded-md border border-slate-200 px-4 py-3"><span className="flex items-center gap-2 text-sm"><Building2 className="text-teal-700" size={16} />{company.company}</span><span className="font-semibold">{company.employment_count}</span></div>)}</div> : <EmptyState title="暂无企业分布" description="就业记录建立后自动汇总。" />}
          </Panel>
          <Panel title="近期就业记录">
            {data.employments.length ? <div className="divide-y divide-slate-200">{data.employments.slice(0, 8).map((item) => <article key={item.id} className="py-3 first:pt-0 last:pb-0"><p className="text-sm font-medium">{item.student_name} · {item.company}</p><p className="mt-1 text-xs text-slate-500">{item.job_title} · {item.onboard_date}</p></article>)}</div> : <EmptyState title="暂无就业记录" description="学生建立就业记录后在这里展示。" />}
          </Panel>
        </div>
      </div>
    </>
  )
}
