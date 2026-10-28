import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  BriefcaseBusiness,
  CheckCircle2,
  CircleStop,
  LoaderCircle,
  MessageSquareText,
  Mic,
  Presentation,
  RefreshCw,
  Send,
  ShieldAlert,
  Square,
  UsersRound,
  Volume2,
} from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { apiFetch, apiFetchBlob } from '../../app/api'
import type { AiCapabilities } from '../chat/types'
import { EmptyState, LoadingState, Notice, PageHeader, Panel, inputClass, primaryButton, secondaryButton } from '../../components/Ui'
import { useAudioRecorder } from '../chat/useAudioRecorder'
import { DigitalHumanStage } from './DigitalHumanStage'
import { EmotionCamera } from './EmotionCamera'
import {
  type InterviewEvaluation,
  type InterviewFinalReport,
  type InterviewProgress,
  type InterviewQuestion,
  type InterviewSession,
  type InterviewStreamState,
  displayInterviewQuestion,
  displayInterviewText,
  streamInterviewAnswer,
} from './interview-api'
import { isPreHireMode, phaseLabel, type PreHireMode, type SimulationMode } from './training-phases'

type Resume = { id: string; original_name: string; parse_status: string }
type Job = { id: string; title: string; company: string }
type InterviewMode = 'structured' | PreHireMode
type WorkplaceScenario = {
  id: string
  title: string
  description: string
  mode: SimulationMode
  difficulty: string
  competencies: string[]
  step_count: number
}
type AiTask = {
  id: string
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  result?: { text?: string; artifact_id?: string; media_type?: string }
  error?: { message?: string } | null
}

type ChatMessage = {
  id: string
  role: 'assistant' | 'user'
  content: string
  question?: InterviewQuestion
}

const scoreLabels: Record<string, string> = {
  content_completeness: '内容完整度',
  job_relevance: '岗位相关性',
  answer_structure: '表达结构',
  evidence_quality: '证据质量',
}

scoreLabels.emotion_stability = '表达稳定度（摄像头分析）'

const taskPolling = (task?: AiTask) => task && ['queued', 'running'].includes(task.status) ? 1_000 : false

const interviewModeLabel: Record<InterviewMode, string> = {
  structured: '结构化岗位面试',
  stress_interview: '压力面试',
  group_interview: '无领导群面',
  presentation_defense: '路演答辩',
  career_planning: '职业规划面试',
}

const interviewModes: Array<{ id: InterviewMode; title: string; description: string; icon: typeof MessageSquareText }> = [
  { id: 'structured', title: '结构化岗位面试', description: '根据简历与岗位动态出题，逐轮评分并追问。', icon: BriefcaseBusiness },
  { id: 'stress_interview', title: '压力面试', description: '可调压力等级，训练高压下的结构化表达。', icon: ShieldAlert },
  { id: 'group_interview', title: '无领导群面', description: '多角色协同讨论，观察表达、协作与推进。', icon: UsersRound },
  { id: 'presentation_defense', title: '路演答辩', description: '先陈述项目，再接受数字人评委追问。', icon: Presentation },
  { id: 'career_planning', title: '职业规划面试', description: '围绕目标、约束与行动形成可执行回答。', icon: MessageSquareText },
]

function requestId(prefix: string) {
  return typeof crypto.randomUUID === 'function' ? `${prefix}-${crypto.randomUUID()}` : `${prefix}-${Date.now()}`
}

function messageFromTurn(turn: InterviewSession['turns'][number]): ChatMessage[] {
  const messages: ChatMessage[] = [
    { id: `question-${turn.id}`, role: 'assistant', content: displayInterviewQuestion(turn.question) ?? turn.question },
    { id: `answer-${turn.id}`, role: 'user', content: turn.answer },
  ]
  if (turn.assistant_content?.trim()) {
    messages.push({ id: `feedback-${turn.id}`, role: 'assistant', content: turn.assistant_content })
  }
  return messages
}

function scoreTone(score: number) {
  if (score >= 80) return 'text-emerald-700'
  if (score >= 60) return 'text-amber-700'
  return 'text-[#d6533e]'
}

function ProgressRail({ progress }: { progress: InterviewProgress }) {
  const percent = progress.max_turns ? Math.min(100, Math.round((progress.turns_answered / progress.max_turns) * 100)) : 0
  return <div className="space-y-4">
    <div className="flex items-end justify-between gap-3">
      <div>
        <p className="text-[11px] font-bold tracking-[0.15em] text-[#647460]">面试进度</p>
        <p className="mt-1 text-lg font-bold text-[#102015]">第 {Math.min(progress.turns_answered + 1, progress.max_turns)} / {progress.max_turns} 轮</p>
      </div>
      <span className="text-sm font-semibold text-[#0f766e]">{percent}%</span>
    </div>
    <div className="h-2 overflow-hidden bg-[#dfe8da]" aria-label="面试进度">
      <div className="h-full bg-[#0f766e] transition-all duration-500" style={{ width: `${percent}%` }} />
    </div>
    <div className="grid grid-cols-3 gap-2 text-xs">
      <div className="border border-[#102015]/10 bg-white/60 px-3 py-2"><span className="block text-[#647460]">核心题</span><strong className="mt-1 block text-[#102015]">{Math.min(progress.core_current, progress.core_total)} / {progress.core_total}</strong></div>
      <div className="border border-[#102015]/10 bg-white/60 px-3 py-2"><span className="block text-[#647460]">追问</span><strong className="mt-1 block text-[#102015]">{progress.follow_ups_used} / {progress.follow_ups_max}</strong></div>
      <div className="border border-[#102015]/10 bg-white/60 px-3 py-2"><span className="block text-[#647460]">已答</span><strong className="mt-1 block text-[#102015]">{progress.turns_answered}</strong></div>
    </div>
  </div>
}

function EvaluationRail({ evaluation }: { evaluation: InterviewEvaluation | null }) {
  if (!evaluation) {
    return <div className="border border-dashed border-[#728171] bg-white/35 px-4 py-6 text-center text-xs leading-5 text-[#647460]">提交第一轮回答后，这里会显示 AI 评分、证据判断和改进建议。</div>
  }
  const feedback = evaluation.feedback ?? []
  return <div className="space-y-4">
    <div className="flex items-center justify-between gap-3">
      <p className="text-sm font-bold text-[#102015]">本轮评分</p>
      <CheckCircle2 size={17} className="text-[#0f766e]" />
    </div>
    <div className="grid grid-cols-2 gap-2">
      {Object.entries(scoreLabels).filter(([key]) => key !== 'emotion_stability' || evaluation.emotion_stability != null).map(([key, label]) => {
        const score = Number(evaluation[key as keyof InterviewEvaluation] ?? 0)
        return <div key={key} className="border border-[#102015]/10 bg-white/65 px-3 py-3">
          <p className="text-[11px] leading-4 text-[#647460]">{label}</p>
          <p className={`mt-1 text-xl font-bold ${scoreTone(score)}`}>{score}</p>
        </div>
      })}
    </div>
    <div>
      <p className="text-xs font-bold text-[#102015]">改进建议</p>
      {feedback.length ? <ul className="mt-2 space-y-2 text-xs leading-5 text-[#526051]">{feedback.map((item) => <li key={item} className="border-l-2 border-[#ff7358] pl-2">{item}</li>)}</ul> : <p className="mt-2 text-xs text-[#647460]">本轮没有额外建议。</p>}
    </div>
  </div>
}

function FinalReport({ report }: { report: InterviewFinalReport }) {
  return <div className="space-y-5">
    <Notice tone="success"><div><p className="font-semibold">模拟面试已完成</p><p className="mt-1 text-xs">共完成 {report.turns_answered} 轮，评分来自本场实际回答。</p></div></Notice>
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
      {Object.entries(report.average_scores).map(([key, score]) => <div key={key} className="border border-[#102015]/10 bg-white/65 px-3 py-3"><p className="text-[11px] text-[#647460]">{scoreLabels[key] ?? key}</p><p className={`mt-1 text-xl font-bold ${scoreTone(score)}`}>{score}</p></div>)}
    </div>
    <div className="grid gap-4 sm:grid-cols-2">
      <div><p className="text-xs font-bold text-[#102015]">表现优势</p><ul className="mt-2 space-y-1 text-xs leading-5 text-[#526051]">{report.strengths.length ? report.strengths.map((item) => <li key={item}>· {item}</li>) : <li>暂无达到优秀阈值的维度。</li>}</ul></div>
      <div><p className="text-xs font-bold text-[#102015]">重点改进</p><ul className="mt-2 space-y-1 text-xs leading-5 text-[#526051]">{report.improvements.length ? report.improvements.map((item) => <li key={item}>· {item}</li>) : <li>当前各维度均达到基础要求。</li>}</ul></div>
    </div>
    {report.feedback.length ? <div><p className="text-xs font-bold text-[#102015]">下一步行动</p><ul className="mt-2 space-y-1 text-xs leading-5 text-[#526051]">{report.feedback.map((item) => <li key={item}>· {item}</li>)}</ul></div> : null}
  </div>
}

export function InterviewPage({ token }: { token: string }) {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const resumes = useQuery({ queryKey: ['resumes'], queryFn: () => apiFetch<Resume[]>('/resumes', {}, token) })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: () => apiFetch<Job[]>('/jobs', {}, token) })
  const scenarios = useQuery({ queryKey: ['workplace-scenarios', 'pre_hire'], queryFn: () => apiFetch<WorkplaceScenario[]>('/workplace/scenarios?phase=pre_hire', {}, token) })
  const sessions = useQuery({ queryKey: ['workplace-sessions', 'pre_hire'], queryFn: () => apiFetch<Array<{ id: string; status: string; mode: SimulationMode; scenario: WorkplaceScenario }>>('/workplace/sessions?phase=pre_hire', {}, token) })
  const [resumeId, setResumeId] = useState('')
  const [jobId, setJobId] = useState('')
  const requestedMode = searchParams.get('mode') as InterviewMode | null
  const [selectedMode, setSelectedMode] = useState<InterviewMode>(requestedMode && interviewModes.some((item) => item.id === requestedMode) ? requestedMode : 'structured')
  const [selectedScenarioId, setSelectedScenarioId] = useState<string | null>(null)
  const [startError, setStartError] = useState('')

  useEffect(() => {
    const requestedJobId = new URLSearchParams(window.location.search).get('job_id')
    if (requestedJobId && jobs.data?.some((job) => job.id === requestedJobId)) setJobId(requestedJobId)
  }, [jobs.data])

  useEffect(() => {
    if (!requestedMode || requestedMode === 'structured' || !interviewModes.some((item) => item.id === requestedMode)) return
    setSelectedMode(requestedMode)
  }, [requestedMode])

  const visibleScenarios = selectedMode === 'structured'
    ? []
    : (scenarios.data ?? []).filter((item) => isPreHireMode(item.mode) && item.mode === selectedMode)
  const selectedScenario = visibleScenarios.find((item) => item.id === selectedScenarioId) ?? visibleScenarios[0] ?? null
  const resumableSession = selectedScenario
    ? sessions.data?.find((item) => item.scenario.id === selectedScenario.id && (item.status === 'active' || item.status === 'paused'))
    : null

  const startStructured = useMutation({
    mutationFn: () => apiFetch<Pick<InterviewSession, 'id'>>('/interviews', { method: 'POST', body: JSON.stringify({ resume_id: resumeId, job_id: jobId }) }, token),
    onSuccess: (value) => navigate(`/student/interview/${value.id}`),
    onError: (error: Error) => setStartError(error.message),
  })

  const startWorkplace = useMutation({
    mutationFn: () => apiFetch<WorkplaceScenario & { id: string }>(`/workplace/scenarios/${selectedScenario?.id}/sessions`, { method: 'POST' }, token),
    onSuccess: (value) => navigate(`/student/workplace/session/${value.id}`),
    onError: (error: Error) => setStartError(error.message),
  })

  const selectedModeTitle = interviewModeLabel[selectedMode]
  const isStarting = startStructured.isPending || startWorkplace.isPending
  const canStart = selectedMode === 'structured' ? Boolean(resumeId && jobId) : Boolean(selectedScenario)
  const startInterview = () => {
    setStartError('')
    if (selectedMode === 'structured') {
      startStructured.mutate()
    } else if (resumableSession) {
      navigate(`/student/workplace/session/${resumableSession.id}`)
    } else {
      startWorkplace.mutate()
    }
  }

  return <>
    <div className="entry-reveal">
      <PageHeader title="入职前 · AI 数字人面试中心" description="面向求职阶段的模拟面试：结构化岗位面试、压力面试、群面、路演答辩和职业规划均在这里完成。AI 自动出题、朗读、评分并生成建议；入职后的工作场景训练请进入职场训练。" />
      <div className="mb-6 flex items-start gap-3 border border-[#0f766e]/25 bg-[#e7f5ef] px-4 py-3 text-sm text-[#0b4f46]">
        <span className="mt-0.5 shrink-0 font-extrabold">{phaseLabel.preHire}</span>
        <span className="text-xs leading-5">这里覆盖拿到 offer 前的求职训练，不包含入职后的任务澄清、交付协作和跨部门工作场景。</span>
      </div>
      <section className="mb-6 grid gap-2 sm:grid-cols-2 xl:grid-cols-5" aria-label="选择面试类型">
        {interviewModes.map((item) => {
          const Icon = item.icon
          const active = selectedMode === item.id
          return <button key={item.id} type="button" aria-pressed={active} onClick={() => { setSelectedMode(item.id); setStartError(''); setSelectedScenarioId(null) }} className={`group relative min-h-[142px] border p-4 text-left transition ${active ? 'border-[#102015] bg-[#102015] text-white shadow-[5px_5px_0_rgba(16,32,21,0.2)]' : 'border-[#102015]/18 bg-[#f8fbf5] text-[#102015] hover:border-[#102015] hover:bg-[#e3f6ce]'}`}>
            <span className={`grid size-9 place-items-center border ${active ? 'border-[#c7ff4c] bg-[#c7ff4c] text-[#102015]' : 'border-[#102015]/18 bg-[#edf2e9]'}`}><Icon size={18} /></span>
            <span className="mt-5 block text-sm font-extrabold">{item.title}</span>
            <span className={`mt-2 block text-xs leading-5 ${active ? 'text-[#cfdbc9]' : 'text-[#647460]'}`}>{item.description}</span>
          </button>
        })}
      </section>

      {startError ? <div className="mb-5"><Notice tone="danger">{startError}</Notice></div> : null}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="panel-prism border p-0">
          <div className="flex items-start justify-between gap-4 border-b border-[#102015]/10 bg-[#edf2e9] px-5 py-5 sm:px-7">
            <div><p className="text-[11px] font-bold tracking-[0.14em] text-[#0f766e]">面试配置</p><h2 className="mt-1 text-2xl font-extrabold text-[#102015]">{selectedModeTitle}</h2></div>
            <span className="grid size-10 place-items-center border border-[#102015]/15 bg-white text-[#0f766e]"><MessageSquareText size={19} /></span>
          </div>
          <div className="p-5 sm:p-7">
            {selectedMode === 'structured' ? <div className="space-y-5">
              <label className="block text-sm font-semibold">简历
                <select aria-label="简历" className={inputClass} value={resumeId} onChange={(event) => setResumeId(event.target.value)}>
                  <option value="">选择已解析简历</option>
                  {resumes.data?.filter((item) => item.parse_status === 'parsed').map((item) => <option key={item.id} value={item.id}>{item.original_name}</option>)}
                </select>
              </label>
              <label className="block text-sm font-semibold">目标岗位
                <select aria-label="目标岗位" className={inputClass} value={jobId} onChange={(event) => setJobId(event.target.value)}>
                  <option value="">选择岗位</option>
                  {jobs.data?.map((job) => <option key={job.id} value={job.id}>{job.title} · {job.company}</option>)}
                </select>
              </label>
              <div className="grid gap-3 sm:grid-cols-3"><div className="border border-[#102015]/12 bg-white/70 p-3"><p className="text-xs text-[#647460]">首题来源</p><p className="mt-1 text-sm font-bold">简历 + 岗位</p></div><div className="border border-[#102015]/12 bg-white/70 p-3"><p className="text-xs text-[#647460]">核心问题</p><p className="mt-1 text-sm font-bold">6 题动态生成</p></div><div className="border border-[#102015]/12 bg-white/70 p-3"><p className="text-xs text-[#647460]">追问上限</p><p className="mt-1 text-sm font-bold">2 轮</p></div></div>
            </div> : <div className="space-y-5">
              <div className="flex items-center justify-between gap-3"><div><p className="text-sm font-bold text-[#102015]">选择面试场景</p><p className="mt-1 text-xs text-[#647460]">场景状态、评分和压力等级由后端持久化。</p></div><span className="text-xs font-bold text-[#0f766e]">{visibleScenarios.length} 个可用</span></div>
              {visibleScenarios.length ? <div className="grid gap-3 sm:grid-cols-2">{visibleScenarios.map((scenario) => <button key={scenario.id} type="button" aria-pressed={selectedScenario?.id === scenario.id} onClick={() => setSelectedScenarioId(scenario.id)} className={`border p-4 text-left transition ${selectedScenario?.id === scenario.id ? 'border-[#102015] bg-[#e3f6ce] shadow-[3px_3px_0_rgba(16,32,21,0.14)]' : 'border-[#102015]/15 bg-white/70 hover:border-[#102015]'}`}><div className="flex items-start justify-between gap-3"><p className="text-sm font-extrabold text-[#102015]">{scenario.title}</p><span className="text-[11px] font-bold text-[#647460]">{scenario.step_count} 阶段</span></div><p className="mt-2 text-xs leading-5 text-[#526051]">{scenario.description}</p><p className="mt-3 text-[11px] font-bold text-[#38642f]">{scenario.competencies.slice(0, 3).join(' · ')}</p></button>)}</div> : <EmptyState title="暂未配置此类面试场景" description="可以先选择结构化岗位面试，或稍后重试入职前面试服务。" />}
              {resumableSession ? <Notice tone="info">已有一条未完成的{selectedModeTitle}，点击开始将从当前阶段恢复。</Notice> : null}
            </div>}
            <div className="mt-7 flex flex-wrap items-center justify-between gap-3 border-t border-[#102015]/10 pt-5">
              <p className="text-xs leading-5 text-[#647460]">进入后：数字人自动提问，可语音或文字回答；AI 会保存每轮评分、证据和改进建议。</p>
              <button type="button" className={primaryButton} aria-label={selectedMode === 'structured' ? '开始模拟面试' : '开始数字人面试'} disabled={!canStart || isStarting} onClick={startInterview}>{isStarting ? <LoaderCircle size={17} className="animate-spin" /> : <MessageSquareText size={17} />}{isStarting ? '正在创建会话' : resumableSession ? '继续面试' : selectedMode === 'structured' ? '开始模拟面试' : '开始数字人面试'}</button>
            </div>
          </div>
        </section>
        <DigitalHumanStage modeLabel={selectedModeTitle} question={null} state="idle" />
      </div>
    </div>
  </>
}

export function InterviewSessionPage({ token }: { token: string }) {
  const { sessionId } = useParams<{ sessionId: string }>()
  const queryClient = useQueryClient()
  const capabilitiesQuery = useQuery({
    queryKey: ['ai-capabilities'],
    queryFn: () => apiFetch<AiCapabilities>('/ai/capabilities', {}, token),
    staleTime: 30_000,
  })
  const sessionQuery = useQuery({
    queryKey: ['interview-session', sessionId],
    queryFn: () => apiFetch<InterviewSession>(`/interviews/${sessionId}`, {}, token),
    enabled: Boolean(sessionId),
  })
  const session = sessionQuery.data
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [answer, setAnswer] = useState('')
  const [evaluation, setEvaluation] = useState<InterviewEvaluation | null>(null)
  const [progress, setProgress] = useState<InterviewProgress | null>(null)
  const [finalReport, setFinalReport] = useState<InterviewFinalReport | null>(null)
  const [currentQuestion, setCurrentQuestion] = useState<InterviewQuestion | null>(null)
  const [streamingText, setStreamingText] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [streamError, setStreamError] = useState('')
  const [transcriptionTaskId, setTranscriptionTaskId] = useState<string | null>(null)
  const [speechTaskId, setSpeechTaskId] = useState<string | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [mediaError, setMediaError] = useState('')
  const initializedRef = useRef<string | null>(null)
  const audioUrlRef = useRef<string | null>(null)
  const appliedTranscriptRef = useRef<string | null>(null)
  const spokenQuestionRef = useRef<string | null>(null)

  useEffect(() => {
    if (!session || initializedRef.current === session.id) return
    initializedRef.current = session.id
    setMessages(session.turns.flatMap(messageFromTurn))
    setCurrentQuestion(session.status === 'completed' ? null : session.question)
    setProgress(session.progress)
    setFinalReport(session.final_report)
    setEvaluation(session.turns.at(-1)?.evaluation ?? null)
  }, [session])

  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (!streaming) return
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [streaming])

  const uploadRecording = useMutation({
    mutationFn: (blob: Blob) => {
      const body = new FormData()
      body.append('file', blob, 'answer.webm')
      return apiFetch<{ task_id: string }>(`/interviews/${sessionId}/recordings`, { method: 'POST', body }, token)
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
  const transcription = useQuery({
    queryKey: ['ai-task', transcriptionTaskId],
    queryFn: () => apiFetch<AiTask>(`/ai/tasks/${transcriptionTaskId}`, {}, token),
    enabled: Boolean(transcriptionTaskId),
    refetchInterval: (query) => taskPolling(query.state.data),
  })
  const speech = useQuery({
    queryKey: ['ai-task', speechTaskId],
    queryFn: () => apiFetch<AiTask>(`/ai/tasks/${speechTaskId}`, {}, token),
    enabled: Boolean(speechTaskId),
    refetchInterval: (query) => taskPolling(query.state.data),
  })

  useEffect(() => {
    const task = transcription.data
    if (transcriptionTaskId && task?.status === 'succeeded' && task.result?.text !== undefined && appliedTranscriptRef.current !== transcriptionTaskId) {
      appliedTranscriptRef.current = transcriptionTaskId
      setAnswer(task.result.text)
    }
  }, [transcription.data, transcriptionTaskId])

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

  const complete = useMutation({
    mutationFn: () => apiFetch<{ status: 'completed'; progress: InterviewProgress; final_report: InterviewFinalReport }>(`/interviews/${sessionId}/complete`, { method: 'POST' }, token),
    onSuccess: (value) => {
      setProgress(value.progress)
      setFinalReport(value.final_report)
      setCurrentQuestion(null)
      void queryClient.invalidateQueries({ queryKey: ['interview-session', sessionId] })
    },
  })

  const submitAnswer = async () => {
    const content = answer.trim()
    if (!content || !sessionId || streaming || !currentQuestion) return
    const submittedQuestion = currentQuestion
    setAnswer('')
    setStreamError('')
    setStreaming(true)
    setStreamingText('')
    setCurrentQuestion(null)
    setMessages((items) => [
      ...items,
      { id: requestId('question'), role: 'assistant', content: displayInterviewQuestion(submittedQuestion.question) ?? submittedQuestion.question },
      { id: requestId('answer'), role: 'user', content },
    ])
    const done = { content: '' }
    try {
      await streamInterviewAnswer(sessionId, content, token, (event) => {
        if (event.event === 'turn.started') {
          setStreaming(true)
        } else if (event.event === 'turn.evaluated') {
          const state = event.data as unknown as InterviewStreamState
          setEvaluation(state.evaluation)
          setProgress(state.progress)
          setFinalReport(state.final_report)
          setCurrentQuestion(state.next_question)
          setSpeechTaskId(state.speech_task_id ?? null)
          if (state.next_question) spokenQuestionRef.current = `${state.next_question.question_id}:${state.next_question.question}`
        } else if (event.event === 'assistant.reset') {
          setStreamingText('')
        } else if (event.event === 'assistant.delta') {
          setStreamingText((value) => value + String(event.data.text ?? ''))
        } else if (event.event === 'assistant.done') {
          done.content = String(event.data.content ?? '')
          setStreamingText(done.content)
        } else if (event.event === 'stream.error') {
          const message = String(event.data.message ?? '流式点评暂时不可用')
          setStreamError(message)
          setAnswer(content)
          const state = event.data as unknown as InterviewStreamState
          if (state.evaluation) setEvaluation(state.evaluation)
          if (state.progress) setProgress(state.progress)
          if (state.final_report) setFinalReport(state.final_report)
          if (state.next_question) setCurrentQuestion(state.next_question)
        }
      })
      if (done.content) {
        setMessages((items) => [...items, { id: requestId('assistant'), role: 'assistant', content: done.content }])
      }
      void queryClient.invalidateQueries({ queryKey: ['interview-session', sessionId] })
    } catch (error) {
      setStreamError(error instanceof Error ? error.message : '提交失败，请稍后重试')
      setAnswer(content)
    } finally {
      setStreaming(false)
      setStreamingText('')
    }
  }

  const currentStatus = finalReport || session?.status === 'completed' ? 'completed' : 'active'
  const currentProgress = progress ?? session?.progress
  const currentJob = session?.job
  const currentQuestionKey = currentQuestion ? `${currentQuestion.question_id}:${currentQuestion.question}` : null
  const speechAvailable = capabilitiesQuery.data
    ? capabilitiesQuery.data.features?.speech_synthesis ?? capabilitiesQuery.data.services.speech.ready
    : capabilitiesQuery.isError
  const emotionAvailable = capabilitiesQuery.data
    ? capabilitiesQuery.data.features?.camera_emotion ?? capabilitiesQuery.data.services.emotion?.ready ?? false
    : false
  useEffect(() => {
    if (capabilitiesQuery.isLoading) return
    if (!sessionId || !currentQuestion || currentStatus === 'completed' || spokenQuestionRef.current === currentQuestionKey) return
    spokenQuestionRef.current = currentQuestionKey
    setSpeechTaskId(null)
    if (!speechAvailable) {
      setMediaError('当前服务器演示版使用文字面试，未部署数字人语音合成。')
      return
    }
    apiFetch<{ task_id: string }>(`/interviews/${sessionId}/speech`, { method: 'POST', body: JSON.stringify({ text: displayInterviewQuestion(currentQuestion.question) ?? currentQuestion.question }) }, token)
      .then((result) => { setSpeechTaskId(result.task_id); setMediaError('') })
      .catch((error: Error) => setMediaError(error.message || '数字人语音生成失败'))
  }, [capabilitiesQuery.isLoading, currentQuestion, currentQuestionKey, currentStatus, sessionId, speechAvailable, token])
  const inputDisabled = currentStatus === 'completed' || streaming || !currentQuestion
  const questionHint = streaming
    ? '正在评分并生成下一题'
    : currentQuestion
      ? `${currentProgress?.current_kind === 'follow_up' ? '动态追问' : '核心问题'} · ${displayInterviewText(currentQuestion.competency, '综合表达与岗位匹配') ?? '综合表达与岗位匹配'}`
      : currentStatus === 'completed' ? '本场面试已结束' : '等待下一题'
  if (sessionQuery.isLoading) return <LoadingState />
  if (sessionQuery.isError || !session) return <EmptyState title="面试会话加载失败" description="请返回面试入口重新选择，或检查后端服务状态。" />

  return <div className="-mx-4 -my-7 flex min-h-[calc(100vh-4rem)] flex-col border-y border-[#102015] bg-[#e9eee5] lg:-mx-9 lg:-my-9">
    <header className="signal-grid shrink-0 border-b border-[#273c2f] bg-[#102015] px-4 py-5 text-[#f8fbf5] sm:px-7">
      <div className="mx-auto flex w-full max-w-7xl items-start justify-between gap-4">
        <div className="min-w-0">
          <Link to="/student/interview" className="inline-flex items-center gap-1 text-xs text-[#dbe8d4] transition hover:text-[#c7ff4c]"><ArrowLeft size={14} />返回面试入口</Link>
          <p className="mt-4 text-[10px] font-bold tracking-[0.16em] text-[#c7ff4c]">实时 AI 面试</p>
          <h1 className="mt-1 truncate text-2xl font-extrabold text-[#f8fbf5] sm:text-3xl">{currentJob?.title ?? '岗位模拟面试'}</h1>
          <p className="mt-2 text-xs text-[#dbe8d4]">{currentJob?.company ?? '目标岗位'} · AI 对话评分与建议</p>
        </div>
        <button type="button" className={`${secondaryButton} shrink-0 border-[#dbe8d4]/60 bg-[#1a3325] text-[#f8fbf5] hover:bg-[#c7ff4c] hover:text-[#102015]`} disabled={complete.isPending || currentStatus === 'completed'} onClick={() => { if (window.confirm('结束后将生成当前阶段报告，未回答的问题不会计入评分。确认结束吗？')) complete.mutate() }}>
          <CircleStop size={16} />结束面试
        </button>
      </div>
    </header>

    <main className="mx-auto grid min-h-0 w-full max-w-7xl flex-1 grid-cols-1 gap-4 p-4 sm:p-6 xl:grid-cols-[minmax(0,1fr)_300px]">
      <section className="flex min-h-[620px] min-w-0 flex-col overflow-hidden border border-[#102015]/20 bg-[#f7faf5] shadow-[5px_5px_0_rgba(16,32,21,0.12)]" aria-label="AI 面试对话">
        <div className="flex shrink-0 items-center justify-between gap-3 border-b border-[#102015]/15 px-4 py-3 sm:px-6">
          <div><p className="text-[11px] font-bold tracking-[0.12em] text-[#0f766e]">AI 面试官</p><p className="mt-1 text-xs text-[#647460]">{questionHint}</p></div>
          <span className="inline-flex items-center gap-1.5 text-xs text-[#647460]"><span className={`size-2 rounded-full ${streaming ? 'animate-pulse bg-[#c7ff4c]' : 'bg-[#0f766e]'}`} />{streaming ? '正在生成点评' : currentStatus === 'completed' ? '已完成' : '等待回答'}</span>
        </div>
        <DigitalHumanStage
          modeLabel="结构化岗位面试"
          question={displayInterviewQuestion(currentQuestion?.question)}
          competency={displayInterviewText(currentQuestion?.competency, '综合表达与岗位匹配')}
          state={currentStatus === 'completed' ? 'complete' : streaming ? 'thinking' : recorder.recording ? 'listening' : currentQuestion ? 'speaking' : 'idle'}
          audioUrl={audioUrl}
          audioLoading={Boolean(speechTaskId && !speech.data?.result?.artifact_id && speech.data?.status !== 'failed')}
          audioError={speech.data?.status === 'failed' ? '数字人语音生成失败' : null}
        />
        <EmotionCamera sessionId={session.id} token={token} disabled={currentStatus === 'completed'} unavailable={!emotionAvailable} />
        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-5 sm:px-7" aria-live="polite">
          {messages.map((message) => <div key={message.id} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[88%] whitespace-pre-wrap px-4 py-3 text-sm leading-7 ${message.role === 'user' ? 'bg-[#102015] text-white' : 'border border-[#102015]/10 bg-white text-[#203226]'}`}>
              {message.role === 'assistant' ? <p className="mb-1 text-[10px] font-bold tracking-[0.12em] text-[#0f766e]">AI 面试官</p> : null}
              {message.content}
            </div>
          </div>)}
          {streaming ? <div className="flex justify-start"><div className="max-w-[88%] border border-[#0f766e]/25 bg-[#edf7f1] px-4 py-3 text-sm leading-7 text-[#203226]"><p className="mb-1 text-[10px] font-bold tracking-[0.12em] text-[#0f766e]">AI 面试官</p>{streamingText || <span className="inline-flex items-center gap-2 text-xs text-[#647460]"><LoaderCircle size={14} className="animate-spin" />正在分析你的回答</span>}</div></div> : null}
          {messages.length === 0 && !currentQuestion && !streaming ? <EmptyState title="还没有对话" description="发送第一段回答，AI 会在同一页面流式返回点评和下一题。" /> : null}
        </div>
        <div className="shrink-0 border-t border-[#102015]/15 bg-[#edf2e9] px-4 py-4 sm:px-6">
          {streamError ? <Notice tone="warning"><div><p>{streamError}</p><p className="mt-1 text-xs">本轮评分已经保存，可以检查右侧评分后重试生成点评。</p></div></Notice> : null}
          {mediaError ? <Notice tone="warning">{mediaError}</Notice> : null}
          {recorder.error ? <Notice tone="warning"><div><p>{recorder.error}</p><button type="button" className="mt-1 inline-flex items-center gap-1 text-xs font-semibold underline" onClick={() => void recorder.start()}><RefreshCw size={13} />重新检测麦克风</button></div></Notice> : null}
          {transcription.data?.status === 'failed' ? <Notice tone="danger">录音转写失败，请直接输入或重新录音。</Notice> : null}
          {currentStatus === 'completed' && finalReport ? <FinalReport report={finalReport} /> : <>
            <div className="flex flex-wrap items-center gap-2">
              {recorder.recording ? <button type="button" className={secondaryButton} aria-label="停止录音" onClick={recorder.stop}><Square size={15} />停止录音</button> : <button type="button" className={secondaryButton} aria-label="开始录音" disabled={inputDisabled || uploadRecording.isPending || transcription.data?.status === 'queued' || transcription.data?.status === 'running'} onClick={() => void recorder.start()}><Mic size={15} />开始录音</button>}
              <span className="text-xs text-[#647460]">{recorder.recording ? '正在录音' : uploadRecording.isPending ? '正在上传录音' : transcription.data?.status === 'queued' || transcription.data?.status === 'running' ? 'AI 正在转写' : '可直接输入，或使用录音转写'}</span>
            </div>
            <div className="mt-3 flex items-end gap-2">
              <textarea aria-label="回答" rows={3} className={`${inputClass} mt-0 min-h-20 resize-y bg-white`} disabled={inputDisabled} value={answer} onChange={(event) => setAnswer(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) { event.preventDefault(); void submitAnswer() } }} placeholder={inputDisabled ? '面试已结束' : '输入你的回答，Ctrl/⌘ + Enter 提交'} />
              <button type="button" className={`${primaryButton} h-20 shrink-0 px-3`} aria-label="提交回答" title="提交回答" disabled={inputDisabled || !answer.trim()} onClick={() => void submitAnswer()}><Send size={17} /></button>
            </div>
          </>}
        </div>
      </section>

      <aside className="space-y-4 xl:sticky xl:top-5 xl:self-start">
        {currentProgress ? <Panel><ProgressRail progress={currentProgress} /></Panel> : null}
        <Panel><EvaluationRail evaluation={evaluation} /></Panel>
        {currentQuestion && currentStatus !== 'completed' ? <Panel title="本轮评分维度"><p className="text-sm font-semibold leading-6 text-[#203226]">{displayInterviewText(currentQuestion.competency, '综合表达与岗位匹配') ?? '综合表达与岗位匹配'}</p><p className="mt-3 inline-flex items-center gap-1 text-xs text-[#0f766e]">{speechAvailable ? <><Volume2 size={14} />问题由数字人自动朗读</> : '当前部署提供文字出题与评分，未部署语音朗读'}</p></Panel> : null}
      </aside>
    </main>
  </div>
}
