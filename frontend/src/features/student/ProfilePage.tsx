import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, Sparkles } from 'lucide-react'
import { useState } from 'react'

import { apiFetch } from '../../app/api'
import { Notice, PageHeader, Panel, inputClass, primaryButton } from '../../components/Ui'

type Evidence = { source: string; quote: string }
type Strength = { name: string; level: string; evidence: Evidence[] }
type Analysis = {
  summary: string
  strengths: Strength[]
  gaps: string[]
  constraints: string[]
}
type Draft = { id: string; provider: string; status: string; analysis: Analysis }

export function ProfilePage({ token }: { token: string }) {
  const queryClient = useQueryClient()
  const [resumeText, setResumeText] = useState('')
  const [city, setCity] = useState('')
  const [industry, setIndustry] = useState('')
  const [draft, setDraft] = useState<Draft | null>(null)
  const [confirmed, setConfirmed] = useState(false)

  const profile = useQuery({
    queryKey: ['profile'],
    queryFn: () => apiFetch<Analysis & { status: string }>('/students/me/profile', {}, token),
    retry: false,
  })

  const analyze = useMutation({
    mutationFn: () =>
      apiFetch<Draft>(
        '/students/me/profile-analyses',
        {
          method: 'POST',
          body: JSON.stringify({
            resume_text: resumeText,
            preferences: { city, industry },
          }),
        },
        token,
      ),
    onSuccess: setDraft,
  })

  const confirm = useMutation({
    mutationFn: () =>
      apiFetch(`/students/me/profile-analyses/${draft?.id}/confirm`, { method: 'POST' }, token),
    onSuccess: () => {
      setConfirmed(true)
      queryClient.invalidateQueries({ queryKey: ['profile'] })
    },
  })

  const current = draft?.analysis ?? (profile.data ? profile.data : null)

  return (
    <>
      <PageHeader
        title="就业画像"
        description="从简历与就业偏好中提取能力证据。AI 生成内容只有在你确认后才会写入正式档案。"
      />

      {confirmed ? <div className="mb-5"><Notice tone="success">画像已确认</Notice></div> : null}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <Panel title="输入材料">
          <div className="space-y-4">
            <label className="block text-sm font-medium text-slate-700">
              简历文本
              <textarea
                aria-label="简历文本"
                rows={10}
                value={resumeText}
                onChange={(event) => setResumeText(event.target.value)}
                placeholder="粘贴简历内容，或在简历管理中上传 PDF / DOCX 文件"
                className={inputClass}
              />
            </label>
            <div className="grid gap-4 sm:grid-cols-2">
              <label className="block text-sm font-medium text-slate-700">
                目标城市
                <input aria-label="目标城市" value={city} onChange={(event) => setCity(event.target.value)} className={inputClass} />
              </label>
              <label className="block text-sm font-medium text-slate-700">
                目标行业
                <input aria-label="目标行业" value={industry} onChange={(event) => setIndustry(event.target.value)} className={inputClass} />
              </label>
            </div>
            {analyze.error ? <Notice tone="danger">{analyze.error.message}</Notice> : null}
            <button type="button" className={primaryButton} disabled={!resumeText.trim() || analyze.isPending} onClick={() => analyze.mutate()}>
              <Sparkles aria-hidden="true" size={17} />
              {analyze.isPending ? '正在分析' : '生成就业画像'}
            </button>
          </div>
        </Panel>

        <Panel title={draft ? '待确认画像' : '当前画像'}>
          {current ? (
            <div className="space-y-6">
              <div>
                <p className="text-xs font-medium text-slate-500">综合结论</p>
                <p className="mt-2 text-base leading-7 text-slate-900">{current.summary}</p>
              </div>
              <div>
                <p className="text-sm font-semibold">能力与证据</p>
                <div className="mt-3 divide-y divide-slate-200 border-y border-slate-200">
                  {current.strengths.map((strength) => (
                    <div key={strength.name} className="py-4">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-medium">{strength.name}</span>
                        <span className="text-xs text-teal-700">{strength.level}</span>
                      </div>
                      {strength.evidence.map((evidence) => (
                        <blockquote key={evidence.quote} className="mt-2 border-l-2 border-slate-300 pl-3 text-sm leading-6 text-slate-600">
                          {evidence.quote}
                        </blockquote>
                      ))}
                    </div>
                  ))}
                </div>
              </div>
              <div className="grid gap-5 sm:grid-cols-2">
                <div><p className="text-sm font-semibold">能力缺口</p><ul className="mt-2 space-y-2 text-sm text-slate-600">{current.gaps.map((item) => <li key={item}>• {item}</li>)}</ul></div>
                <div><p className="text-sm font-semibold">求职约束</p><ul className="mt-2 space-y-2 text-sm text-slate-600">{current.constraints.map((item) => <li key={item}>• {item}</li>)}</ul></div>
              </div>
              {draft ? (
                <button type="button" className={primaryButton} disabled={confirm.isPending} onClick={() => confirm.mutate()}>
                  <Check aria-hidden="true" size={17} />确认并保存画像
                </button>
              ) : null}
            </div>
          ) : (
            <div className="py-16 text-center text-sm text-slate-500">输入简历文本后生成第一份就业画像。</div>
          )}
        </Panel>
      </div>
    </>
  )
}

