import { useMutation, useQuery } from '@tanstack/react-query'
import { CheckCircle2, Send, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { useParams } from 'react-router-dom'

import { apiFetch } from '../../app/api'
import { EmptyState, LoadingState, Notice, PageHeader, Panel, primaryButton } from '../../components/Ui'

type Invitation = { company: string; job_title: string; expires_at: string; dimensions: string[] }

const labels: Record<string, string> = {
  role_readiness: '适岗速度',
  professional_skill: '专业技能',
  learning: '学习能力',
  communication: '沟通协作',
  delivery_quality: '任务质量',
  initiative: '主动性',
  professionalism: '职业规范',
}

export function EmployerReviewPage() {
  const { token = '' } = useParams()
  const [scores, setScores] = useState<Record<string, number>>({})
  const [trialResult, setTrialResult] = useState('passed')
  const [strengths, setStrengths] = useState('')
  const [improvement, setImprovement] = useState('')
  const [curriculumSuggestion, setCurriculumSuggestion] = useState('')
  const query = useQuery({
    queryKey: ['employer-invitation', token],
    queryFn: async () => {
      const payload = await apiFetch<Invitation>(`/employment/employer-invitations/${token}`)
      setScores(Object.fromEntries(payload.dimensions.map((dimension) => [dimension, 4])))
      return payload
    },
    enabled: Boolean(token),
    retry: false,
  })
  const submit = useMutation({
    mutationFn: () => apiFetch(`/employment/employer-invitations/${token}/review`, {
      method: 'POST',
      body: JSON.stringify({ scores, trial_result: trialResult, strengths, improvement, curriculum_suggestion: curriculumSuggestion || null }),
    }),
  })

  if (query.isLoading) return <LoadingState />
  if (query.isError || !query.data) return <EmptyState title="评价邀请不可用" description="链接可能已过期、已使用或被撤销。" />
  if (submit.isSuccess) {
    return <main className="mx-auto max-w-3xl px-4 py-10"><Panel><div className="py-10 text-center"><CheckCircle2 className="mx-auto text-emerald-600" size={42} /><h1 className="mt-4 text-2xl font-semibold">评价已提交</h1><p className="mt-2 text-sm text-slate-600">感谢参与学校就业质量回访，链接已自动失效。</p></div></Panel></main>
  }

  return (
    <main className="mx-auto max-w-4xl px-4 py-8">
      <PageHeader title="企业就业质量评价" description="请基于学生近期真实表现填写。学校仅用于就业质量分析和课程改进，展示前会进行审核与脱敏。" />
      <Panel>
        <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-200 pb-5">
          <div>
            <p className="text-lg font-semibold">{query.data.company}</p>
            <p className="mt-1 text-sm text-slate-600">{query.data.job_title}</p>
          </div>
          <span className="inline-flex items-center gap-2 rounded bg-teal-50 px-3 py-2 text-sm text-teal-900"><ShieldCheck size={16} />有效期至 {new Date(query.data.expires_at).toLocaleString()}</span>
        </div>
        {submit.isError ? <div className="mt-4"><Notice tone="danger">{submit.error.message}</Notice></div> : null}
        <div className="mt-5 grid gap-4 sm:grid-cols-2">
          {query.data.dimensions.map((dimension) => <label key={dimension} className="text-sm text-slate-700">{labels[dimension] ?? dimension}：{scores[dimension] ?? 4}<input type="range" min={1} max={5} value={scores[dimension] ?? 4} onChange={(event) => setScores((current) => ({ ...current, [dimension]: Number(event.target.value) }))} className="mt-2 w-full" /></label>)}
        </div>
        <div className="mt-5 grid gap-3">
          <select aria-label="试用期结果" value={trialResult} onChange={(event) => setTrialResult(event.target.value)} className="h-10 rounded-md border border-slate-300 bg-white px-3 text-sm">
            <option value="passed">通过/表现稳定</option>
            <option value="observing">继续观察</option>
            <option value="not_passed">未通过</option>
          </select>
          <textarea aria-label="表现亮点" value={strengths} onChange={(event) => setStrengths(event.target.value)} rows={4} placeholder="近期表现亮点、完成的任务、适应速度" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <textarea aria-label="改进建议" value={improvement} onChange={(event) => setImprovement(event.target.value)} rows={4} placeholder="还需要提升的能力、职业规范或协作方式" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
          <textarea aria-label="课程建议" value={curriculumSuggestion} onChange={(event) => setCurriculumSuggestion(event.target.value)} rows={3} placeholder="对学校课程、实训或就业指导的建议，可选" className="rounded-md border border-slate-300 px-3 py-2 text-sm" />
        </div>
        <button className={`${primaryButton} mt-5`} disabled={strengths.trim().length < 10 || improvement.trim().length < 10 || submit.isPending} onClick={() => submit.mutate()}><Send size={17} />提交评价</button>
      </Panel>
    </main>
  )
}
