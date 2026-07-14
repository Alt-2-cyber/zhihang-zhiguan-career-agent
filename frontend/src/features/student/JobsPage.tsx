import { useMutation, useQuery } from '@tanstack/react-query'
import { Building2, MapPin, SearchCheck } from 'lucide-react'
import { useState } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, LoadingState, PageHeader, Panel, primaryButton } from '../../components/Ui'

type Job = { id: string; title: string; company: string; location: string; description: string }
type Match = { job_id: string; recommendation: string; overall_score: number; dimensions: { dimension: string; score: number; evidence: { source: string; quote: string }[] }[]; gaps: string[]; actions: string[] }
const dimensionLabels: Record<string, string> = { requirements: '硬性条件', skills: '技能', experience: '经历', preferences: '偏好', growth: '发展方向' }

export function JobsPage({ token }: { token: string }) {
  const jobs = useQuery({ queryKey: ['jobs'], queryFn: () => apiFetch<Job[]>('/jobs', {}, token) })
  const [selected, setSelected] = useState<Job | null>(null)
  const match = useMutation({ mutationFn: (id: string) => apiFetch<Match>(`/jobs/${id}/match`, { method: 'POST' }, token) })
  if (jobs.isLoading) return <LoadingState />
  return <><PageHeader title="岗位匹配" description="基于已确认画像，从硬性条件、技能、经历、偏好和发展方向五个维度提供有证据的匹配建议。" /><div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]"><Panel title="岗位库">{jobs.data?.length ? <div className="divide-y divide-slate-200">{jobs.data.map((job) => <button key={job.id} type="button" onClick={() => { setSelected(job); match.reset() }} className={`w-full px-2 py-4 text-left ${selected?.id === job.id ? 'bg-teal-50' : 'hover:bg-slate-50'}`}><p className="font-medium">{job.title}</p><div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500"><span className="flex items-center gap-1"><Building2 size={13} />{job.company}</span><span className="flex items-center gap-1"><MapPin size={13} />{job.location}</span></div></button>)}</div> : <EmptyState title="岗位库为空" description="导入百川云璟数据或运行演示数据初始化。" />}</Panel><Panel title="匹配分析">{selected ? <div><h2 className="text-lg font-semibold">{selected.title}</h2><p className="mt-3 text-sm leading-6 text-slate-600">{selected.description}</p><button className={`${primaryButton} mt-5`} onClick={() => match.mutate(selected.id)}><SearchCheck size={17} />开始五维匹配</button>{match.data ? <div className="mt-6 border-t border-slate-200 pt-5"><div className="flex items-end justify-between"><div><p className="text-xs text-slate-500">综合匹配度</p><p className="mt-1 text-3xl font-semibold text-teal-700">{match.data.overall_score}</p></div><span className="text-sm font-medium">{match.data.recommendation === 'apply' ? '适合投递' : '补充后投递'}</span></div><div className="mt-5 space-y-4">{match.data.dimensions.map((item) => <div key={item.dimension}><div className="flex justify-between text-sm"><span>{dimensionLabels[item.dimension]}</span><span>{item.score}</span></div><div className="mt-1.5 h-2 bg-slate-100"><div className="h-full bg-teal-700" style={{ width: `${item.score}%` }} /></div><p className="mt-2 text-xs text-slate-500">依据：{item.evidence[0]?.quote}</p></div>)}</div></div> : null}</div> : <EmptyState title="选择一个岗位" description="查看岗位详情并运行五维匹配分析。" />}</Panel></div></>
}

