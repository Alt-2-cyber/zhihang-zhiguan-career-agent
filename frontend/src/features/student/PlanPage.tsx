import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Sparkles } from 'lucide-react'
import { useState } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, Notice, PageHeader, Panel, inputClass, primaryButton, secondaryButton } from '../../components/Ui'
import { AskAgentButton } from '../chat/AskAgentButton'

type Plan = { id: string; provider: string; primary_role: string; backup_roles: string[]; rationale: string; status: string; tasks: { id: string; title: string; week: number; due_date: string; acceptance_criteria: string; status: string }[] }

export function PlanPage({ token }: { token: string }) {
  const queryClient = useQueryClient()
  const [targetRole, setTargetRole] = useState('')
  const [generated, setGenerated] = useState<Plan | null>(null)
  const current = useQuery({ queryKey: ['current-plan'], queryFn: () => apiFetch<Plan>('/plans/current', {}, token), retry: false })
  const generate = useMutation({ mutationFn: () => apiFetch<Plan>('/plans/generate', { method: 'POST', body: JSON.stringify({ target_role: targetRole || null }) }, token), onSuccess: setGenerated })
  const confirm = useMutation({ mutationFn: (id: string) => apiFetch<Plan>(`/plans/${id}/confirm`, { method: 'POST' }, token), onSuccess: (plan) => { setGenerated(plan); queryClient.setQueryData(['current-plan'], plan) } })
  const plan = generated ?? current.data
  return <><PageHeader title="四周求职计划" description="把岗位目标拆解为有截止日期和完成标准的行动任务。" action={plan ? <AskAgentButton role="student" context={{ type: 'plan', id: plan.id }} /> : undefined} />
    <Panel className="mb-6"><div className="flex flex-col gap-3 sm:flex-row"><label className="flex-1 text-sm font-medium text-slate-700">目标岗位<input value={targetRole} onChange={(e) => setTargetRole(e.target.value)} placeholder="例如：数据分析师" className={inputClass} /></label><button className={`${primaryButton} sm:mt-7`} onClick={() => generate.mutate()} disabled={generate.isPending}><Sparkles size={17} />生成计划</button></div></Panel>
    {plan ? <div className="space-y-6"><Panel><div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between"><div><p className="text-xs text-slate-500">主目标岗位</p><h2 className="mt-1 text-xl font-semibold">{plan.primary_role}</h2><p className="mt-3 text-sm leading-6 text-slate-600">{plan.rationale}</p><p className="mt-2 text-xs text-slate-500">备选：{plan.backup_roles.join('、') || '无'}</p></div>{plan.status === 'pending_confirmation' ? <button className={secondaryButton} onClick={() => confirm.mutate(plan.id)}><Check size={16} />确认计划</button> : <Notice tone="success">计划已生效</Notice>}</div></Panel><section className="grid gap-4 lg:grid-cols-4">{plan.tasks.map((task) => <article key={task.id} className="rounded-md border border-slate-200 bg-white p-5"><p className="text-xs font-semibold text-teal-700">第 {task.week} 周</p><h3 className="mt-3 text-sm font-semibold">{task.title}</h3><p className="mt-3 text-xs leading-5 text-slate-600">{task.acceptance_criteria}</p><p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-500">截止 {task.due_date}</p></article>)}</section></div> : <EmptyState title="尚未生成计划" description="输入目标岗位，或由 AI 根据已确认画像推荐方向。" />}</>
}

