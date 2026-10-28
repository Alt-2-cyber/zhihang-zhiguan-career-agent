import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  AlertTriangle,
  ArrowLeft,
  ArrowRight,
  BriefcaseBusiness,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ClipboardList,
  CircleDot,
  FileCheck2,
  FileText,
  ListChecks,
  Mic,
  Pause,
  PlayCircle,
  RefreshCw,
  RotateCcw,
  Save,
  SendHorizontal,
  Sparkles,
  ShieldAlert,
  Square,
  Target,
  Users,
  UsersRound,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { apiFetch, apiFetchBlob } from '../../app/api'
import { EmptyState, LoadingState, Notice, PageHeader, Panel, primaryButton, secondaryButton } from '../../components/Ui'
import { AskAgentButton } from '../chat/AskAgentButton'
import { useAudioRecorder } from '../chat/useAudioRecorder'
import { DigitalHumanStage } from './DigitalHumanStage'
import { isPostHireMode, isPreHireMode, phaseLabel, type SimulationMode } from './training-phases'

type Mode = SimulationMode
type PressureLevel = 'light' | 'medium' | 'high'
type ControlRequest = {
  action: 'pause' | 'resume' | 'lower_pressure' | 'set_pressure' | 'stop' | 'complete'
  pressure_level?: PressureLevel
}
type Scenario = {
  id: string
  title: string
  category: string
  difficulty: string
  description: string
  mode: Mode
  competencies: string[]
  step_count: number
  stages: { key: string; title: string }[]
  phase?: 'pre_hire' | 'post_hire'
  work_context?: WorkContext
}
type WorkContext = {
  role?: string
  stage?: string
  objective?: string
  stakeholders?: string[]
  deliverables?: string[]
  deadline?: string
  acceptance_criteria?: string[]
  constraints?: string[]
  workflow?: string[]
}
type Material = {
  id?: string
  source_type: string
  source_id: string
  source_name: string
  purpose?: string
  ready?: boolean
}
type Turn = {
  id: string
  sequence: number
  prompt: string
  response: string
  score: number
  feedback: { dimensions?: Record<string, number>; strengths?: string[]; improvements?: string[]; agent_feedback?: string[] }
}
type SimulationMessage = {
  id: string
  sequence: number
  speaker: string
  display_name: string
  stage: string
  content: string
  reply_to: string | null
}
type Report = {
  average_dimensions?: Record<string, number>
  strengths?: string[]
  improvements?: string[]
  evidence?: { turn: number; score: number; response_excerpt: string }[]
}
type SimulationSession = {
  id: string
  status: 'active' | 'paused' | 'completed' | 'stopped'
  mode: Mode
  stage: string
  stress_level: 'light' | 'medium' | 'high'
  current_step: number
  score: number | null
  assessment: { summary?: string; next_action?: string } | null
  report: Report | null
  scenario: Scenario
  current_prompt: string | null
  turns: Turn[]
  messages: SimulationMessage[]
  materials: Material[]
  phase?: 'pre_hire' | 'post_hire'
  work_context?: WorkContext
  deliverables: WorkplaceDeliverable[]
}
type WorkplaceActionType = 'clarify_questions' | 'action_plan' | 'risk_register' | 'meeting_minutes' | 'weekly_report' | 'delivery_draft'
type WorkplaceDeliverable = {
  id: string
  session_id: string
  action_type: WorkplaceActionType
  action_label: string
  title: string
  content: string
  status: 'draft' | 'submitted' | 'reviewed'
  revision: number
  reviewer_feedback: string | null
  review: { score?: number; dimensions?: Record<string, number>; strengths?: string[]; improvements?: string[] } | null
  submitted_at: string | null
  updated_at: string
}
type AiTask = {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  result?: { text?: string; artifact_id?: string; media_type?: string }
  error?: { message?: string } | null
}

const modeLabel: Record<Mode, string> = {
  workplace: '入职后职场情景',
  group_interview: '无领导群面',
  stress_interview: '压力面试',
  presentation_defense: '路演答辩',
  career_planning: '职业规划',
}

const difficultyLabel: Record<string, string> = { easy: '基础', medium: '进阶', hard: '挑战' }
const pressureLabel: Record<PressureLevel, string> = { light: '低', medium: '中', high: '高' }
const workplaceActionLabel: Record<WorkplaceActionType, string> = {
  clarify_questions: '任务澄清',
  action_plan: '行动计划',
  risk_register: '风险清单',
  meeting_minutes: '会议纪要',
  weekly_report: '周报汇报',
  delivery_draft: '交付草案',
}
const workplaceDimensionLabel: Record<string, string> = {
  objective_understanding: '目标理解',
  actionability: '行动可执行',
  risk_awareness: '风险意识',
  stakeholder_alignment: '协作对齐',
  delivery_quality: '交付质量',
  evidence_quality: '证据质量',
}
const dimensionLabel: Record<string, string> = { structure: '结构', evidence: '证据', collaboration: '协作', completeness: '完整度' }
const messageTone: Record<string, string> = {
  interviewer: 'border-[#ff7358]/35 bg-[#fff0eb] text-[#702314]',
  reviewer: 'border-[#ff7358]/35 bg-[#fff0eb] text-[#702314]',
  career_coach: 'border-[#38642f]/30 bg-[#e3f6ce] text-[#30442f]',
  candidate_logic: 'border-[#102015]/20 bg-[#edf2e9] text-[#102015]',
  candidate_collaboration: 'border-emerald-700/25 bg-emerald-50 text-emerald-950',
  candidate_challenger: 'border-[#102015]/20 bg-[#edf2e9] text-[#102015]',
}

function sessionStatusLabel(status: SimulationSession['status']) {
  if (status === 'completed') return '已完成'
  if (status === 'paused') return '已暂停'
  if (status === 'stopped') return '已停止'
  return '进行中'
}

function ScenarioRow({ scenario, selected, onSelect }: { scenario: Scenario; selected: boolean; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={`group grid w-full gap-4 border-l-2 px-4 py-4 text-left transition sm:grid-cols-[minmax(0,1fr)_180px_auto] sm:items-center ${selected ? 'border-[#4f7e20] bg-[#e3f6ce]' : 'border-transparent bg-white hover:border-[#4f7e20] hover:bg-[#f1f7ec]'}`}
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-3">
          <p className="truncate text-sm font-extrabold text-[#102015]">{scenario.title}</p>
          <span className="text-[11px] font-bold text-[#647460]">{difficultyLabel[scenario.difficulty] ?? scenario.difficulty}</span>
        </div>
        <p className="mt-1 line-clamp-2 text-xs leading-5 text-[#647460]">{scenario.description}</p>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {scenario.competencies.slice(0, 3).map((item) => <span key={item} className="border border-[#102015]/12 bg-[#f8fbf5] px-2 py-1 text-[11px] font-semibold text-[#526051]">{item}</span>)}
      </div>
      <ArrowRight className="text-[#38642f] transition group-hover:translate-x-1" size={17} />
    </button>
  )
}

function WorkMetric({ label, value, detail }: { label: string; value: string; detail: string }) {
  return <div className="border-l border-[#102015]/15 pl-4 first:border-l-0 first:pl-0">
    <p className="text-[11px] font-bold tracking-[0.08em] text-[#647460]">{label}</p>
    <p className="mt-1 text-2xl font-extrabold text-[#102015]">{value}</p>
    <p className="mt-1 text-xs text-[#647460]">{detail}</p>
  </div>
}

function WorkBriefList({ label, items, fallback, danger = false }: { label: string; items?: string[]; fallback: string; danger?: boolean }) {
  return <div className="border-t border-[#102015]/10 pt-4">
    <div className="flex items-center gap-2 text-xs font-extrabold text-[#30442f]">
      {danger ? <ShieldAlert size={15} className="text-[#b54b32]" /> : <CheckCircle2 size={15} className="text-[#4f7e20]" />}
      {label}
    </div>
    {items?.length ? <ul className="mt-2 space-y-1.5 text-xs leading-5 text-[#526051]">{items.map((item) => <li key={item} className="flex gap-2"><span className={`mt-2 size-1.5 shrink-0 rounded-full ${danger ? 'bg-[#b54b32]' : 'bg-[#4f7e20]'}`} />{item}</li>)}</ul> : <p className="mt-2 text-xs leading-5 text-[#647460]">{fallback}</p>}
  </div>
}

export function WorkplacePage({ token }: { token: string }) {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const modeFilter = searchParams.get('mode')
  const selectedMode = isPostHireMode(modeFilter) ? modeFilter : null
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null)
  const scenarios = useQuery({ queryKey: ['workplace-scenarios', 'post_hire'], queryFn: () => apiFetch<Scenario[]>('/workplace/scenarios?phase=post_hire', {}, token) })
  const sessions = useQuery({ queryKey: ['workplace-sessions', 'post_hire'], queryFn: () => apiFetch<SimulationSession[]>('/workplace/sessions?phase=post_hire', {}, token) })

  useEffect(() => {
    if (modeFilter === 'structured' || isPreHireMode(modeFilter)) {
      navigate(`/student/interview?mode=${modeFilter}`, { replace: true })
    }
  }, [modeFilter, navigate])
  const start = useMutation({
    mutationFn: (scenarioId: string) => apiFetch<SimulationSession>(`/workplace/scenarios/${scenarioId}/sessions`, { method: 'POST' }, token),
    onSuccess: (session) => {
      void Promise.all([
        queryClient.invalidateQueries({ queryKey: ['workplace-sessions'] }),
        queryClient.invalidateQueries({ queryKey: ['workplace-reports'] }),
      ])
      navigate(`/student/workplace/session/${session.id}`)
    },
  })
  const visibleScenarios = useMemo(() => {
    const source = scenarios.data ?? []
    return source.filter((item) => isPostHireMode(item.mode) && (!selectedMode || item.mode === selectedMode))
  }, [scenarios.data, selectedMode])
  const selectedScenario = visibleScenarios.find((item) => item.id === selectedScenarioId) ?? visibleScenarios[0] ?? null
  const visibleSessions = useMemo(() => (sessions.data ?? []).filter((session) => isPostHireMode(session.mode)), [sessions.data])
  const resumableSession = selectedScenario
    ? sessions.data?.find((session) => session.scenario.id === selectedScenario.id && (session.status === 'active' || session.status === 'paused')) ?? null
    : null
  const selectedContext = selectedScenario?.work_context ?? {}
  const workflow = (selectedContext.workflow ?? []).filter((item): item is WorkplaceActionType => item in workplaceActionLabel)
  const activeSession = visibleSessions.find((session) => session.status === 'active' || session.status === 'paused') ?? null
  const allDeliverables = visibleSessions.flatMap((session) => session.deliverables ?? [])
  const submittedDeliverables = allDeliverables.filter((item) => item.status !== 'draft')
  const reviewedScores = submittedDeliverables.map((item) => item.review?.score).filter((score): score is number => typeof score === 'number')
  const averageScore = reviewedScores.length ? String(Math.round(reviewedScores.reduce((sum, score) => sum + score, 0) / reviewedScores.length)) : '--'
  const completedSessionCount = visibleSessions.filter((session) => session.status === 'completed').length
  const selectedSessionDeliverables = resumableSession?.deliverables ?? []
  const selectedCompletedActions = new Set(selectedSessionDeliverables.filter((item) => item.status !== 'draft').map((item) => item.action_type))

  const enterTraining = () => {
    if (!selectedScenario) return
    if (resumableSession) {
      navigate(`/student/workplace/session/${resumableSession.id}`)
      return
    }
    start.mutate(selectedScenario.id)
  }

  const retry = () => {
    void Promise.all([scenarios.refetch(), sessions.refetch()])
  }

  if (scenarios.isLoading || sessions.isLoading) return <LoadingState />

  if (scenarios.isError || sessions.isError) {
    return (
      <div className="entry-reveal">
        <PageHeader title="职场训练" description="训练数据未能加载；这不代表没有可选场景。恢复服务后可在此继续进入或新建训练。" />
        <Panel title="训练服务暂时不可用" className="max-w-3xl">
          <Notice tone="danger">无法连接训练数据服务，请稍后重新加载。</Notice>
          <button type="button" className={`${primaryButton} mt-5`} onClick={retry}>重新加载训练数据</button>
        </Panel>
      </div>
    )
  }

  return (
    <div className="entry-reveal space-y-6">
      <PageHeader
        title="职场工作台"
        description="把入职后的工作目标拆成可执行的行动、可交付的成果和可复盘的证据。这里不进行面试问答，而是处理真实工作任务。"
        action={activeSession ? <AskAgentButton role="student" context={{ type: 'workplace_session', id: activeSession.id }} /> : undefined}
      />
      {start.isError ? <Notice tone="danger">{start.error.message}</Notice> : null}

      <section className="border border-[#102015] bg-[#102015] p-1 shadow-[7px_7px_0_rgba(16,32,21,0.14)]">
        <div className="grid gap-px bg-[#102015] lg:grid-cols-[minmax(0,1.35fr)_minmax(300px,0.65fr)]">
          <div className="bg-[#e3f6ce] p-6 sm:p-8">
            <div className="flex flex-wrap items-center gap-3 text-xs font-extrabold text-[#38642f]">
              <span className="inline-flex items-center gap-2"><BriefcaseBusiness size={15} />POST-HIRE WORKSPACE</span>
              <span className="border border-[#38642f]/25 bg-white/70 px-2 py-1">真实工作任务</span>
            </div>
            <h2 className="mt-5 max-w-3xl text-3xl font-extrabold leading-tight text-[#102015] sm:text-4xl">{selectedContext.objective ?? '从一份清晰的工作简报开始。'}</h2>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-[#526051]">{selectedScenario?.description ?? '选择一个工作场景，系统会生成岗位上下文、协作对象、验收标准和交付路径。'}</p>
            <div className="mt-7 flex flex-wrap items-center gap-3">
              <button type="button" className={primaryButton} onClick={enterTraining} disabled={!selectedScenario || start.isPending}><PlayCircle size={17} />{start.isPending ? '正在创建任务' : resumableSession ? '继续当前任务' : '进入工作任务台'}</button>
              {resumableSession ? <span className="inline-flex items-center gap-2 text-xs font-bold text-[#38642f]"><RotateCcw size={14} />已有任务 {sessionStatusLabel(resumableSession.status)}</span> : <span className="text-xs text-[#526051]">选择场景后开始一份独立工作会话</span>}
            </div>
          </div>
          <div className="bg-[#f8fbf5] p-6 sm:p-8">
            <p className="text-[11px] font-bold tracking-[0.14em] text-[#4f7e20]">CURRENT BRIEF</p>
            <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-1">
              <BriefFact icon={<BriefcaseBusiness size={15} />} label="岗位 / 阶段" value={`${selectedContext.role ?? '待确认'} · ${selectedContext.stage ?? '待确认'}`} />
              <BriefFact icon={<CalendarDays size={15} />} label="交付截止" value={selectedContext.deadline ?? '先与主管确认'} />
              <BriefFact icon={<Users size={15} />} label="协作对象" value={selectedContext.stakeholders?.length ? selectedContext.stakeholders.join('、') : '待确认协作方'} />
              <BriefFact icon={<FileCheck2 size={15} />} label="交付物" value={selectedContext.deliverables?.length ? selectedContext.deliverables.join('、') : '待确认交付物'} />
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-3 border-y border-[#102015]/15 py-5 sm:grid-cols-2 xl:grid-cols-4">
        <WorkMetric label="可用工作场景" value={String(visibleScenarios.length)} detail="按入职后的工作问题组织" />
        <WorkMetric label="进行中的任务" value={String(visibleSessions.filter((session) => session.status === 'active' || session.status === 'paused').length)} detail="可继续的工作会话" />
        <WorkMetric label="已提交交付物" value={String(submittedDeliverables.length)} detail="已进入结构化评审" />
        <WorkMetric label="平均工作评分" value={averageScore} detail={reviewedScores.length ? `${reviewedScores.length} 份评审结果` : '完成提交后生成'} />
      </div>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section className="panel-prism border p-0">
          <div className="flex items-start justify-between gap-4 border-b border-[#102015]/10 bg-[#edf2e9] px-5 py-5 sm:px-7">
            <div><p className="text-[11px] font-bold tracking-[0.14em] text-[#4f7e20]">WORK PLAN</p><h2 className="mt-1 text-xl font-extrabold text-[#102015]">工作简报与验收标准</h2></div>
            <span className="grid size-10 place-items-center border border-[#102015]/15 bg-white text-[#38642f]"><ClipboardList size={19} /></span>
          </div>
          <div className="grid gap-5 p-5 sm:p-7 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <p className="text-xs font-extrabold text-[#38642f]">本次工作目标</p>
              <p className="mt-2 text-sm font-bold leading-6 text-[#102015]">{selectedContext.objective ?? '选择工作场景后，目标会从服务端简报加载。'}</p>
              <WorkBriefList label="验收标准" items={selectedContext.acceptance_criteria} fallback="提交前先确认可验证的验收标准。" />
              <WorkBriefList label="约束与风险" items={selectedContext.constraints} fallback="当前没有额外约束，仍需在执行中记录新风险。" danger />
            </div>
            <div className="border-l border-[#102015]/10 pl-0 lg:pl-5">
              <p className="text-xs font-extrabold text-[#38642f]">行动路径</p>
              <div className="mt-3 space-y-2">
                {(workflow.length ? workflow : (Object.keys(workplaceActionLabel) as WorkplaceActionType[])).map((item, index) => {
                  const done = selectedCompletedActions.has(item)
                  return <div key={item} className={`flex items-center gap-3 border px-3 py-2.5 text-xs ${done ? 'border-[#4f7e20]/35 bg-[#e3f6ce] text-[#30442f]' : 'border-[#102015]/12 bg-white text-[#526051]'}`}><span className={`grid size-6 place-items-center text-[11px] font-extrabold ${done ? 'bg-[#4f7e20] text-white' : 'bg-[#edf2e9] text-[#38642f]'}`}>{done ? <CheckCircle2 size={14} /> : index + 1}</span><span className="font-bold">{workplaceActionLabel[item]}</span><span className="ml-auto text-[11px] text-[#647460]">{done ? '已提交' : '待处理'}</span></div>
                })}
              </div>
            </div>
          </div>
        </section>
        <aside className="border border-[#102015] bg-[#102015] p-6 text-[#f8fbf5] shadow-[6px_6px_0_rgba(16,32,21,0.14)]">
          <p className="text-[11px] font-bold tracking-[0.14em] text-[#c7ff4c]">POST-HIRE SIGNALS</p>
          <h2 className="mt-4 text-2xl font-extrabold">工作能力闭环</h2>
          <p className="mt-3 text-sm leading-6 text-[#b8c6b5]">工作台只记录真实简报、交付版本和后端评审，不把工作任务伪装成面试题。</p>
          <div className="mt-6 space-y-3 border-t border-white/10 pt-5 text-sm">
            <div className="flex items-center justify-between gap-4"><span className="text-[#b8c6b5]">已完成场景</span><strong className="text-[#c7ff4c]">{completedSessionCount}</strong></div>
            <div className="flex items-center justify-between gap-4"><span className="text-[#b8c6b5]">当前任务状态</span><strong className="text-white">{activeSession ? sessionStatusLabel(activeSession.status) : '未开始'}</strong></div>
            <div className="flex items-center justify-between gap-4"><span className="text-[#b8c6b5]">可追溯交付版本</span><strong className="text-white">{allDeliverables.length}</strong></div>
          </div>
          <button type="button" className="mt-7 inline-flex w-full items-center justify-center gap-2 border border-[#c7ff4c] bg-[#c7ff4c] px-4 py-3 text-sm font-extrabold text-[#102015] transition hover:bg-white" onClick={enterTraining} disabled={!selectedScenario || start.isPending}><PlayCircle size={17} />{resumableSession ? '继续当前任务' : '开始一份工作任务'}</button>
        </aside>
      </div>

      <section className="border border-[#102015]/18 bg-[#f8fbf5] shadow-[4px_4px_0_rgba(16,32,21,0.08)]">
        <div className="flex flex-wrap items-end justify-between gap-4 border-b border-[#102015]/10 px-5 py-5 sm:px-7">
          <div><p className="text-[11px] font-bold tracking-[0.14em] text-[#4f7e20]">WORK SCENARIO LIBRARY</p><h2 className="mt-1 text-xl font-extrabold text-[#102015]">选择一个工作问题</h2><p className="mt-1 text-xs text-[#647460]">场景只描述入职后的工作任务；进入后会生成独立简报和交付记录。</p></div>
          <span className="text-xs font-bold text-[#647460]">{visibleScenarios.length} 个场景</span>
        </div>
        {visibleScenarios.length ? <div className="divide-y divide-[#102015]/10">{visibleScenarios.map((scenario) => <ScenarioRow key={scenario.id} scenario={scenario} selected={selectedScenario?.id === scenario.id} onSelect={() => setSelectedScenarioId(scenario.id)} />)}</div> : <div className="p-5"><EmptyState title={selectedMode ? `${modeLabel[selectedMode]}暂未配置训练场景` : '暂未配置入职后训练场景'} description="训练场景准备完成后会显示在这里。" /></div>}
      </section>

      {visibleSessions.length ? (
        <Panel title="最近工作记录">
          <div className="divide-y divide-[#102015]/10">
            {visibleSessions.map((session) => {
              const submitted = (session.deliverables ?? []).filter((item) => item.status !== 'draft').length
              return <button key={session.id} type="button" onClick={() => navigate(`/student/workplace/session/${session.id}`)} className="group flex w-full items-center justify-between gap-4 py-4 text-left first:pt-0 last:pb-0">
                <div className="min-w-0"><p className="truncate text-sm font-extrabold text-[#102015] group-hover:text-[#38642f]">{session.scenario.title}</p><p className="mt-1 text-xs text-[#647460]">{sessionStatusLabel(session.status)} · {submitted} 份已提交交付物 · {session.score ?? '待评审'}</p></div>
                <ArrowRight size={16} className="shrink-0 text-[#38642f] transition group-hover:translate-x-1" />
              </button>
            })}
          </div>
        </Panel>
      ) : null}
    </div>
  )
}

export function WorkplaceSessionPage({ token }: { token: string }) {
  const { sessionId } = useParams<{ sessionId: string }>()
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const [response, setResponse] = useState('')
  const [transcriptionTaskId, setTranscriptionTaskId] = useState<string | null>(null)
  const [speechTaskId, setSpeechTaskId] = useState<string | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [mediaError, setMediaError] = useState('')
  const appliedTranscriptRef = useRef<string | null>(null)
  const spokenPromptRef = useRef<string | null>(null)
  const audioUrlRef = useRef<string | null>(null)
  const sessions = useQuery({ queryKey: ['workplace-sessions', 'all'], queryFn: () => apiFetch<SimulationSession[]>('/workplace/sessions', {}, token) })
  const materials = useQuery({ queryKey: ['workplace-materials'], queryFn: () => apiFetch<Material[]>('/workplace/materials', {}, token) })
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['workplace-sessions'] }),
      queryClient.invalidateQueries({ queryKey: ['workplace-reports'] }),
    ])
  }
  const answer = useMutation({
    mutationFn: (text: string) => apiFetch<SimulationSession>(`/workplace/sessions/${sessionId}/answers`, { method: 'POST', body: JSON.stringify({ response: text }) }, token),
    onSuccess: async () => { setResponse(''); await refresh() },
  })
  const uploadRecording = useMutation({
    mutationFn: (blob: Blob) => {
      const body = new FormData()
      body.append('file', blob, 'training-answer.webm')
      return apiFetch<{ task_id: string }>(`/workplace/sessions/${sessionId}/recordings`, { method: 'POST', body }, token)
    },
    onSuccess: (value) => {
      appliedTranscriptRef.current = null
      setTranscriptionTaskId(value.task_id)
      setMediaError('')
    },
  })
  const recorder = useAudioRecorder((blob) => uploadRecording.mutate(blob), {
    unsupported: '当前浏览器不支持录音，请直接输入回答',
    denied: '麦克风权限被拒绝，请在浏览器地址栏中允许访问后重试',
    missing: '未检测到可用麦克风，请连接设备后重新检测',
    busy: '麦克风正在被其他程序占用，请关闭占用程序后重新检测',
    failed: '麦克风启动失败，请检查系统录音设备后重新检测',
  })
  const bind = useMutation({
    mutationFn: (material: Material) => apiFetch<{ id: string }>(`/workplace/sessions/${sessionId}/materials`, { method: 'POST', body: JSON.stringify({ source_type: material.source_type, source_id: material.source_id, purpose: 'answer_context' }) }, token),
    onSuccess: refresh,
  })
  const control = useMutation({
    mutationFn: (payload: ControlRequest) => apiFetch<SimulationSession>(`/workplace/sessions/${sessionId}/controls`, { method: 'POST', body: JSON.stringify(payload) }, token),
    onSuccess: refresh,
  })
  const selectedSession = sessions.data?.find((session) => session.id === sessionId) ?? null
  const transcription = useQuery({
    queryKey: ['ai-task', transcriptionTaskId],
    queryFn: () => apiFetch<AiTask>(`/ai/tasks/${transcriptionTaskId}`, {}, token),
    enabled: Boolean(transcriptionTaskId),
    refetchInterval: (query) => query.state.data && ['queued', 'running'].includes(query.state.data.status) ? 1_000 : false,
  })
  const speech = useQuery({
    queryKey: ['ai-task', speechTaskId],
    queryFn: () => apiFetch<AiTask>(`/ai/tasks/${speechTaskId}`, {}, token),
    enabled: Boolean(speechTaskId),
    refetchInterval: (query) => query.state.data && ['queued', 'running'].includes(query.state.data.status) ? 1_000 : false,
  })

  useEffect(() => {
    const task = transcription.data
    if (transcriptionTaskId && task?.status === 'succeeded' && task.result?.text !== undefined && appliedTranscriptRef.current !== transcriptionTaskId) {
      appliedTranscriptRef.current = transcriptionTaskId
      setResponse(task.result.text)
    }
  }, [transcription.data, transcriptionTaskId])

  useEffect(() => {
    const prompt = selectedSession?.current_prompt
    if (selectedSession?.mode === 'workplace') return
    if (!sessionId || !prompt || selectedSession?.status !== 'active' || spokenPromptRef.current === prompt) return
    spokenPromptRef.current = prompt
    setSpeechTaskId(null)
    apiFetch<{ task_id: string }>(`/workplace/sessions/${sessionId}/speech`, { method: 'POST', body: JSON.stringify({ text: prompt }) }, token)
      .then((result) => { setSpeechTaskId(result.task_id); setMediaError('') })
      .catch((error: Error) => setMediaError(error.message || '数字人语音生成失败'))
  }, [selectedSession?.current_prompt, selectedSession?.status, sessionId, token])

  useEffect(() => {
    const artifactId = speech.data?.status === 'succeeded' ? speech.data.result?.artifact_id : undefined
    if (!artifactId || audioUrlRef.current === artifactId) return
    let cancelled = false
    audioUrlRef.current = artifactId
    apiFetchBlob(`/ai/media/${artifactId}`, token).then((blob) => {
      if (cancelled) return
      setAudioUrl((previous) => {
        if (previous) URL.revokeObjectURL(previous)
        return URL.createObjectURL(blob)
      })
    }).catch(() => { if (!cancelled) setMediaError('AI 语音加载失败，可直接阅读文字问题') })
    return () => { cancelled = true }
  }, [speech.data, token])

  useEffect(() => () => {
    if (audioUrl) URL.revokeObjectURL(audioUrl)
    audioUrlRef.current = null
  }, [audioUrl])

  if (sessions.isLoading || materials.isLoading) return <LoadingState />
  if (!selectedSession) {
    return (
      <div className="entry-reveal">
        <PageHeader title="训练会话不存在" description="该训练可能已不可用，或你没有访问权限。" />
        <button type="button" className={secondaryButton} onClick={() => navigate('/student/workplace')}><ArrowLeft size={16} />返回入职后训练</button>
      </div>
    )
  }

  if (selectedSession.mode === 'workplace') {
    return <WorkplaceTaskSessionView token={token} session={selectedSession} onRefresh={refresh} />
  }

  const isPreHireSession = isPreHireMode(selectedSession.mode)
  const sessionEntryPath = isPreHireSession ? '/student/interview' : '/student/workplace'
  const sessionEntryLabel = isPreHireSession ? '返回入职前模拟面试' : '返回入职后训练'
  const currentStageIndex = selectedSession.scenario.stages.findIndex((stage) => stage.key === selectedSession.stage)
  const availableMaterials = materials.data?.filter((item) => !selectedSession.materials.some((bound) => bound.source_id === item.source_id)) ?? []
  const isLive = selectedSession.status === 'active' || selectedSession.status === 'paused'

  return (
    <div className="entry-reveal">
      <section className="signal-grid border border-[#102015] bg-[#f8fbf5] px-5 py-6 text-[#102015] shadow-[7px_7px_0_rgba(16,32,21,0.14)] sm:px-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <button type="button" className="inline-flex items-center gap-2 text-sm font-bold text-[#526051] hover:text-[#38642f]" onClick={() => navigate(sessionEntryPath)}><ArrowLeft size={16} />{sessionEntryLabel}</button>
            <h1 className="mt-5 text-3xl font-extrabold leading-9 sm:text-4xl">{selectedSession.scenario.title}</h1>
            <p className="mt-2 text-sm text-[#526051]">{isPreHireSession ? phaseLabel.preHire : phaseLabel.postHire} · {modeLabel[selectedSession.mode]} · {sessionStatusLabel(selectedSession.status)} · 第 {Math.max(1, selectedSession.current_step + 1)} / {selectedSession.scenario.step_count} 阶段</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="border border-[#102015]/15 bg-[#e7f1df] px-4 py-2 text-right">
              <p className="text-[10px] font-bold tracking-[0.12em] text-[#526051]">综合评分</p>
              <p className="mt-1 text-2xl font-extrabold text-[#38642f]">{selectedSession.score ?? '--'}</p>
            </div>
            <AskAgentButton role="student" context={{ type: 'workplace_session', id: selectedSession.id }} className="border-[#102015]/20 bg-[#102015] text-white hover:border-[#38642f] hover:bg-[#38642f]" />
          </div>
        </div>
      </section>

      {(answer.isError || control.isError || bind.isError) ? <div className="mt-5"><Notice tone="danger">{answer.error?.message ?? control.error?.message ?? bind.error?.message}</Notice></div> : null}

      <div className="mt-6 grid gap-6 lg:grid-cols-[minmax(0,1fr)_310px]">
        <main className="min-w-0">
          <section className="border border-[#102015] bg-[#f8fbf5] p-0 shadow-[7px_7px_0_rgba(16,32,21,0.12)]">
            <DigitalHumanStage
              modeLabel={modeLabel[selectedSession.mode]}
              question={selectedSession.current_prompt}
              state={selectedSession.status === 'completed' ? 'complete' : answer.isPending ? 'thinking' : recorder.recording ? 'listening' : selectedSession.current_prompt ? 'speaking' : 'idle'}
              audioUrl={audioUrl}
              audioLoading={Boolean(speechTaskId && !speech.data?.result?.artifact_id && speech.data?.status !== 'failed')}
              audioError={speech.data?.status === 'failed' ? '数字人语音生成失败' : null}
            />
            {selectedSession.status === 'active' && selectedSession.current_prompt ? <div className="border-t border-[#102015]/12 p-5 sm:p-7">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <label className="text-sm font-bold text-[#30442f]" htmlFor="workplace-response">你的回答</label>
                <span className="text-xs text-[#647460]">语音会先转写到输入框，确认后再提交给评分 Agent。</span>
              </div>
              {mediaError ? <div className="mt-4"><Notice tone="warning">{mediaError}</Notice></div> : null}
              {recorder.error ? <div className="mt-4"><Notice tone="warning"><div><p>{recorder.error}</p><button type="button" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold underline" onClick={() => void recorder.start()}><RefreshCw size={13} />重新检测麦克风</button></div></Notice></div> : null}
              {transcription.data?.status === 'failed' ? <div className="mt-4"><Notice tone="danger">录音转写失败，请直接输入回答。</Notice></div> : null}
              <div className="mt-4 flex flex-wrap items-center gap-2">
                {recorder.recording ? <button type="button" className={secondaryButton} aria-label="停止录音" onClick={recorder.stop}><Square size={15} />停止录音</button> : <button type="button" className={secondaryButton} aria-label="开始录音" disabled={answer.isPending || uploadRecording.isPending || transcription.data?.status === 'queued' || transcription.data?.status === 'running'} onClick={() => void recorder.start()}><Mic size={15} />开始录音</button>}
                <span className="text-xs text-[#647460]">{recorder.recording ? '正在录音' : uploadRecording.isPending ? '正在上传录音' : transcription.data?.status === 'queued' || transcription.data?.status === 'running' ? 'AI 正在转写' : '也可以直接输入文字'}</span>
              </div>
              <textarea id="workplace-response" aria-label="训练回答" value={response} onChange={(event) => setResponse(event.target.value)} rows={5} placeholder="按照真实经历作答，写明目标、行动、协作对象和可验证结果。" className="input-prism mt-3 w-full resize-y rounded-md border px-4 py-3 text-sm leading-6 text-[#102015] outline-none" />
              <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                <p className="text-xs text-[#647460]">至少输入 20 个字符后可提交本轮回答。</p>
                <button type="button" className={primaryButton} disabled={response.trim().length < 20 || answer.isPending} onClick={() => answer.mutate(response.trim())}><SendHorizontal size={17} />{answer.isPending ? 'AI 正在评分' : '提交本轮回答'}</button>
              </div>
            </div> : null}
          </section>

          {selectedSession.status === 'paused' ? <Notice tone="warning"><div className="flex flex-wrap items-center justify-between gap-3"><span className="inline-flex items-center gap-2"><Pause size={16} />训练已暂停，现有记录已保存。</span><button type="button" className={secondaryButton} disabled={control.isPending} onClick={() => control.mutate({ action: 'resume' })}>恢复训练</button></div></Notice> : null}
          {selectedSession.status === 'completed' ? <ReportView report={selectedSession.report} assessment={selectedSession.assessment} /> : null}
          {selectedSession.status === 'stopped' ? <Notice tone="warning"><AlertTriangle size={16} />{selectedSession.assessment?.summary ?? '训练已停止，之前的记录仍可查看。'}</Notice> : null}

          {selectedSession.turns.length ? (
            <details className="group mt-6 border border-[#102015]/20 bg-[#f8fbf5]">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-extrabold text-[#102015] [&::-webkit-details-marker]:hidden"><span>已完成回合 · {selectedSession.turns.length}</span><ChevronDown size={18} className="transition group-open:rotate-180" /></summary>
              <div className="divide-y divide-[#102015]/10 border-t border-[#102015]/10 px-5">
                {selectedSession.turns.map((turn) => <article key={turn.id} className="py-5"><div className="flex items-start justify-between gap-4"><p className="text-sm font-bold text-[#102015]">第 {turn.sequence} 轮 · {turn.prompt}</p><strong className="shrink-0 text-lg text-[#38642f]">{turn.score}</strong></div><p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#526051]">{turn.response}</p>{turn.feedback.improvements?.length ? <p className="mt-3 border-l-2 border-[#ff7358] pl-3 text-xs leading-5 text-[#8c2f1f]">改进：{turn.feedback.improvements.join('；')}</p> : null}</article>)}
              </div>
            </details>
          ) : null}

          {selectedSession.messages.length ? (
            <details className="group mt-4 border border-[#102015]/20 bg-[#f8fbf5]">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-extrabold text-[#102015] [&::-webkit-details-marker]:hidden"><span className="inline-flex items-center gap-2"><UsersRound size={17} />Agent 角色交流 · {selectedSession.messages.length}</span><ChevronDown size={18} className="transition group-open:rotate-180" /></summary>
              <div className="space-y-2 border-t border-[#102015]/10 p-5">{selectedSession.messages.map((message) => <article key={message.id} className={`border p-3 text-sm leading-6 ${messageTone[message.speaker] ?? 'border-[#102015]/20 bg-[#edf2e9] text-[#102015]'}`}><p className="font-extrabold">{message.display_name}</p><p className="mt-1">{message.content}</p></article>)}</div>
            </details>
          ) : null}
        </main>

        <aside className="space-y-5">
          <section className="panel-prism overflow-hidden border p-0">
            <h2 className="border-b border-[#102015]/10 bg-[#edf2e9] px-5 py-4 text-sm font-extrabold text-[#102015]">训练进度</h2>
            <div className="p-5">
              <div className="space-y-3">
                {selectedSession.scenario.stages.map((stage, index) => {
                  const active = selectedSession.stage === stage.key
                  const complete = index < currentStageIndex || selectedSession.status === 'completed'
                  return <div key={stage.key} className={`flex items-center gap-3 border-l-2 px-3 py-2 text-sm ${active ? 'border-[#102015] bg-[#e3f6ce] font-extrabold text-[#102015]' : complete ? 'border-emerald-600 text-[#38642f]' : 'border-[#d2dbce] text-[#647460]'}`}><CircleDot size={14} />{index + 1}. {stage.title}</div>
                })}
              </div>
              {selectedSession.mode === 'stress_interview' && isLive ? (
                <div className="mt-5 border-l-2 border-[#ff7358] bg-[#fff0eb] px-3 py-3 text-xs leading-5 text-[#8c2f1f]">
                  <div className="flex items-start gap-2"><ShieldAlert size={16} className="mt-0.5 shrink-0" /><div><p className="font-extrabold">压力等级：{pressureLabel[selectedSession.stress_level]}</p><p className="mt-1 text-[#9b4b3b]">调整后会在下一轮追问中生效。</p></div></div>
                  <div className="mt-3 grid grid-cols-3 gap-2" role="group" aria-label="压力等级">
                    {(Object.keys(pressureLabel) as PressureLevel[]).map((level) => {
                      const selected = selectedSession.stress_level === level
                      return <button key={level} type="button" aria-label={`设置压力等级：${pressureLabel[level]}`} aria-pressed={selected} disabled={selected || control.isPending} onClick={() => control.mutate({ action: 'set_pressure', pressure_level: level })} className={`border px-2 py-2 text-xs font-bold transition ${selected ? 'border-[#8c2f1f] bg-[#8c2f1f] text-white' : 'border-[#ff7358]/45 bg-white/70 text-[#8c2f1f] hover:border-[#8c2f1f]'}`}>{pressureLabel[level]}</button>
                    })}
                  </div>
                </div>
              ) : null}
            </div>
          </section>
          {isLive ? (
            <section className="border border-[#102015]/20 bg-[#f8fbf5] p-5 shadow-[4px_4px_0_rgba(16,32,21,0.1)]">
              <h2 className="text-sm font-extrabold text-[#102015]">训练控制</h2>
              <div className="mt-4 grid gap-2">
                {selectedSession.status === 'active' ? <button type="button" className={secondaryButton} disabled={control.isPending} onClick={() => control.mutate({ action: 'pause' })}><Pause size={16} />暂停训练</button> : null}
                <button type="button" className={`${secondaryButton} hover:border-[#ff7358] hover:bg-[#fff0eb]`} disabled={control.isPending} onClick={() => control.mutate({ action: 'stop' })}><Square size={15} />结束训练</button>
              </div>
            </section>
          ) : null}
          {isLive ? (
            <details className="group border border-[#102015]/20 bg-[#f8fbf5] shadow-[4px_4px_0_rgba(16,32,21,0.1)]">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-5 py-4 text-sm font-extrabold text-[#102015] [&::-webkit-details-marker]:hidden"><span>材料上下文 · {selectedSession.materials.length}</span><ChevronDown size={18} className="transition group-open:rotate-180" /></summary>
              <div className="border-t border-[#102015]/10 p-5">
                <div className="space-y-2">{selectedSession.materials.map((item) => <p key={item.id ?? item.source_id} className="flex items-center gap-2 border border-[#102015]/12 bg-white px-3 py-2 text-xs text-[#526051]"><FileText size={14} />{item.source_name}</p>)}</div>
                {availableMaterials.length ? <div className="mt-4 space-y-2 border-t border-[#102015]/10 pt-4">{availableMaterials.map((item) => <button key={item.source_id} type="button" className={`${secondaryButton} h-auto w-full justify-start py-2 text-left text-xs`} disabled={bind.isPending} onClick={() => bind.mutate(item)}><FileText size={14} />绑定 {item.source_name}</button>)}</div> : null}
                {!selectedSession.materials.length && !availableMaterials.length ? <p className="text-xs leading-5 text-[#647460]">上传并解析简历后，可在此确认它用于本次训练。</p> : null}
              </div>
            </details>
          ) : null}
        </aside>
      </div>
    </div>
  )
}

function WorkplaceTaskSessionView({
  token,
  session,
  onRefresh,
}: {
  token: string
  session: SimulationSession
  onRefresh: () => Promise<void>
}) {
  const [actionType, setActionType] = useState<WorkplaceActionType>(
    (session.work_context?.workflow?.find((item): item is WorkplaceActionType => item in workplaceActionLabel) ?? 'clarify_questions'),
  )
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')
  const isLive = session.status === 'active' || session.status === 'paused'
  const context = session.work_context ?? session.scenario.work_context ?? {}
  const workflow = (context.workflow ?? []).filter((item): item is WorkplaceActionType => item in workplaceActionLabel)
  const actionOptions: WorkplaceActionType[] = workflow.length ? workflow : (Object.keys(workplaceActionLabel) as WorkplaceActionType[])
  const current = session.deliverables.find((item) => item.action_type === actionType && item.status === 'draft')
  const submitted = session.deliverables.filter((item) => item.status !== 'draft')
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const save = useMutation({
    mutationFn: () => apiFetch<{ deliverable: WorkplaceDeliverable }>(
      `/workplace/sessions/${session.id}/deliverables`,
      { method: 'POST', body: JSON.stringify({ action_type: actionType, title, content }) },
      token,
    ),
    onSuccess: async () => {
      setError('')
      setNotice('草案已保存到当前会话。')
      await onRefresh()
    },
    onError: (value: Error) => { setError(value.message) },
  })
  const submit = useMutation({
    mutationFn: () => apiFetch<{ deliverable: WorkplaceDeliverable }>(
      `/workplace/sessions/${session.id}/deliverables/submit`,
      { method: 'POST', body: JSON.stringify({ action_type: actionType, title, content }) },
      token,
    ),
    onSuccess: async () => {
      setError('')
      setNotice('交付物已提交，后端已完成结构化评审。')
      await onRefresh()
      void queryClient.invalidateQueries({ queryKey: ['workplace-reports'] })
    },
    onError: (value: Error) => { setError(value.message) },
  })
  const assist = useMutation({
    mutationFn: () => apiFetch<{ deliverable: WorkplaceDeliverable; provider: string; rationale: string[] }>(
      `/workplace/sessions/${session.id}/workplace-assist`,
      { method: 'POST', body: JSON.stringify({ action_type: actionType }) },
      token,
    ),
    onSuccess: async (value) => {
      setTitle(value.deliverable.title)
      setContent(value.deliverable.content)
      setError('')
      setNotice(`工作 Agent 已生成${value.deliverable.action_label}草案（${value.provider}），请核对事实后提交。`)
      await onRefresh()
    },
    onError: (value: Error) => { setError(value.message) },
  })
  const control = useMutation({
    mutationFn: (action: ControlRequest['action']) => apiFetch<SimulationSession>(
      `/workplace/sessions/${session.id}/controls`,
      { method: 'POST', body: JSON.stringify({ action }) },
      token,
    ),
    onSuccess: async () => {
      setError('')
      await onRefresh()
    },
    onError: (value: Error) => { setError(value.message) },
  })

  useEffect(() => {
    if (current) {
      setTitle(current.title)
      setContent(current.content)
    } else {
      setTitle(workplaceActionLabel[actionType])
      setContent('')
    }
  }, [actionType, current?.id])

  const listValue = (value: string[] | undefined, fallback: string) => value?.length ? value.join('、') : fallback
  const statusLabel = session.status === 'completed' ? '已完成' : session.status === 'paused' ? '已暂停' : '进行中'
  const selectedSubmitted = submitted.filter((item) => item.action_type === actionType).sort((a, b) => b.revision - a.revision)[0]
  const score = selectedSubmitted?.review?.score

  return (
    <div className="entry-reveal space-y-6">
      <section className="signal-grid border border-[#102015] bg-[#f8fbf5] px-5 py-6 text-[#102015] shadow-[7px_7px_0_rgba(16,32,21,0.14)] sm:px-7">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="min-w-0">
            <button type="button" className="inline-flex items-center gap-2 text-sm font-bold text-[#526051] hover:text-[#38642f]" onClick={() => navigate('/student/workplace')}><ArrowLeft size={16} />返回职场训练</button>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <span className="inline-flex items-center gap-2 border border-[#38642f]/30 bg-[#e3f6ce] px-3 py-1.5 text-xs font-extrabold text-[#30442f]"><BriefcaseBusiness size={15} />真实工作任务台</span>
              <span className="text-xs font-bold text-[#647460]">{statusLabel} · {session.deliverables.length} 份交付记录</span>
            </div>
            <h1 className="mt-4 text-3xl font-extrabold leading-tight sm:text-4xl">{session.scenario.title}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-[#526051]">这里处理入职后的工作任务和交付物，不再使用求职面试的提问回合。每次保存、提交和评审都会写入服务端。</p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <div className="border border-[#102015]/15 bg-[#e7f1df] px-5 py-2 text-right">
              <p className="text-[10px] font-bold tracking-[0.12em] text-[#526051]">工作能力评分</p>
              <p className="mt-1 text-2xl font-extrabold text-[#38642f]">{session.score ?? score ?? '--'}</p>
            </div>
            <AskAgentButton role="student" context={{ type: 'workplace_session', id: session.id }} className="border-[#102015]/20 bg-[#102015] text-white hover:border-[#38642f] hover:bg-[#38642f]" />
          </div>
        </div>
      </section>

      {notice ? <Notice tone="success"><CheckCircle2 size={16} />{notice}</Notice> : null}
      {error ? <Notice tone="danger"><AlertTriangle size={16} />{error}</Notice> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(360px,0.9fr)_320px]">
        <section className="panel-prism min-w-0 border p-0">
          <div className="border-b border-[#102015]/10 bg-[#edf2e9] px-5 py-4">
            <p className="text-[11px] font-bold tracking-[0.14em] text-[#4f7e20]">WORK BRIEF</p>
            <h2 className="mt-1 text-xl font-extrabold text-[#102015]">任务简报</h2>
          </div>
          <div className="space-y-5 p-5">
            <div className="border-l-2 border-[#4f7e20] bg-[#e3f6ce] px-4 py-3">
              <p className="text-xs font-bold text-[#4f7e20]">本次目标</p>
              <p className="mt-2 text-sm font-bold leading-6 text-[#102015]">{context.objective ?? '待与主管确认目标和完成定义。'}</p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <BriefFact icon={<BriefcaseBusiness size={15} />} label="岗位 / 阶段" value={`${context.role ?? '待确认'} · ${context.stage ?? '待确认'}`} />
              <BriefFact icon={<CalendarDays size={15} />} label="截止时间" value={context.deadline ?? '待确认'} />
              <BriefFact icon={<Users size={15} />} label="协作对象" value={listValue(context.stakeholders, '待确认协作方')} />
              <BriefFact icon={<FileCheck2 size={15} />} label="交付物" value={listValue(context.deliverables, '待确认交付物')} />
            </div>
            <BriefList icon={<Target size={15} />} label="验收标准" items={context.acceptance_criteria} fallback="提交前先确认可验证的验收标准。" />
            <BriefList icon={<ShieldAlert size={15} />} label="约束与风险" items={context.constraints} fallback="当前没有额外约束，仍需在工作中记录新风险。" danger />
            <div className="border-t border-[#102015]/10 pt-4">
              <p className="text-xs font-extrabold text-[#526051]">建议交付路径</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {actionOptions.map((item, index) => <span key={item} className="inline-flex items-center gap-2 border border-[#102015]/15 bg-white px-3 py-2 text-xs font-bold text-[#30442f]"><span className="grid size-5 place-items-center bg-[#102015] text-[10px] text-[#c7ff4c]">{index + 1}</span>{workplaceActionLabel[item]}</span>)}
              </div>
            </div>
          </div>
        </section>

        <section className="panel-prism min-w-0 border p-0">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#102015]/10 bg-[#edf2e9] px-5 py-4">
            <div><p className="text-[11px] font-bold tracking-[0.14em] text-[#4f7e20]">DELIVERABLE STUDIO</p><h2 className="mt-1 text-xl font-extrabold text-[#102015]">工作交付编辑器</h2></div>
            <span className="text-xs font-bold text-[#647460]">{content.length} 字</span>
          </div>
          <div className="p-5">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {actionOptions.map((item) => {
                const active = item === actionType
                const Icon = item === 'clarify_questions' ? ClipboardList : item === 'action_plan' ? ListChecks : item === 'risk_register' ? ShieldAlert : item === 'meeting_minutes' ? FileText : item === 'weekly_report' ? CalendarDays : FileCheck2
                return <button key={item} type="button" onClick={() => setActionType(item)} className={`flex min-h-16 items-center gap-2 border px-3 py-2 text-left text-xs font-extrabold transition ${active ? 'border-[#102015] bg-[#102015] text-[#c7ff4c]' : 'border-[#102015]/15 bg-white text-[#30442f] hover:border-[#38642f] hover:bg-[#e3f6ce]'}`}><Icon size={16} />{workplaceActionLabel[item]}</button>
              })}
            </div>
            {selectedSubmitted ? <div className="mt-4 flex items-center justify-between gap-3 border border-emerald-700/20 bg-emerald-50 px-3 py-2 text-xs text-emerald-950"><span className="inline-flex items-center gap-2"><CheckCircle2 size={15} />已提交第 {selectedSubmitted.revision} 版</span><span>评分 {selectedSubmitted.review?.score ?? '--'}</span></div> : null}
            <label className="mt-5 block text-xs font-extrabold text-[#526051]" htmlFor="workplace-deliverable-title">交付物标题</label>
            <input id="workplace-deliverable-title" value={title} onChange={(event) => setTitle(event.target.value)} disabled={!isLive} className="input-prism mt-2 w-full rounded-md border px-3 py-2.5 text-sm font-bold text-[#102015] outline-none" />
            <label className="mt-4 block text-xs font-extrabold text-[#526051]" htmlFor="workplace-deliverable-content">交付物内容</label>
            <textarea id="workplace-deliverable-content" value={content} onChange={(event) => setContent(event.target.value)} disabled={!isLive} rows={14} placeholder="把真实工作中的目标、行动、协作、风险和验收证据写在这里。" className="input-prism mt-2 w-full resize-y rounded-md border px-4 py-3 text-sm leading-7 text-[#102015] outline-none" />
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" className={secondaryButton} disabled={!isLive || content.trim().length < 20 || save.isPending} onClick={() => save.mutate()}><Save size={16} />{save.isPending ? '正在保存' : '保存草案'}</button>
              <button type="button" className={secondaryButton} disabled={!isLive || assist.isPending} onClick={() => assist.mutate()}><Sparkles size={16} />{assist.isPending ? 'Agent 正在生成' : 'AI 生成草案'}</button>
              <button type="button" className={primaryButton} disabled={!isLive || content.trim().length < 20 || submit.isPending} onClick={() => submit.mutate()}><SendHorizontal size={16} />{submit.isPending ? '正在评审' : '提交交付物'}</button>
            </div>
            <p className="mt-3 text-xs leading-5 text-[#647460]">AI 只提供基于任务简报的草案，不会代替你提交外部系统；提交前请核对每项事实。</p>
          </div>
        </section>

        <aside className="space-y-5">
          <section className="panel-prism border p-0">
            <div className="border-b border-[#102015]/10 bg-[#edf2e9] px-5 py-4"><p className="text-[11px] font-bold tracking-[0.14em] text-[#4f7e20]">ARTIFACT LOG</p><h2 className="mt-1 text-xl font-extrabold text-[#102015]">交付历史</h2></div>
            <div className="divide-y divide-[#102015]/10">
              {session.deliverables.length ? session.deliverables.map((item) => <article key={item.id} className="p-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-extrabold text-[#102015]">{item.title}</p><p className="mt-1 text-xs text-[#647460]">{item.action_label} · 第 {item.revision} 版</p></div><span className={`shrink-0 border px-2 py-1 text-[10px] font-bold ${item.status === 'draft' ? 'border-amber-700/25 bg-amber-50 text-amber-950' : 'border-emerald-700/25 bg-emerald-50 text-emerald-950'}`}>{item.status === 'draft' ? '草案' : '已提交'}</span></div>{item.review?.dimensions ? <div className="mt-3 grid grid-cols-2 gap-2">{Object.entries(item.review.dimensions).slice(0, 4).map(([key, value]) => <div key={key} className="bg-[#edf2e9] px-2 py-2"><p className="truncate text-[10px] text-[#647460]">{workplaceDimensionLabel[key] ?? key}</p><p className="mt-1 text-sm font-extrabold text-[#38642f]">{value}</p></div>)}</div> : null}{item.reviewer_feedback ? <p className="mt-3 border-l-2 border-[#ff7358] pl-3 text-xs leading-5 text-[#8c2f1f]">{item.reviewer_feedback}</p> : null}</article>) : <div className="p-5"><EmptyState title="还没有交付记录" description="保存或提交第一份工作交付物后，版本和评审会显示在这里。" /></div>}
            </div>
          </section>
          <section className="border border-[#102015]/20 bg-[#f8fbf5] p-5 shadow-[4px_4px_0_rgba(16,32,21,0.1)]"><h2 className="text-sm font-extrabold text-[#102015]">会话控制</h2><div className="mt-4 grid gap-2">{session.status === 'active' ? <button type="button" className={secondaryButton} disabled={control.isPending} onClick={() => control.mutate('pause')}><Pause size={16} />暂停工作台</button> : session.status === 'paused' ? <button type="button" className={secondaryButton} disabled={control.isPending} onClick={() => control.mutate('resume')}><PlayCircle size={16} />恢复工作台</button> : null}{isLive ? <button type="button" className={primaryButton} disabled={control.isPending || submitted.length === 0} onClick={() => control.mutate('complete')}><CheckCircle2 size={16} />完成本次复盘</button> : null}</div>{isLive && submitted.length === 0 ? <p className="mt-3 text-xs leading-5 text-[#8c2f1f]">至少提交一份交付物后才能完成复盘。</p> : null}</section>
        </aside>
      </div>
    </div>
  )
}

function BriefFact({ icon, label, value }: { icon: ReactNode; label: string; value: string }) {
  return <div className="border border-[#102015]/12 bg-white px-3 py-3"><p className="flex items-center gap-2 text-[10px] font-bold tracking-[0.08em] text-[#647460]">{icon}{label}</p><p className="mt-2 text-xs font-bold leading-5 text-[#102015]">{value}</p></div>
}

function BriefList({ icon, label, items, fallback, danger = false }: { icon: ReactNode; label: string; items?: string[]; fallback: string; danger?: boolean }) {
  return <div className={`border-l-2 px-3 py-3 ${danger ? 'border-[#ff7358] bg-[#fff0eb]' : 'border-[#38642f] bg-[#edf2e9]'}`}><p className={`flex items-center gap-2 text-xs font-extrabold ${danger ? 'text-[#8c2f1f]' : 'text-[#30442f]'}`}>{icon}{label}</p><ul className={`mt-2 space-y-1 text-xs leading-5 ${danger ? 'text-[#8c2f1f]' : 'text-[#526051]'}`}>{items?.length ? items.map((item) => <li key={item}>· {item}</li>) : <li>{fallback}</li>}</ul></div>
}

function ReportView({ report, assessment }: { report: Report | null; assessment: SimulationSession['assessment'] }) {
  if (!report) return <div className="mt-6"><Notice tone="success"><CheckCircle2 size={16} />{assessment?.summary ?? '训练已完成。'}</Notice></div>
  return (
    <section className="mt-6 border border-[#102015] bg-[#f8fbf5] p-5 shadow-[7px_7px_0_rgba(16,32,21,0.12)] sm:p-7">
      <Notice tone="success"><CheckCircle2 size={16} />{assessment?.summary ?? '训练已完成。'} {assessment?.next_action}</Notice>
      <div className="mt-6 grid gap-px border border-[#102015]/15 bg-[#102015]/15 sm:grid-cols-4">
        {Object.entries(report.average_dimensions ?? {}).map(([key, score]) => <div key={key} className="bg-[#f8fbf5] p-4"><p className="text-xs font-bold text-[#647460]">{dimensionLabel[key] ?? key}</p><p className="mt-2 text-2xl font-extrabold text-[#102015]">{score}</p></div>)}
      </div>
      <div className="mt-6 grid gap-6 sm:grid-cols-2">
        <div><p className="text-sm font-extrabold text-[#102015]">表现优势</p><ul className="mt-3 space-y-2 text-sm leading-6 text-[#526051]">{(report.strengths ?? []).map((item) => <li key={item} className="flex gap-2"><CheckCircle2 className="mt-1 shrink-0 text-emerald-700" size={15} />{item}</li>)}</ul></div>
        <div><p className="text-sm font-extrabold text-[#102015]">重点改进</p><ul className="mt-3 space-y-2 text-sm leading-6 text-[#526051]">{(report.improvements ?? []).map((item) => <li key={item} className="flex gap-2"><AlertTriangle className="mt-1 shrink-0 text-[#b24531]" size={15} />{item}</li>)}</ul></div>
      </div>
    </section>
  )
}
