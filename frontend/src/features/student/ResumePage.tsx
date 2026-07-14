import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { FileUp } from 'lucide-react'
import { useState } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, Notice, PageHeader, Panel, primaryButton } from '../../components/Ui'

type Resume = { id: string; original_name: string; stored_name: string; media_type: string; size_bytes: number; parse_status: string }

export function ResumePage({ token }: { token: string }) {
  const queryClient = useQueryClient()
  const [file, setFile] = useState<File | null>(null)
  const resumes = useQuery({ queryKey: ['resumes'], queryFn: () => apiFetch<Resume[]>('/resumes', {}, token) })
  const upload = useMutation({ mutationFn: () => { const body = new FormData(); if (file) body.append('file', file); return apiFetch<Resume>('/resumes', { method: 'POST', body }, token) }, onSuccess: () => { setFile(null); queryClient.invalidateQueries({ queryKey: ['resumes'] }) } })
  return <><PageHeader title="简历管理" description="上传 PDF 或 DOCX 简历。针对岗位的修改建议采用原文、建议和理由对照，不自动写入虚假经历。" /><div className="grid gap-6 lg:grid-cols-[0.75fr_1.25fr]"><Panel title="上传简历"><label className="block border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-600"><FileUp className="mx-auto mb-3 text-teal-700" /><span>{file ? file.name : '选择 PDF 或 DOCX 文件'}</span><input className="sr-only" type="file" accept=".pdf,.docx" onChange={(e) => setFile(e.target.files?.[0] ?? null)} /></label><button className={`${primaryButton} mt-4 w-full`} disabled={!file || upload.isPending} onClick={() => upload.mutate()}>上传并解析</button>{upload.error ? <div className="mt-4"><Notice tone="danger">{upload.error.message}</Notice></div> : null}</Panel><Panel title="简历版本">{resumes.data?.length ? <div className="divide-y divide-slate-200">{resumes.data.map((resume) => <div key={resume.id} className="flex items-center justify-between gap-4 py-4"><div><p className="text-sm font-medium">{resume.original_name}</p><p className="mt-1 text-xs text-slate-500">{Math.ceil(resume.size_bytes / 1024)} KB</p></div><span className={`text-xs ${resume.parse_status === 'parsed' ? 'text-emerald-700' : 'text-amber-700'}`}>{resume.parse_status === 'parsed' ? '解析成功' : '需要手工录入'}</span></div>)}</div> : <EmptyState title="还没有简历" description="上传第一份简历以开始岗位匹配和模拟面试。" />}</Panel></div></>
}

