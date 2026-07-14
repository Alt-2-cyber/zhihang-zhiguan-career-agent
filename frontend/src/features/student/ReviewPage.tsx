import { useMutation } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'

import { apiFetch } from '../../app/api'
import { EmptyState, PageHeader, Panel, primaryButton } from '../../components/Ui'

type Review = { id: string; metrics: Record<string, number>; insights: string[]; actions: string[]; status: string }
const metricLabels: Record<string, string> = { applications: '投递', responses: '回复', assessments: '笔试', interviews: '面试', offers: '录用' }

export function ReviewPage({ token }: { token: string }) {
  const review = useMutation({ mutationFn: () => apiFetch<Review>('/reviews/weekly', { method: 'POST' }, token) })
  return <><PageHeader title="每周复盘" description="从真实投递事件计算求职漏斗，并给出最多三项优先改进动作。" action={<button className={primaryButton} onClick={() => review.mutate()}><RefreshCw size={16} />生成本周复盘</button>} />{review.data ? <div className="space-y-6"><section className="grid border border-slate-200 bg-white sm:grid-cols-5">{Object.entries(review.data.metrics).map(([key, value], index) => <div key={key} className={`p-5 ${index ? 'border-t border-slate-200 sm:border-l sm:border-t-0' : ''}`}><p className="text-xs text-slate-500">{metricLabels[key]}</p><p className="mt-2 text-2xl font-semibold">{value}</p></div>)}</section><div className="grid gap-6 lg:grid-cols-2"><Panel title="数据洞察"><ul className="space-y-3 text-sm leading-6 text-slate-700">{review.data.insights.map((item) => <li key={item}>• {item}</li>)}</ul></Panel><Panel title="下周优先行动"><ol className="space-y-3">{review.data.actions.map((item, index) => <li key={item} className="flex gap-3 text-sm"><span className="grid size-6 shrink-0 place-items-center bg-teal-700 text-xs text-white">{index + 1}</span><span className="pt-0.5">{item}</span></li>)}</ol></Panel></div></div> : <EmptyState title="还没有本周复盘" description="系统会基于最近七天的投递事件生成统计与建议。" />}</>
}

