import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, BriefcaseBusiness, CheckCircle2, Target } from 'lucide-react'
import { Link } from 'react-router-dom'

import { apiFetch } from '../../app/api'
import { EmptyState, LoadingState, PageHeader, Panel, primaryButton } from '../../components/Ui'
import { StudentInterventions } from './StudentInterventions'

type Dashboard = {
  profile_confirmed: boolean
  primary_role: string | null
  application_count: number
  stage_counts: Record<string, number>
  risk_count: number
  tasks: { id: string; title: string; due_date: string; status: string }[]
}

export function StudentDashboard({ token }: { token: string }) {
  const query = useQuery({ queryKey: ['student-dashboard'], queryFn: () => apiFetch<Dashboard>('/dashboard/student', {}, token) })
  if (query.isLoading) return <LoadingState />
  if (!query.data) return <EmptyState title="工作台暂不可用" description="请刷新页面或稍后重试。" />
  const data = query.data
  const metrics = [
    { label: '目标岗位', value: data.primary_role ?? '未确定', icon: Target, color: 'text-teal-700' },
    { label: '累计投递', value: String(data.application_count), icon: BriefcaseBusiness, color: 'text-sky-700' },
    { label: '进入面试', value: String(data.stage_counts.interview ?? 0), icon: CheckCircle2, color: 'text-emerald-700' },
    { label: '待处理提醒', value: String(data.risk_count), icon: AlertTriangle, color: data.risk_count ? 'text-amber-700' : 'text-slate-500' },
  ]

  return (
    <>
      <PageHeader
        title="学生工作台"
        description="围绕当前目标推进今天的求职任务，并持续记录投递和面试结果。"
        action={
          <Link to={data.profile_confirmed ? '/student/assistant' : '/student/profile'} className={primaryButton}>
            {data.profile_confirmed ? '询问就业助手' : '建立就业画像'}
          </Link>
        }
      />
      <section className="grid border border-slate-200 bg-white sm:grid-cols-2 xl:grid-cols-4">
        {metrics.map(({ label, value, icon: Icon, color }, index) => <div key={label} className={`p-5 ${index ? 'border-t border-slate-200 sm:border-l sm:border-t-0' : ''}`}><div className="flex items-center justify-between"><p className="text-xs text-slate-500">{label}</p><Icon className={color} size={18} /></div><p className="mt-3 truncate text-2xl font-semibold">{value}</p></div>)}
      </section>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
        <Panel title="近期任务">
          {data.tasks.length ? <div className="divide-y divide-slate-200">{data.tasks.map((task) => <div key={task.id} className="flex items-center justify-between gap-4 py-3"><div><p className="text-sm font-medium">{task.title}</p><p className="mt-1 text-xs text-slate-500">截止 {task.due_date}</p></div><span className="text-xs text-slate-500">{task.status === 'completed' ? '已完成' : '待完成'}</span></div>)}</div> : <EmptyState title="还没有行动任务" description="确认就业画像后生成四周求职计划。" />}
        </Panel>
        <Panel title="投递漏斗">
          {['saved', 'applied', 'assessment', 'interview', 'offered'].map((stage, index) => { const labels = ['收藏岗位', '已投递', '笔试测评', '面试', '录用']; const count = data.stage_counts[stage] ?? 0; const width = data.application_count ? Math.max(8, (count / data.application_count) * 100) : 8; return <div key={stage} className="mb-4 last:mb-0"><div className="mb-1.5 flex justify-between text-xs"><span>{labels[index]}</span><span>{count}</span></div><div className="h-2 bg-slate-100"><div className="h-full bg-teal-700" style={{ width: `${width}%` }} /></div></div> })}
        </Panel>
      </div>
      <StudentInterventions token={token} />
    </>
  )
}
