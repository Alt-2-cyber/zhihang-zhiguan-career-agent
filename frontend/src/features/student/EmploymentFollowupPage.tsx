import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircle2, ClipboardPlus, ExternalLink, Send, ShieldCheck } from 'lucide-react'
import { useMemo, useState } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, LoadingState, Notice, PageHeader, Panel, primaryButton, secondaryButton } from '../../components/Ui'
import { AskAgentButton } from '../chat/AskAgentButton'

type Application = { id: string; job_id: string; stage: string }
type Job = { id: string; title: string; company: string }
type Followup = { id: string; milestone: string; due_date: string; status: string; student_completed_at: string | null; employer_completed_at: string | null }
type EmploymentRecord = {
  id: string
  application_id: string
  company: string
  job_title: string
  onboard_date: string
  status: string
  student_consent: boolean
  employer_invitation_enabled: boolean
  employer_review_received: boolean
  employee_feedback: { overall_score: number; moderation_status: string; would_recommend: boolean } | null
  interview_experience: { moderation_status: string; advice: string } | null
  followups: Followup[]
}

const scoreKeys = ['job_consistency', 'interview_difficulty', 'workload', 'mentoring', 'team_climate', 'compensation_delivery', 'growth_space'] as const
const scoreLabels: Record<(typeof scoreKeys)[number], string> = {
  job_consistency: '岗位一致',
  interview_difficulty: '面试难度',
  workload: '工作强度',
  mentoring: '带教培训',
  team_climate: '团队氛围',
  compensation_delivery: '薪酬兑现',
  growth_space: '成长空间',
}
const milestoneLabel: Record<string, string> = { day_7: '入职 7 天', day_30: '入职 30 天', day_90: '入职 90 天', day_180: '入职 180 天' }

function defaultScores() {
  return Object.fromEntries(scoreKeys.map((key) => [key, 4])) as Record<(typeof scoreKeys)[number], number>
}

export function EmploymentFollowupPage({ token }: { token: string }) {
  const queryClient = useQueryClient()
  const [applicationId, setApplicationId] = useState('')
  const [onboardDate, setOnboardDate] = useState(() => new Date().toISOString().slice(0, 10))
  const [consent, setConsent] = useState(true)
  const [selectedRecordId, setSelectedRecordId] = useState<string | null>(null)
  const [scores, setScores] = useState(defaultScores)
  const [requirements, setRequirements] = useState('')
  const [experience, setExperience] = useState('')
  const [recommendation, setRecommendation] = useState('')
  const [process, setProcess] = useState('')
  const [questions, setQuestions] = useState('')
  const [advice, setAdvice] = useState('')
  const [inviteToken, setInviteToken] = useState<string | null>(null)
  const records = useQuery({ queryKey: ['employment-records'], queryFn: () => apiFetch<EmploymentRecord[]>('/employment/records', {}, token) })
  const applications = useQuery({ queryKey: ['applications'], queryFn: () => apiFetch<Application[]>('/applications', {}, token) })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: () => apiFetch<Job[]>('/jobs', {}, token) })
  const create = useMutation({
    mutationFn: () => apiFetch<EmploymentRecord>('/employment/records', { method: 'POST', body: JSON.stringify({ application_id: applicationId, onboard_date: onboardDate, student_consent: consent }) }, token),
    onSuccess: async (record) => {
      setSelectedRecordId(record.id)
      await queryClient.invalidateQueries({ queryKey: ['employment-records'] })
    },
  })
  const submitFeedback = useMutation({
    mutationFn: (recordId: string) => apiFetch(`/employment/records/${recordId}/employee-feedback`, {
      method: 'PUT',
      body: JSON.stringify({
        scores,
        requirements,
        experience,
        recommendation,
        would_recommend: scores.growth_space >= 4 && scores.team_climate >= 4,
        interview: { difficulty: scores.interview_difficulty, rounds: 3, process, questions, advice },
      }),
    }, token),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['employment-records'] })
    },
  })
  const invite = useMutation({
    mutationFn: (recordId: string) => apiFetch<{ token: string; expires_at: string; warning: string }>(`/employment/records/${recordId}/employer-invitations`, { method: 'POST' }, token),
    onSuccess: (payload) => setInviteToken(payload.token),
  })
  const jobMap = useMemo(() => new Map(jobs.data?.map((job) => [job.id, job]) ?? []), [jobs.data])
  const offerApplications = applications.data?.filter((item) => item.stage === 'offered') ?? []
  const selectedRecord = records.data?.find((record) => record.id === selectedRecordId) ?? records.data?.[0] ?? null

  if (records.isLoading || applications.isLoading || jobs.isLoading) return <LoadingState />

  return (
    <>
      <PageHeader title="入职跟踪" description="把已录用投递转为就业记录，追踪 7/30/90/180 天回访，并沉淀学生与企业的双向反馈。" action={selectedRecord ? <AskAgentButton role="student" context={{ type: 'employment_record', id: selectedRecord.id }} /> : undefined} />
      <div className="grid gap-6 xl:grid-cols-[0.85fr_1.15fr]">
        <div className="space-y-6">
          <Panel title="从录用投递建立就业记录">
            {create.isError ? <Notice tone="danger">{create.error.message}</Notice> : null}
            <div className="space-y-3">
              <select aria-label="选择已录用投递" value={applicationId} onChange={(event) => setApplicationId(event.target.value)} className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm">
                <option value="">选择已录用投递</option>
                {offerApplications.map((application) => {
                  const job = jobMap.get(application.job_id)
                  return <option key={application.id} value={application.id}>{job?.company ?? '企业'} · {job?.title ?? '岗位'}</option>
                })}
              </select>
              <input aria-label="入职日期" type="date" value={onboardDate} onChange={(event) => setOnboardDate(event.target.value)} className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm" />
              <label className="flex items-center gap-2 text-sm text-slate-700"><input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} />授权邀请企业提交就业质量评价</label>
              <button className={`${primaryButton} w-full`} disabled={!applicationId || create.isPending} onClick={() => create.mutate()}><ClipboardPlus size={17} />建立就业跟踪</button>
            </div>
          </Panel>
          <Panel title="就业记录">
            {records.data?.length ? <div className="space-y-3">{records.data.map((record) => <button key={record.id} type="button" onClick={() => setSelectedRecordId(record.id)} className={`w-full rounded-md border p-4 text-left ${selectedRecord?.id === record.id ? 'border-teal-700 bg-teal-50' : 'border-slate-200 bg-white hover:bg-slate-50'}`}><div className="flex items-center justify-between gap-3"><p className="font-medium">{record.company}</p>{record.employer_review_received ? <ShieldCheck className="text-emerald-600" size={18} /> : null}</div><p className="mt-1 text-sm text-slate-600">{record.job_title}</p><p className="mt-2 text-xs text-slate-500">入职：{record.onboard_date} · 学生反馈：{record.employee_feedback ? record.employee_feedback.moderation_status : '未提交'}</p></button>)}</div> : <EmptyState title="暂无就业记录" description="先把录用投递转为就业记录，再进入入职跟踪。" />}
          </Panel>
        </div>

        <Panel title="双向反馈闭环">
          {selectedRecord ? (
            <div className="space-y-5">
              <div className="grid gap-3 sm:grid-cols-4">
                {selectedRecord.followups.map((followup) => <div key={followup.id} className="border border-slate-200 bg-slate-50 p-3"><p className="text-xs text-slate-500">{milestoneLabel[followup.milestone] ?? followup.milestone}</p><p className="mt-1 text-sm font-medium">{followup.due_date}</p><p className="mt-1 text-xs text-slate-500">{followup.status}</p></div>)}
              </div>
              {invite.isError ? <Notice tone="danger">{invite.error.message}</Notice> : null}
              {submitFeedback.isError ? <Notice tone="danger">{submitFeedback.error.message}</Notice> : null}
              {inviteToken ? <Notice tone="warning"><ExternalLink size={16} />企业评价链接只展示一次：/employer-review/{inviteToken}</Notice> : null}
              <div className="flex flex-wrap gap-2">
                <button className={secondaryButton} disabled={!selectedRecord.employer_invitation_enabled || invite.isPending || selectedRecord.employer_review_received} onClick={() => invite.mutate(selectedRecord.id)}><Send size={16} />生成企业评价邀请</button>
                {selectedRecord.employer_review_received ? <span className="inline-flex h-10 items-center gap-2 text-sm text-emerald-700"><CheckCircle2 size={16} />企业评价已收到</span> : null}
              </div>
              <div className="border-t border-slate-200 pt-5">
                <p className="text-sm font-semibold">学生企业反馈</p>
                <div className="mt-3 grid gap-3 sm:grid-cols-2">
                  {scoreKeys.map((key) => <label key={key} className="text-sm text-slate-700">{scoreLabels[key]}：{scores[key]}<input type="range" min={1} max={5} value={scores[key]} onChange={(event) => setScores((current) => ({ ...current, [key]: Number(event.target.value) }))} className="mt-2 w-full" /></label>)}
                </div>
                <div className="mt-4 grid gap-3">
                  <textarea aria-label="企业要求" value={requirements} onChange={(event) => setRequirements(event.target.value)} rows={3} placeholder="企业真实要求、试用期看重的能力、工作标准" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  <textarea aria-label="工作体验" value={experience} onChange={(event) => setExperience(event.target.value)} rows={3} placeholder="工作内容、强度、团队、导师和薪酬兑现情况" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  <textarea aria-label="给后来者建议" value={recommendation} onChange={(event) => setRecommendation(event.target.value)} rows={3} placeholder="给后续面试者和学弟学妹的建议" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  <textarea aria-label="面试流程" value={process} onChange={(event) => setProcess(event.target.value)} rows={2} placeholder="面试流程、轮次和周期" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  <textarea aria-label="面试问题" value={questions} onChange={(event) => setQuestions(event.target.value)} rows={2} placeholder="面试重点问题" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
                  <textarea aria-label="面试建议" value={advice} onChange={(event) => setAdvice(event.target.value)} rows={2} placeholder="面试准备建议" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
                </div>
                <button className={`${primaryButton} mt-4`} disabled={[requirements, experience, recommendation, process, questions, advice].some((item) => item.trim().length < 10) || submitFeedback.isPending} onClick={() => submitFeedback.mutate(selectedRecord.id)}><Send size={17} />提交学生反馈</button>
              </div>
            </div>
          ) : <EmptyState title="选择一条就业记录" description="查看回访节点、企业邀请和学生反馈表。" />}
        </Panel>
      </div>
    </>
  )
}
