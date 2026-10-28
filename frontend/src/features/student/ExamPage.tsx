import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  ArrowLeft,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  ListChecks,
  RotateCcw,
  Send,
  Star,
  TriangleAlert,
} from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { apiFetch } from '../../app/api'
import { EmptyState, LoadingState, Notice, Panel, primaryButton, secondaryButton } from '../../components/Ui'

type Exam = {
  id: string
  title: string
  skill_name: string
  status: string
  question_count: number
  passing_score: number
  duration_minutes: number
  started_at: string | null
  expires_at: string | null
  remaining_seconds: number | null
  latest_score: number | null
  latest_passed: boolean | null
  submitted_at: string | null
  created_at: string
}

type ExamQuestion = {
  id: string
  sequence: number
  prompt: string
  options: { key: string; text: string }[]
}

type ExamResult = {
  question_id: string
  sequence: number
  prompt?: string
  selected_answer: string
  correct_answer: string
  is_correct: boolean
  explanation: string
}

type ExamSubmission = {
  id: string
  exam_id: string
  answers: Record<string, string>
  score: number
  passed: boolean
  results: ExamResult[]
  submitted_at: string
}

type ExamDetail = Exam & {
  questions: ExamQuestion[]
  submission?: ExamSubmission | null
}

type LearningReview = {
  favorites: Array<{ question_id: string }>
}

function formatRemaining(seconds: number | null) {
  if (seconds === null) return '--:--'
  return `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`
}

function statusLabel(status: string) {
  if (status === 'in_progress') return '进行中'
  if (status === 'passed') return '已通过'
  if (status === 'submitted') return '已交卷'
  if (status === 'expired') return '已过期'
  return '待开始'
}

export function ExamPage({ token }: { token: string }) {
  const navigate = useNavigate()
  const { examId } = useParams<{ examId: string }>()
  const queryClient = useQueryClient()
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [activeQuestionIndex, setActiveQuestionIndex] = useState(0)
  const [remainingSeconds, setRemainingSeconds] = useState<number | null>(null)
  const [submission, setSubmission] = useState<ExamSubmission | null>(null)
  const [hydratedSnapshot, setHydratedSnapshot] = useState<string | null>(null)
  const autoSubmittedExamRef = useRef<string | null>(null)
  const answersRef = useRef(answers)
  const draftKey = examId ? `career-agent.exam-draft.${examId}` : null

  useEffect(() => {
    answersRef.current = answers
  }, [answers])

  const examQuery = useQuery({
    queryKey: ['growth-exam', examId],
    enabled: Boolean(examId),
    queryFn: () => apiFetch<ExamDetail>(`/growth/exams/${examId}`, {}, token),
  })
  const reviewQuery = useQuery({
    queryKey: ['growth-review'],
    queryFn: () => apiFetch<LearningReview>('/growth/review', {}, token),
    enabled: Boolean(examQuery.data),
  })

  useEffect(() => {
    if (!examQuery.data) return
    const snapshot = `${examQuery.data.id}:${examQuery.data.status}:${examQuery.data.submitted_at ?? ''}`
    const restored = examQuery.data.submission ?? null
    let draft: Record<string, string> = {}
    if (!restored && draftKey) {
      try {
        const parsed = JSON.parse(window.localStorage.getItem(draftKey) ?? '{}') as Record<string, unknown>
        draft = Object.fromEntries(
          Object.entries(parsed).filter(([, value]) => typeof value === 'string'),
        ) as Record<string, string>
      } catch {
        window.localStorage.removeItem(draftKey)
      }
    }
    setAnswers(restored?.answers ?? draft)
    setSubmission(restored)
    setActiveQuestionIndex(0)
    autoSubmittedExamRef.current = null
    setHydratedSnapshot(snapshot)
  }, [draftKey, examQuery.data])

  const startExam = useMutation({
    mutationFn: () => apiFetch<ExamDetail>(`/growth/exams/${examId}/start`, { method: 'POST' }, token),
    onSuccess: (exam) => {
      setAnswers(exam.submission?.answers ?? {})
      setSubmission(exam.submission ?? null)
      queryClient.setQueryData(['growth-exam', examId], exam)
    },
  })

  const submitExam = useMutation({
    mutationFn: (payload: { answers: Record<string, string> }) =>
      apiFetch<ExamSubmission>(
        `/growth/exams/${examId}/submit`,
        { method: 'POST', body: JSON.stringify(payload) },
        token,
      ),
    onSuccess: async (result) => {
      setSubmission(result)
      if (draftKey) window.localStorage.removeItem(draftKey)
      queryClient.setQueryData<ExamDetail | undefined>(['growth-exam', examId], (current) =>
        current
          ? {
              ...current,
              status: result.passed ? 'passed' : 'submitted',
              latest_score: result.score,
              latest_passed: result.passed,
              submitted_at: result.submitted_at,
              submission: result,
            }
          : current,
      )
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['growth-exams'] }),
        queryClient.invalidateQueries({ queryKey: ['growth-review'] }),
        queryClient.invalidateQueries({ queryKey: ['growth-overview'] }),
      ])
    },
  })

  const favoriteQuestion = useMutation({
    mutationFn: (questionId: string) => apiFetch(`/growth/questions/${questionId}/favorite`, { method: 'POST' }, token),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['growth-review'] }),
  })

  const exam = examQuery.data
  const questions = exam?.questions ?? []
  const activeQuestion = questions[activeQuestionIndex] ?? null
  const answeredCount = questions.filter((question) => Boolean(answers[question.id])).length
  const isFinished = Boolean(submission || exam?.status === 'passed' || exam?.status === 'submitted')
  const examSnapshot = exam ? `${exam.id}:${exam.status}:${exam.submitted_at ?? ''}` : null
  const favoritedQuestionIds = useMemo(
    () => new Set(reviewQuery.data?.favorites.map((item) => item.question_id) ?? []),
    [reviewQuery.data],
  )

  useEffect(() => {
    if (!draftKey || !examSnapshot || hydratedSnapshot !== examSnapshot) return
    if (exam?.status === 'in_progress' && !submission) {
      window.localStorage.setItem(draftKey, JSON.stringify(answers))
    } else {
      window.localStorage.removeItem(draftKey)
    }
  }, [answers, draftKey, exam?.status, examSnapshot, hydratedSnapshot, submission])

  useEffect(() => {
    if (!exam?.expires_at || exam.status !== 'in_progress' || submission) {
      setRemainingSeconds(null)
      return undefined
    }
    const updateRemaining = () => {
      const next = Math.max(0, Math.ceil((new Date(exam.expires_at!).getTime() - Date.now()) / 1000))
      setRemainingSeconds(next)
      if (next === 0 && autoSubmittedExamRef.current !== exam.id) {
        autoSubmittedExamRef.current = exam.id
        submitExam.mutate({ answers: answersRef.current })
      }
    }
    updateRemaining()
    const timer = window.setInterval(updateRemaining, 1_000)
    return () => window.clearInterval(timer)
  }, [exam?.expires_at, exam?.status, exam?.id, submission, submitExam])

  useEffect(() => {
    if (!exam || exam.status !== 'in_progress' || submission) return undefined
    const warnBeforeLeave = (event: BeforeUnloadEvent) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warnBeforeLeave)
    return () => window.removeEventListener('beforeunload', warnBeforeLeave)
  }, [exam, submission])

  const leaveExam = () => {
    if (exam?.status === 'in_progress' && answeredCount > 0 && !window.confirm('离开后当前未交卷答案只保存在本页，确定离开吗？')) return
    navigate('/student/learning')
  }

  const submit = () => {
    if (!examId || submitExam.isPending || isFinished) return
    submitExam.mutate({ answers })
  }

  const selectAnswer = (questionId: string, value: string) => {
    const next = { ...answersRef.current, [questionId]: value }
    answersRef.current = next
    setAnswers(next)
    if (draftKey) window.localStorage.setItem(draftKey, JSON.stringify(next))
  }

  if (examQuery.isLoading) return <LoadingState />
  if (examQuery.isError) return <EmptyState title="考试加载失败" description={examQuery.error.message} />
  if (!exam || !examId) return <EmptyState title="考试不存在" description="请返回学习成长重新选择一场考试。" />

  return (
    <div className="entry-reveal space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button type="button" className={`${secondaryButton} h-9 px-3 text-xs`} onClick={leaveExam}><ArrowLeft size={15} />学习成长</button>
        <span className="text-xs font-semibold tracking-[0.12em] text-[#52645a]">专注考试 / {statusLabel(exam.status)}</span>
      </div>

      <header className="border border-[#102015]/15 bg-[#112219] px-5 py-5 text-white shadow-[6px_6px_0_rgba(17,34,25,0.18)] sm:px-7">
        <div className="flex flex-wrap items-start justify-between gap-5">
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-[0.14em] text-[#c7ff4c]">{exam.skill_name}</p>
            <h1 className="mt-2 text-2xl font-bold sm:text-3xl">{exam.title}</h1>
            <p className="mt-2 text-sm text-[#cfdbc9]">{exam.question_count} 道单选题 · {exam.passing_score} 分通过 · 时长 {exam.duration_minutes} 分钟</p>
          </div>
          {exam.status === 'in_progress' && !submission ? (
            <div className={`flex items-center gap-2 border px-4 py-2 text-sm font-bold ${remainingSeconds !== null && remainingSeconds <= 60 ? 'border-[#ff7358] bg-[#702314]' : 'border-[#c7ff4c]/40 bg-white/5'}`} aria-live="polite"><Clock3 size={17} />{formatRemaining(remainingSeconds)}</div>
          ) : null}
        </div>
      </header>

      {startExam.isError ? <Notice tone="danger">{startExam.error.message}</Notice> : null}
      {submitExam.isError ? <Notice tone="danger">{submitExam.error.message}</Notice> : null}

      {exam.status === 'generated' ? (
        <Panel title="开始考试">
          <div className="grid gap-5 lg:grid-cols-[1fr_auto] lg:items-center">
            <div>
              <p className="text-sm font-semibold text-[#102015]">准备好后再开始计时</p>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#526051]">开始后题目会按顺序呈现，剩余时间由服务端截止时间计算。刷新或重新打开本页面可以恢复试卷状态。</p>
              <div className="mt-4 flex flex-wrap gap-3 text-xs text-[#647460]"><span className="inline-flex items-center gap-1"><ListChecks size={14} />{questions.length} 题</span><span className="inline-flex items-center gap-1"><Clock3 size={14} />{exam.duration_minutes} 分钟</span><span className="inline-flex items-center gap-1"><TriangleAlert size={14} />交卷后不可重复提交</span></div>
            </div>
            <button className={primaryButton} disabled={startExam.isPending} onClick={() => startExam.mutate()}><Clock3 size={17} />{startExam.isPending ? '正在开始...' : '开始限时测验'}</button>
          </div>
        </Panel>
      ) : null}

      {exam.status === 'expired' ? <Notice tone="warning">本场考试已过期，系统没有替你提交未完成答案。请返回学习成长重新生成考试。</Notice> : null}

      {exam.status === 'in_progress' && !submission ? (
        <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_250px]">
          <Panel title={`第 ${activeQuestionIndex + 1} / ${questions.length} 题`} className="min-h-[520px]">
            {activeQuestion ? (
              <div className="flex min-h-[430px] flex-col">
                <div className="flex-1">
                  <div className="flex items-start justify-between gap-4">
                    <h2 className="max-w-3xl text-lg font-bold leading-8 text-[#102015]">{activeQuestion.prompt}</h2>
                    <button type="button" className={`grid size-9 shrink-0 place-items-center border ${favoritedQuestionIds.has(activeQuestion.id) ? 'border-amber-500 bg-amber-50 text-amber-700' : 'border-[#102015]/15 text-[#647460] hover:border-amber-500 hover:text-amber-700'}`} aria-label={favoritedQuestionIds.has(activeQuestion.id) ? '取消收藏题目' : '收藏题目'} title={favoritedQuestionIds.has(activeQuestion.id) ? '取消收藏题目' : '收藏题目'} onClick={() => favoriteQuestion.mutate(activeQuestion.id)}><Star size={17} fill={favoritedQuestionIds.has(activeQuestion.id) ? 'currentColor' : 'none'} /></button>
                  </div>
                  <div className="mt-8 grid gap-3">
                    {activeQuestion.options.map((option) => {
                      const selected = answers[activeQuestion.id] === option.key
                      return <label key={option.key} className={`flex cursor-pointer items-start gap-3 border px-4 py-3 text-sm transition ${selected ? 'border-[#0f766e] bg-[#edf7f1] text-[#102015] shadow-[3px_3px_0_rgba(15,118,110,0.14)]' : 'border-[#102015]/15 bg-white/60 text-[#526051] hover:border-[#0f766e]'}`}><input type="radio" name={activeQuestion.id} value={option.key} checked={selected} onChange={() => selectAnswer(activeQuestion.id, option.key)} className="mt-1 accent-[#0f766e]" /><span><span className="mr-2 font-bold text-[#0f766e]">{option.key}</span>{option.text}</span></label>
                    })}
                  </div>
                </div>
                <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-[#102015]/10 pt-4">
                  <button type="button" className={secondaryButton} disabled={activeQuestionIndex === 0} onClick={() => setActiveQuestionIndex((index) => Math.max(0, index - 1))}><ChevronLeft size={16} />上一题</button>
                  {activeQuestionIndex < questions.length - 1 ? <button type="button" className={secondaryButton} onClick={() => setActiveQuestionIndex((index) => Math.min(questions.length - 1, index + 1))}>下一题<ChevronRight size={16} /></button> : <button type="button" className={primaryButton} disabled={answeredCount === 0 || submitExam.isPending} onClick={submit}><Send size={16} />{submitExam.isPending ? '正在交卷...' : `提交答卷 ${answeredCount}/${questions.length}`}</button>}
                </div>
              </div>
            ) : <EmptyState title="题目暂不可用" description="请刷新本页面重新加载试卷。" />}
          </Panel>

          <aside className="lg:sticky lg:top-24">
            <Panel title="答题卡">
              <div className="grid grid-cols-5 gap-2">
                {questions.map((question, index) => <button key={question.id} type="button" aria-label={`第 ${index + 1} 题`} aria-current={index === activeQuestionIndex ? 'step' : undefined} onClick={() => setActiveQuestionIndex(index)} className={`grid aspect-square place-items-center border text-xs font-bold transition ${index === activeQuestionIndex ? 'border-[#102015] bg-[#102015] text-[#c7ff4c]' : answers[question.id] ? 'border-[#0f766e] bg-[#edf7f1] text-[#0f766e]' : 'border-[#102015]/15 bg-white/60 text-[#647460] hover:border-[#0f766e]'}`}>{index + 1}</button>)}
              </div>
              <div className="mt-5 space-y-2 text-xs text-[#647460]"><p className="flex items-center justify-between"><span>已作答</span><strong className="text-[#102015]">{answeredCount} / {questions.length}</strong></p><p className="flex items-center justify-between"><span>通过线</span><strong className="text-[#102015]">{exam.passing_score} 分</strong></p></div>
              <button type="button" className={`${primaryButton} mt-5 w-full`} disabled={answeredCount === 0 || submitExam.isPending} onClick={submit}><Send size={16} />提交答卷</button>
              <p className="mt-3 text-[11px] leading-5 text-[#647460]">提交后会立即评分，并把错题解释写入学习复盘。</p>
            </Panel>
          </aside>
        </div>
      ) : null}

      {isFinished && submission ? (
        <section className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
            <Panel title="本次结果">
              <div className="flex items-center gap-5">
                <div className={`grid size-28 shrink-0 place-items-center rounded-full border-8 ${submission.passed ? 'border-emerald-500 bg-emerald-50 text-emerald-800' : 'border-amber-500 bg-amber-50 text-amber-800'}`}><span className="text-3xl font-bold">{submission.score}</span></div>
                <div><p className="text-lg font-bold text-[#102015]">{submission.passed ? '已通过' : '需要补强'}</p><p className="mt-2 text-sm text-[#526051]">答对 {submission.results.filter((item) => item.is_correct).length} / {submission.results.length} 题 · 通过线 {exam.passing_score} 分</p><p className="mt-2 text-xs text-[#647460]">提交时间 {new Date(submission.submitted_at).toLocaleString('zh-CN', { hour12: false })}</p></div>
              </div>
              <button type="button" className={`${secondaryButton} mt-6`} onClick={() => navigate('/student/learning')}><ArrowLeft size={16} />返回学习成长</button>
            </Panel>
            <Panel title="下一步">
              <div className="grid gap-3 sm:grid-cols-2"><div className="border-l-2 border-[#0f766e] bg-[#edf7f1] px-4 py-3"><p className="text-sm font-semibold text-[#102015]">复盘错题</p><p className="mt-1 text-xs leading-5 text-[#526051]">错题解释已进入复盘，可从薄弱技能继续创建学习任务。</p></div><div className="border-l-2 border-[#0284c7] bg-sky-50 px-4 py-3"><p className="text-sm font-semibold text-[#102015]">继续提升</p><p className="mt-1 text-xs leading-5 text-[#526051]">返回学习成长查看能力雷达和学习趋势，避免只看一次分数。</p></div></div>
            </Panel>
          </div>
          <Panel title="逐题解析">
            <div className="divide-y divide-[#102015]/10">{questions.map((question) => { const result = submission.results.find((item) => item.question_id === question.id); if (!result) return null; const favorited = favoritedQuestionIds.has(question.id); return <article key={question.id} className="py-5 first:pt-0 last:pb-0"><div className="flex items-start gap-3"><div className={`mt-0.5 grid size-7 shrink-0 place-items-center rounded-full ${result.is_correct ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>{result.is_correct ? <CheckCircle2 size={16} /> : <RotateCcw size={16} />}</div><div className="min-w-0 flex-1"><div className="flex items-start justify-between gap-3"><p className="text-sm font-semibold leading-6 text-[#102015]">{question.sequence}. {result.prompt ?? question.prompt}</p><button type="button" className={`grid size-8 shrink-0 place-items-center ${favorited ? 'text-amber-600' : 'text-[#647460]'}`} aria-label={favorited ? '取消收藏题目' : '收藏题目'} onClick={() => favoriteQuestion.mutate(question.id)}><Star size={16} fill={favorited ? 'currentColor' : 'none'} /></button></div><p className="mt-2 text-xs text-[#526051]">你的答案：{result.selected_answer || '未作答'} · 正确答案：{result.correct_answer}</p><p className="mt-2 border-l-2 border-[#0f766e] bg-[#edf7f1] px-3 py-2 text-xs leading-5 text-[#526051]">{result.explanation}</p></div></div></article> })}</div>
          </Panel>
        </section>
      ) : null}
    </div>
  )
}
