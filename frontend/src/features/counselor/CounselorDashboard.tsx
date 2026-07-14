import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BriefcaseBusiness, Users } from 'lucide-react'
import { useEffect, useRef } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, LoadingState, PageHeader, Panel } from '../../components/Ui'

export type CounselorData = {
  student_count: number
  application_count: number
  risk_count: number
  students: { id: string; display_name: string; username: string; risk_count: number }[]
  risks: { id: string; student_id: string; rule_code: string; level: string; facts: { message?: string; value?: number } }[]
}

function OverviewChart({ data }: { data: CounselorData }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!ref.current || typeof ResizeObserver === 'undefined') return
    let disposed = false
    let cleanup = () => undefined
    void import('./chartRuntime').then(({ initOverviewChart }) => {
      if (disposed || !ref.current) return
      const chart = initOverviewChart(ref.current, Math.max(0, data.student_count - data.risk_count), data.risk_count)
      const observer = new ResizeObserver(() => chart.resize())
      observer.observe(ref.current)
      cleanup = () => { observer.disconnect(); chart.dispose() }
    })
    return () => { disposed = true; cleanup() }
  }, [data])
  return <div ref={ref} className="h-52 min-w-0 max-w-full overflow-hidden" aria-label="班级风险分布图" />
}

export function CounselorDashboard({ token }: { token: string }) {
  const query = useQuery({ queryKey: ['counselor-dashboard'], queryFn: () => apiFetch<CounselorData>('/dashboard/counselor', {}, token) })
  if (query.isLoading) return <LoadingState />
  if (!query.data) return <EmptyState title="班级数据暂不可用" description="请刷新页面或稍后重试。" />
  const data = query.data
  const studentMap = new Map(data.students.map((student) => [student.id, student]))
  return <><PageHeader title="班级就业概览" description="依据求职过程事实定位需要帮助的学生，所有风险均可查看触发原因。" /><section className="grid border border-slate-200 bg-white sm:grid-cols-3">{[{ label: '班级学生', value: data.student_count, icon: Users, color: 'text-teal-700' }, { label: '累计投递', value: data.application_count, icon: BriefcaseBusiness, color: 'text-sky-700' }, { label: '需要关注', value: data.risk_count, icon: AlertTriangle, color: 'text-amber-700' }].map((item, index) => <div key={item.label} className={`p-5 ${index ? 'border-t border-slate-200 sm:border-l sm:border-t-0' : ''}`}><div className="flex items-center justify-between"><p className="text-xs text-slate-500">{item.label}</p><item.icon className={item.color} size={18} /></div><p className="mt-3 text-3xl font-semibold">{item.value}</p></div>)}</section><div className="mt-6 grid gap-6 xl:grid-cols-[0.75fr_1.25fr]"><Panel title="班级风险分布"><OverviewChart data={data} /></Panel><Panel title="需要关注的学生">{data.risks.length ? <div className="divide-y divide-slate-200">{data.risks.map((risk) => <div key={risk.id} className="grid gap-3 py-4 sm:grid-cols-[160px_1fr_auto] sm:items-center"><div><p className="text-sm font-medium">{studentMap.get(risk.student_id)?.display_name ?? '学生'}</p><p className="mt-1 text-xs text-slate-500">{studentMap.get(risk.student_id)?.username}</p></div><div><p className="text-sm text-slate-800">{risk.facts.message ?? risk.rule_code}</p><p className="mt-1 text-xs text-slate-500">规则：{risk.rule_code}</p></div><span className="text-xs font-medium text-amber-700">{risk.level === 'intervention' ? '需干预' : '关注'}</span></div>)}</div> : <EmptyState title="当前没有风险提醒" description="系统每天根据任务、投递和面试事实重新评估。" />}</Panel></div></>
}
