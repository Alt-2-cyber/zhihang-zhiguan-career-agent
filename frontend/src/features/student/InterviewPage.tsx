import { useMutation, useQuery } from '@tanstack/react-query'
import { MessageSquareText, Send } from 'lucide-react'
import { useState } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, Notice, PageHeader, Panel, inputClass, primaryButton } from '../../components/Ui'

type Resume = { id: string; original_name: string; parse_status: string }
type Job = { id: string; title: string; company: string }
type Session = { id: string; question: { question_id: string; question: string; competency: string } }
type AnswerResult = { evaluation: Record<string, number | string[]>; follow_up: { question_id: string; question: string; competency: string } | null }

export function InterviewPage({ token }: { token: string }) {
  const resumes = useQuery({ queryKey: ['resumes'], queryFn: () => apiFetch<Resume[]>('/resumes', {}, token) })
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: () => apiFetch<Job[]>('/jobs', {}, token) })
  const [resumeId, setResumeId] = useState(''); const [jobId, setJobId] = useState(''); const [answer, setAnswer] = useState(''); const [session, setSession] = useState<Session | null>(null); const [result, setResult] = useState<AnswerResult | null>(null)
  const start = useMutation({ mutationFn: () => apiFetch<Session>('/interviews', { method: 'POST', body: JSON.stringify({ resume_id: resumeId, job_id: jobId }) }, token), onSuccess: setSession })
  const submit = useMutation({ mutationFn: () => apiFetch<AnswerResult>(`/interviews/${session?.id}/answers`, { method: 'POST', body: JSON.stringify({ answer }) }, token), onSuccess: (value) => { setResult(value); setAnswer(''); if (value.follow_up && session) setSession({ ...session, question: value.follow_up }) } })
  return <><PageHeader title="模拟面试" description="问题与追问来自目标岗位和你的简历，评分只关注内容、相关性、结构和证据。" /><div className="grid gap-6 xl:grid-cols-[0.7fr_1.3fr]"><Panel title="面试设置"><div className="space-y-4"><label className="block text-sm font-medium">简历<select className={inputClass} value={resumeId} onChange={(e) => setResumeId(e.target.value)}><option value="">选择已解析简历</option>{resumes.data?.filter((r) => r.parse_status === 'parsed').map((r) => <option key={r.id} value={r.id}>{r.original_name}</option>)}</select></label><label className="block text-sm font-medium">目标岗位<select className={inputClass} value={jobId} onChange={(e) => setJobId(e.target.value)}><option value="">选择岗位</option>{jobs.data?.map((job) => <option key={job.id} value={job.id}>{job.title} · {job.company}</option>)}</select></label><button className={`${primaryButton} w-full`} disabled={!resumeId || !jobId || start.isPending} onClick={() => start.mutate()}><MessageSquareText size={17} />开始模拟面试</button></div></Panel><Panel title="面试对话">{session ? <div><p className="text-xs font-medium text-teal-700">考察：{session.question.competency}</p><h2 className="mt-3 text-lg font-semibold leading-8">{session.question.question}</h2><textarea rows={7} value={answer} onChange={(e) => setAnswer(e.target.value)} className={inputClass} placeholder="输入你的回答" /><button className={`${primaryButton} mt-4`} disabled={!answer.trim() || submit.isPending} onClick={() => submit.mutate()}><Send size={16} />提交回答</button>{result ? <div className="mt-6"><Notice tone="success">回答已评分，系统已生成针对性反馈。</Notice><div className="mt-4 grid gap-3 sm:grid-cols-2">{Object.entries(result.evaluation).filter(([, value]) => typeof value === 'number').map(([key, value]) => <div key={key} className="border border-slate-200 p-3"><p className="text-xs text-slate-500">{key}</p><p className="mt-1 text-xl font-semibold">{value as number}</p></div>)}</div></div> : null}</div> : <EmptyState title="准备开始面试" description="选择一份已解析简历和目标岗位。" />}</Panel></div></>
}

