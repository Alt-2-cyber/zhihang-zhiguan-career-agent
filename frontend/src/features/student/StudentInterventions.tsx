import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Send } from 'lucide-react'
import { useState } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, Notice, Panel, inputClass, primaryButton } from '../../components/Ui'

type Intervention = {
  id: string
  title: string
  description: string
  status: string
  feedback: string | null
}

const statusLabels: Record<string, string> = {
  assigned: '待完成',
  acknowledged: '进行中',
  submitted: '待辅导员确认',
  resolved: '已完成',
  cancelled: '已取消',
}

export function StudentInterventions({ token }: { token: string }) {
  const queryClient = useQueryClient()
  const [feedback, setFeedback] = useState<Record<string, string>>({})
  const query = useQuery({
    queryKey: ['interventions'],
    queryFn: () => apiFetch<Intervention[]>('/interventions', {}, token),
  })
  const submit = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) =>
      apiFetch(
        `/interventions/${id}/submit`,
        { method: 'PATCH', body: JSON.stringify({ feedback: value }) },
        token,
      ),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['interventions'] }),
  })

  return (
    <Panel title="辅导员帮扶任务" className="mt-6">
      {query.data?.length ? (
        <div className="divide-y divide-slate-200">
          {query.data.map((item) => (
            <article key={item.id} className="py-4 first:pt-0 last:pb-0">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <h3 className="text-sm font-semibold">{item.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{item.description}</p>
                </div>
                <span className="shrink-0 text-xs text-teal-700">
                  {statusLabels[item.status] ?? item.status}
                </span>
              </div>
              {item.feedback ? (
                <div className="mt-3">
                  <Notice tone="info">已提交：{item.feedback}</Notice>
                </div>
              ) : null}
              {item.status === 'assigned' || item.status === 'acknowledged' ? (
                <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                  <label className="flex-1 text-sm font-medium">
                    <span className="sr-only">任务反馈</span>
                    <textarea
                      aria-label="任务反馈"
                      rows={3}
                      value={feedback[item.id] ?? ''}
                      onChange={(event) =>
                        setFeedback((current) => ({ ...current, [item.id]: event.target.value }))
                      }
                      placeholder="说明完成结果或当前困难"
                      className={inputClass}
                    />
                  </label>
                  <button
                    type="button"
                    className={`${primaryButton} sm:self-end`}
                    disabled={!feedback[item.id]?.trim() || submit.isPending}
                    onClick={() => submit.mutate({ id: item.id, value: feedback[item.id] })}
                  >
                    <Send size={16} />提交任务反馈
                  </button>
                </div>
              ) : null}
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title="当前没有帮扶任务" description="辅导员布置的任务会显示在这里。" />
      )}
    </Panel>
  )
}

