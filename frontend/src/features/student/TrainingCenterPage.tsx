import { useQuery } from '@tanstack/react-query'
import {
  ArrowRight,
  BrainCircuit,
  ClipboardCheck,
  MessageSquareText,
  Presentation,
  Sparkles,
  UsersRound,
} from 'lucide-react'
import { Link } from 'react-router-dom'

import { apiFetch } from '../../app/api'
import { EmptyState, LoadingState, PageHeader, Panel } from '../../components/Ui'
import { isPreHireMode, type SimulationMode } from './training-phases'

type TrainingReport = {
  id: string
  title: string
  mode: SimulationMode
  score: number | null
  completed_at: string | null
}
type Exam = { id: string; title: string; skill_name: string; latest_score: number | null; status: string; submitted_at: string | null }
type TrainingEntry = { title: string; description: string; to: string; icon: typeof BrainCircuit }

const preHireEntries: TrainingEntry[] = [
  { title: '岗位模拟面试', description: '关联已解析简历和目标岗位，支持录音转写、结构化追问与语音朗读。', to: '/student/interview', icon: MessageSquareText },
  { title: '压力面试', description: '可控追问强度，学生可暂停、降低压力或结束训练，所有控制即时生效。', to: '/student/interview?mode=stress_interview', icon: Sparkles },
  { title: '无领导群面', description: '三类候选人角色围绕同一案例讨论，后端校验阶段、角色与回复关系。', to: '/student/interview?mode=group_interview', icon: UsersRound },
  { title: '路演答辩', description: '围绕真实项目完成开场陈述、评委追问和结果收束，每轮都保留证据与评分。', to: '/student/interview?mode=presentation_defense', icon: Presentation },
  { title: '职业规划面试', description: '将目标方向、现实约束和本周行动转成可验收的求职承诺，训练记录可恢复。', to: '/student/interview?mode=career_planning', icon: ClipboardCheck },
]

const postHireEntries: TrainingEntry[] = [
  { title: '入职后职场训练', description: '针对任务澄清、主动沟通、交付协作和跨部门需求变更，形成逐轮评分和事实证据。', to: '/student/workplace', icon: BrainCircuit },
]

const modeLabel: Record<SimulationMode, string> = {
  workplace: '入职后职场训练',
  group_interview: '入职前无领导群面',
  stress_interview: '入职前压力面试',
  presentation_defense: '入职前路演答辩',
  career_planning: '入职前职业规划',
}

function TrainingEntrySection({ title, description, entries }: { title: string; description: string; entries: TrainingEntry[] }) {
  return (
    <section className="border border-[#102015]/20 bg-[#102015] p-1 shadow-[7px_7px_0_rgba(16,32,21,0.13)]">
      <div className="border-b border-[#102015]/20 bg-[#edf2e9] px-5 py-5 sm:px-7">
        <p className="text-[11px] font-bold tracking-[0.14em] text-[#0f766e]">TRAINING PHASE</p>
        <h2 className="mt-1 text-2xl font-extrabold text-[#102015]">{title}</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-[#526051]">{description}</p>
      </div>
      <div className={`grid gap-px bg-[#102015] ${entries.length > 1 ? 'md:grid-cols-2 xl:grid-cols-4' : 'grid-cols-1'}`}>
        {entries.map((entry, index) => {
          const Icon = entry.icon
          return (
            <Link key={entry.title} to={entry.to} className="group relative flex min-h-[206px] flex-col overflow-hidden bg-[#f8fbf5] p-5 transition hover:bg-[#c7ff4c]">
              <span className="grid size-10 place-items-center border border-[#102015]/20 bg-[#edf2e9] text-[#102015] group-hover:bg-[#102015] group-hover:text-[#c7ff4c]">
                <Icon size={20} strokeWidth={2} />
              </span>
              <span className="absolute right-5 top-5 text-[11px] font-extrabold tracking-[0.14em] text-[#748073] group-hover:text-[#30442f]">{String(index + 1).padStart(2, '0')}</span>
              <h3 className="mt-7 text-xl font-extrabold text-[#102015]">{entry.title}</h3>
              <p className="mt-2 max-w-md text-sm leading-6 text-[#526051]">{entry.description}</p>
              <span className="mt-auto inline-flex items-center gap-2 pt-6 text-sm font-extrabold text-[#102015]">进入训练<ArrowRight size={17} className="transition group-hover:translate-x-1" /></span>
            </Link>
          )
        })}
      </div>
    </section>
  )
}

function TrainingReportList({ reports, emptyTitle }: { reports: TrainingReport[]; emptyTitle: string }) {
  if (!reports.length) return <EmptyState title={emptyTitle} description="完成对应阶段的训练后，评分和报告会自动保存在这里。" />
  return (
    <div className="divide-y divide-[#102015]/10">
      {reports.slice(0, 6).map((item) => (
        <Link key={item.id} to={isPreHireMode(item.mode) ? `/student/interview?mode=${item.mode}` : '/student/workplace'} className="group flex items-center justify-between gap-4 py-3.5 first:pt-0 last:pb-0">
          <div className="min-w-0">
            <p className="truncate text-sm font-extrabold text-[#102015] group-hover:text-[#38642f]">{item.title}</p>
            <p className="mt-1 text-xs text-[#647460]">{modeLabel[item.mode]} · {item.completed_at ? new Date(item.completed_at).toLocaleDateString('zh-CN') : '刚刚完成'}</p>
          </div>
          <strong className="grid size-11 shrink-0 place-items-center bg-[#c7ff4c] text-sm text-[#102015]">{item.score ?? '--'}</strong>
        </Link>
      ))}
    </div>
  )
}

export function TrainingCenterPage({ token }: { token: string }) {
  const reports = useQuery({ queryKey: ['workplace-reports'], queryFn: () => apiFetch<TrainingReport[]>('/workplace/reports', {}, token) })
  const exams = useQuery({ queryKey: ['learning-exams'], queryFn: () => apiFetch<Exam[]>('/growth/exams', {}, token) })
  if (reports.isLoading || exams.isLoading) return <LoadingState />

  const examRows = exams.data?.filter((item) => item.submitted_at).slice(0, 4) ?? []
  return (
    <div className="entry-reveal">
      <PageHeader title="训练中心" description="按就业阶段组织训练入口：入职前练求职与面试，入职后练真实工作场景；技能测验独立记录，不与面试会话混在一起。" />
      <div className="space-y-6">
        <TrainingEntrySection title="入职前 · 求职训练" description="适用于还没有入职、正在准备求职的阶段。AI 数字人会根据岗位、简历和场景动态出题，支持语音回答、流式点评、压力等级和结构化评分。" entries={preHireEntries} />
        <TrainingEntrySection title="入职后 · 职场训练" description="适用于已经入职后的工作适应与成长。训练任务澄清、主动沟通、交付协作和跨部门需求变更，不再显示任何求职面试模式。" entries={postHireEntries} />
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-2">
        <Panel title="入职前训练报告">
          <TrainingReportList reports={reports.data?.filter((item) => isPreHireMode(item.mode)) ?? []} emptyTitle="还没有入职前训练报告" />
        </Panel>
        <Panel title="入职后训练报告">
          <TrainingReportList reports={reports.data?.filter((item) => !isPreHireMode(item.mode)) ?? []} emptyTitle="还没有入职后训练报告" />
        </Panel>
      </div>
      <Panel title="技能测验记录" className="mt-6">
        {examRows.length ? (
          <div className="divide-y divide-[#102015]/10">
            {examRows.map((item) => (
              <Link key={item.id} to="/student/learning" className="group flex items-center justify-between gap-4 py-3.5 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="truncate text-sm font-extrabold text-[#102015] group-hover:text-[#38642f]">{item.title}</p>
                  <p className="mt-1 text-xs text-[#647460]">{item.skill_name} · {item.status === 'passed' ? '已通过' : '待巩固'}</p>
                </div>
                <strong className="grid size-11 shrink-0 place-items-center bg-[#102015] text-sm text-[#c7ff4c]">{item.latest_score ?? '--'}</strong>
              </Link>
            ))}
          </div>
        ) : <EmptyState title="还没有提交测验" description="在学习成长页生成并完成技能测验，成绩会自动纳入训练记录。" />}
      </Panel>
    </div>
  )
}
