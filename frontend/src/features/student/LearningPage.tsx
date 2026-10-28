import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowUpRight,
  BookOpenCheck,
  BrainCircuit,
  CheckCircle2,
  CircleDashed,
  ExternalLink,
  ListChecks,
  Target,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { apiFetch } from '../../app/api'
import {
  EmptyState,
  LoadingState,
  Notice,
  PageHeader,
  Panel,
  primaryButton,
  secondaryButton,
} from '../../components/Ui'
import { AskAgentButton } from '../chat/AskAgentButton'

type SkillGap = {
  id: string
  skill_name: string
  current_level: number
  baseline_level: number
  target_level: number
  evidence_count: number
  data_status: string
  score_reason: string
}

type LearningTask = {
  id: string
  course_id: string | null
  course_title: string | null
  skill_name: string
  title: string
  due_date: string
  acceptance_criteria: string
  status: string
  completion_note: string | null
}

type Growth = {
  plan: { id: string; target_role: string; rationale: string } | null
  skill_gaps: SkillGap[]
  tasks: LearningTask[]
  metrics: { total_tasks: number; completed_tasks: number; completion_rate: number }
  analytics: {
    rubric_version: string
    radar: Array<{
      skill_name: string
      baseline: number
      current: number
      target: number
      gap: number
      evidence_count: number
      baseline_evidence_count: number
      latest_exam_score: number | null
      latest_training_score: number | null
      score_sources: string[]
      score_reason: string
      data_status: string
      status: string
    }>
    weak_points: Array<{
      skill_name: string
      baseline: number
      current: number
      target: number
      gap: number
      evidence_count: number
      baseline_evidence_count: number
      latest_exam_score: number | null
      latest_training_score: number | null
      score_sources: string[]
      score_reason: string
      data_status: string
      status: string
    }>
    trend: Array<{ period: string; average_score: number | null; completed_tasks: number; exam_count: number }>
  }
}

type Course = {
  id: string
  title: string
  provider: string
  source_url: string | null
  duration_minutes: number
  skills: string[]
  description: string
}

type Exam = {
  id: string
  title: string
  skill_name: string
  status: string
  question_count: number
  passing_score: number
  duration_minutes: number
  started_at: string | null
  latest_score: number | null
  latest_passed: boolean | null
  created_at: string
}

function LearningAnalyticsCharts({ analytics }: { analytics: Growth['analytics'] }) {
  const radarRef = useRef<HTMLDivElement>(null)
  const trendRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    let cleanup = () => {}
    let disposed = false
    void import('./analyticsChartRuntime').then(({ initLearningRadar, initLearningTrend }) => {
      if (disposed || !trendRef.current) return
      const radar = radarRef.current && analytics.radar.length >= 3
        ? initLearningRadar(radarRef.current, analytics.radar)
        : null
      const trend = initLearningTrend(trendRef.current, analytics.trend)
      const observer = new ResizeObserver(() => {
        radar?.resize()
        trend.resize()
      })
      if (radarRef.current) observer.observe(radarRef.current)
      observer.observe(trendRef.current)
      cleanup = () => {
        observer.disconnect()
        radar?.dispose()
        trend.dispose()
      }
    })
    return () => {
      disposed = true
      cleanup()
    }
  }, [analytics.radar, analytics.trend])

  return (
    <div className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
      <Panel title="能力雷达">
        {analytics.radar.length >= 3 ? (
          <div ref={radarRef} className="h-72 w-full" />
        ) : (
          <EmptyState title="能力维度不足" description="至少积累三项技能诊断后生成雷达图。" />
        )}
      </Panel>
      <Panel title="学习趋势">
        <div ref={trendRef} className="h-72 w-full" />
      </Panel>
    </div>
  )
}

function examStatusLabel(status: string, score: number | null) {
  if (status === 'in_progress') return '进行中'
  if (status === 'generated') return '待开始'
  if (status === 'passed') return score === null ? '已通过' : `${score} 分`
  if (status === 'submitted') return score === null ? '已交卷' : `${score} 分 · 待补强`
  if (status === 'expired') return '已过期'
  return '处理中'
}

export function LearningPage({ token }: { token: string }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [editing, setEditing] = useState<string | null>(null)
  const [evidence, setEvidence] = useState('')
  const [selectedCourseId, setSelectedCourseId] = useState('')

  const overviewQuery = useQuery({
    queryKey: ['growth-overview'],
    queryFn: () => apiFetch<Growth>('/growth/overview', {}, token),
  })
  const coursesQuery = useQuery({
    queryKey: ['growth-courses'],
    queryFn: () => apiFetch<Course[]>('/growth/courses?limit=20', {}, token),
  })
  const examsQuery = useQuery({
    queryKey: ['growth-exams'],
    queryFn: () => apiFetch<Exam[]>('/growth/exams', {}, token),
  })

  const courses = coursesQuery.data ?? []
  const selectedCourse = courses.find((course) => course.id === selectedCourseId) ?? courses[0]
  const data = overviewQuery.data
  const recommendedTask = data?.tasks.find((task) => task.status !== 'completed')
  const bSiteCourseCount = useMemo(
    () => courses.filter((course) => course.source_url?.includes('bilibili.com')).length,
    [courses],
  )

  const updateTask = useMutation({
    mutationFn: ({ id, status, completionNote }: { id: string; status: string; completionNote?: string }) =>
      apiFetch(
        `/growth/tasks/${id}`,
        { method: 'PATCH', body: JSON.stringify({ status, completion_note: completionNote || null }) },
        token,
      ),
    onSuccess: async () => {
      setEditing(null)
      setEvidence('')
      await queryClient.invalidateQueries({ queryKey: ['growth-overview'] })
    },
  })

  const createExam = useMutation({
    mutationFn: () =>
      apiFetch<{ id: string }>(
        '/growth/exams',
        {
          method: 'POST',
          body: JSON.stringify({
            course_id: selectedCourse?.id ?? recommendedTask?.course_id ?? null,
            task_id: recommendedTask?.id ?? null,
            skill_name: selectedCourse?.skills[0] ?? recommendedTask?.skill_name ?? null,
            question_count: 5,
          }),
        },
        token,
        240_000,
      ),
    onSuccess: async (exam) => {
      await queryClient.invalidateQueries({ queryKey: ['growth-exams'] })
      navigate(`/student/learning/exams/${exam.id}`)
    },
  })

  if (overviewQuery.isLoading || coursesQuery.isLoading || examsQuery.isLoading) return <LoadingState />
  if (!data) return <EmptyState title="学习数据暂不可用" description="请稍后刷新页面。" />

  return (
    <div className="entry-reveal space-y-6">
      <PageHeader
        title="学习成长"
        description="把能力差距转成课程、任务证据和可追踪的 AI 测验。答题过程已独立为专注考试页面。"
        action={data.plan ? <AskAgentButton role="student" context={{ type: 'plan', id: data.plan.id }} /> : undefined}
      />

      <section className="grid border border-[#102015]/15 bg-[#f8fbf5] sm:grid-cols-4">
        {[
          ['目标岗位', data.plan?.target_role ?? '待确认'],
          ['学习任务', String(data.metrics.total_tasks)],
          ['完成率', `${data.metrics.completion_rate}%`],
          ['B站课程', `${bSiteCourseCount} 个`],
        ].map(([label, value], index) => (
          <div key={label} className={`metric-cell p-5 ${index ? 'border-t sm:border-l sm:border-t-0' : ''}`}>
            <p className="text-xs text-[#647460]">{label}</p>
            <p className="mt-2 text-2xl font-bold text-[#102015]">{value}</p>
          </div>
        ))}
      </section>

      <LearningAnalyticsCharts analytics={data.analytics} />

      <section className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
        <Panel title="优先补强">
          {data.analytics.weak_points.length ? (
            <div className="space-y-3">
              {data.analytics.weak_points.slice(0, 5).map((item) => (
                <div key={item.skill_name} className="flex items-center justify-between gap-4 border-b border-[#102015]/10 pb-3 last:border-0 last:pb-0">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-[#102015]">{item.skill_name}</p>
                    <p className="mt-1 text-xs text-[#647460]">当前 {item.current} / 目标 {item.target} · {item.evidence_count} 条有效证据</p>
                  </div>
                  <span className="shrink-0 text-sm font-bold text-[#b45309]">差距 {item.gap}</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="暂无薄弱项" description="完成能力诊断后显示优先补强方向。" />
          )}
        </Panel>
        <Panel title="能力评估口径">
          <p className="text-sm leading-6 text-[#526051]">初始诊断只作为基线；最近测验、专项训练和已提交学习证据按固定权重纳入。单纯完成任务最多带来 6 分证据修正，不会把“已完成”直接当作能力分。</p>
          <div className="mt-4 grid gap-3 md:grid-cols-2">
            {data.analytics.radar.slice(0, 4).map((item) => (
              <div key={item.skill_name} className="border-l-2 border-[#0f766e] bg-[#edf4e9] px-3 py-2">
                <p className="text-sm font-semibold text-[#102015]">{item.skill_name} · {item.current}/{item.target}</p>
                <p className="mt-1 text-xs leading-5 text-[#647460]">{item.score_reason}</p>
              </div>
            ))}
          </div>
        </Panel>
      </section>

      <section className="grid gap-5 xl:grid-cols-[0.9fr_1.1fr]">
        <Panel title="学习任务与成果证据">
          {updateTask.isError ? <Notice tone="danger">{updateTask.error.message}</Notice> : null}
          {data.tasks.length ? (
            <div className="divide-y divide-[#102015]/10">
              {data.tasks.slice(0, 6).map((task) => (
                <article key={task.id} className="py-4 first:pt-0 last:pb-0">
                  <div className="flex items-start gap-3">
                    {task.status === 'completed' ? <CheckCircle2 className="mt-0.5 shrink-0 text-emerald-700" size={18} /> : <CircleDashed className="mt-0.5 shrink-0 text-amber-700" size={18} />}
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-start justify-between gap-2">
                        <div>
                          <p className="text-sm font-semibold text-[#102015]">{task.title}</p>
                          <p className="mt-1 text-xs text-[#647460]">{task.skill_name} · 截止 {task.due_date}{task.course_title ? ` · ${task.course_title}` : ''}</p>
                        </div>
                        <AskAgentButton role="student" context={{ type: 'learning_task', id: task.id }} className="h-8 px-2 text-xs" />
                      </div>
                      <p className="mt-2 text-xs leading-5 text-[#526051]">验收：{task.acceptance_criteria}</p>
                      {task.completion_note ? <p className="mt-2 border-l-2 border-emerald-600 bg-emerald-50 px-3 py-2 text-xs text-emerald-950">成果：{task.completion_note}</p> : null}
                      {editing === task.id ? (
                        <div className="mt-3">
                          <textarea aria-label="成果说明" value={evidence} onChange={(event) => setEvidence(event.target.value)} rows={3} placeholder="写明完成内容、练习数量、验证结果或成果链接" className="input-prism w-full rounded-md border px-3 py-2 text-sm outline-none" />
                          <div className="mt-2 flex gap-2">
                            <button className={primaryButton} disabled={evidence.trim().length < 5 || updateTask.isPending} onClick={() => updateTask.mutate({ id: task.id, status: 'completed', completionNote: evidence.trim() })}><BookOpenCheck size={16} />提交成果</button>
                            <button className={secondaryButton} onClick={() => { setEditing(null); setEvidence('') }}>取消</button>
                          </div>
                        </div>
                      ) : task.status !== 'completed' ? (
                        <div className="mt-3 flex flex-wrap gap-2">
                          <button className={secondaryButton} onClick={() => updateTask.mutate({ id: task.id, status: 'in_progress' })}><Target size={16} />标记进行中</button>
                          <button className={primaryButton} onClick={() => setEditing(task.id)}><CheckCircle2 size={16} />完成并提交证据</button>
                        </div>
                      ) : null}
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : <EmptyState title="暂无学习任务" description="让学习成长 Agent 根据技能差距创建计划。" />}
        </Panel>

        <Panel title="课程资源">
          {coursesQuery.isError ? <Notice tone="danger">{coursesQuery.error.message}</Notice> : null}
          {courses.length ? (
            <div className="grid gap-3 md:grid-cols-2">
              {courses.slice(0, 6).map((course) => (
                <article key={course.id} className={`border p-4 transition ${selectedCourse?.id === course.id ? 'border-[#0f766e] bg-[#edf7f1]' : 'border-[#102015]/15 bg-white/60'}`}>
                  <label className="flex cursor-pointer items-start gap-3">
                    <input type="radio" checked={selectedCourse?.id === course.id} onChange={() => setSelectedCourseId(course.id)} className="mt-1 accent-[#0f766e]" />
                    <span className="min-w-0"><span className="block text-sm font-semibold text-[#102015]">{course.title}</span><span className="mt-1 block text-xs text-[#647460]">{course.provider} · 约 {course.duration_minutes} 分钟</span></span>
                  </label>
                  <p className="mt-3 line-clamp-3 text-xs leading-5 text-[#526051]">{course.description}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">{course.skills.map((skill) => <span key={skill} className="bg-[#e6eee1] px-2 py-1 text-[11px] text-[#526051]">{skill}</span>)}</div>
                  {course.source_url ? <a className={`${secondaryButton} mt-4 h-9 w-full text-xs`} href={course.source_url} target="_blank" rel="noreferrer"><ExternalLink size={15} />打开课程</a> : null}
                </article>
              ))}
            </div>
          ) : <EmptyState title="暂无课程资源" description="运行种子数据后会显示公开课程入口。" />}
        </Panel>
      </section>

      <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="AI 出题考试">
          {createExam.isError ? <Notice tone="danger">{createExam.error.message}</Notice> : null}
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[#102015]/10 pb-4">
            <div>
              <p className="text-sm font-semibold text-[#102015]">为当前课程生成一份可追踪测验</p>
              <p className="mt-1 text-xs leading-5 text-[#647460]">题目由 Agent 生成并写入数据库，答题和评分在独立页面完成。</p>
            </div>
            <button className={primaryButton} disabled={!selectedCourse && !recommendedTask || createExam.isPending} onClick={() => createExam.mutate()}><BrainCircuit size={16} />{createExam.isPending ? '正在生成题目...' : 'AI 出题并开始'}</button>
          </div>
          <div className="mt-4 flex items-center gap-2 text-xs text-[#647460]"><ListChecks size={15} />当前范围：{selectedCourse?.title ?? recommendedTask?.title ?? '就业能力'} · 5 题 · 限时 20 分钟</div>
        </Panel>

        <Panel title="历史考试">
          {examsQuery.data?.length ? <div className="space-y-2">{examsQuery.data.slice(0, 5).map((exam) => <button key={exam.id} className="flex w-full items-center justify-between gap-3 border border-[#102015]/15 bg-white/60 px-3 py-3 text-left transition hover:border-[#0f766e] hover:bg-[#edf7f1]" onClick={() => navigate(`/student/learning/exams/${exam.id}`)}><span className="min-w-0"><span className="block truncate text-sm font-semibold text-[#102015]">{exam.title}</span><span className="mt-1 block text-xs text-[#647460]">{exam.skill_name} · {exam.question_count} 题 · {examStatusLabel(exam.status, exam.latest_score)}</span></span><ArrowUpRight className="shrink-0 text-[#0f766e]" size={17} /></button>)}</div> : <EmptyState title="还没有考试记录" description="先选择课程，生成第一份 AI 测验。" />}
        </Panel>
      </section>

      <p className="flex items-center gap-2 text-xs text-[#647460]"><ArrowUpRight size={14} />错题和收藏会在独立考试页查看，避免学习概览继续堆叠答题内容。</p>
    </div>
  )
}
