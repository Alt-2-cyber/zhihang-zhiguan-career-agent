import { Download, RefreshCw, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { apiFetch, apiFetchBlob } from '../../app/api'
import { EmptyState, LoadingState, Notice, PageHeader, Panel, primaryButton, secondaryButton } from '../../components/Ui'

type AuditLog = {
  id: string
  user_id: string | null
  action: string
  resource_type: string | null
  resource_id: string | null
  details: Record<string, unknown> | null
  created_at: string
}

type AuditLogResponse = {
  items: AuditLog[]
  count: number
}

function buildQuery(params: Record<string, string>) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value.trim()) search.set(key, value.trim())
  })
  return search.toString()
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

function downloadBlob(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  window.URL.revokeObjectURL(url)
}

export function AuditLogsPage({ token }: { token: string }) {
  const [action, setAction] = useState('')
  const [userId, setUserId] = useState('')
  const [limit, setLimit] = useState('100')
  const [expandedId, setExpandedId] = useState<string | null>(null)
  const [exportError, setExportError] = useState<string | null>(null)
  const [exporting, setExporting] = useState(false)

  const queryString = useMemo(() => buildQuery({ action, user_id: userId, limit }), [action, limit, userId])
  const path = `/audit/logs${queryString ? `?${queryString}` : ''}`

  const query = useQuery({
    queryKey: ['audit-logs', queryString],
    queryFn: () => apiFetch<AuditLogResponse>(path, {}, token),
  })

  const exportCsv = async () => {
    setExportError(null)
    setExporting(true)
    try {
      const blob = await apiFetchBlob(`/audit/logs/export.csv${queryString ? `?${queryString}` : ''}`, token)
      downloadBlob(blob, `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`)
    } catch (error) {
      setExportError(error instanceof Error ? error.message : '审计导出失败')
    } finally {
      setExporting(false)
    }
  }

  if (query.isLoading) return <LoadingState />

  return (
    <>
      <PageHeader
        title="审计日志"
        description="查看登录、Agent 动作、工具确认、撤销和敏感查询记录。列表只展示后端已脱敏字段，导出 CSV 用于交付验收和合规留痕。"
        action={
          <button type="button" className={primaryButton} onClick={exportCsv} disabled={exporting || !query.data?.count}>
            <Download size={16} />
            导出 CSV
          </button>
        }
      />

      <Panel>
        <div className="grid gap-3 lg:grid-cols-[1.3fr_1.3fr_0.6fr_auto]">
          <label className="text-xs font-medium text-slate-600">
            动作编码
            <span className="relative mt-2 block">
              <Search className="absolute left-3 top-2.5 text-slate-400" size={16} />
              <input
                value={action}
                onChange={(event) => setAction(event.target.value)}
                placeholder="chat.action_confirmed"
                className="h-10 w-full rounded-md border border-slate-300 bg-white pl-9 pr-3 text-sm outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15"
              />
            </span>
          </label>
          <label className="text-xs font-medium text-slate-600">
            用户 ID
            <input
              value={userId}
              onChange={(event) => setUserId(event.target.value)}
              placeholder="可选"
              className="mt-2 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15"
            />
          </label>
          <label className="text-xs font-medium text-slate-600">
            条数
            <select
              value={limit}
              onChange={(event) => setLimit(event.target.value)}
              className="mt-2 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15"
            >
              <option value="50">50</option>
              <option value="100">100</option>
              <option value="300">300</option>
              <option value="1000">1000</option>
            </select>
          </label>
          <div className="flex items-end">
            <button type="button" className={secondaryButton} onClick={() => query.refetch()}>
              <RefreshCw size={16} />
              刷新
            </button>
          </div>
        </div>
      </Panel>

      {query.isError ? <Notice tone="danger">{query.error.message}</Notice> : null}
      {exportError ? <Notice tone="danger">{exportError}</Notice> : null}

      <Panel title={`审计记录 ${query.data?.count ?? 0} 条`} className="mt-5">
        {query.data?.items.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] text-left text-sm">
              <thead className="border-b border-slate-200 text-xs text-slate-500">
                <tr>
                  <th className="px-3 py-3 font-medium">时间</th>
                  <th className="px-3 py-3 font-medium">动作</th>
                  <th className="px-3 py-3 font-medium">用户</th>
                  <th className="px-3 py-3 font-medium">资源</th>
                  <th className="px-3 py-3 font-medium">详情</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {query.data.items.map((item) => {
                  const expanded = expandedId === item.id
                  return (
                    <tr key={item.id} className="align-top">
                      <td className="whitespace-nowrap px-3 py-4 text-slate-500">{formatDate(item.created_at)}</td>
                      <td className="px-3 py-4 font-medium text-slate-900">{item.action}</td>
                      <td className="px-3 py-4 text-slate-600">{item.user_id ?? '系统'}</td>
                      <td className="px-3 py-4 text-slate-600">
                        {item.resource_type ?? '-'}
                        {item.resource_id ? <span className="block max-w-[240px] truncate text-xs text-slate-400">{item.resource_id}</span> : null}
                      </td>
                      <td className="px-3 py-4">
                        <button type="button" className="text-sm font-medium text-teal-700 hover:text-teal-900" onClick={() => setExpandedId(expanded ? null : item.id)}>
                          {expanded ? '收起' : '展开脱敏详情'}
                        </button>
                        {expanded ? (
                          <pre className="mt-3 max-h-72 overflow-auto rounded-md bg-slate-950 p-3 text-xs leading-5 text-slate-100">
                            {JSON.stringify(item.details ?? {}, null, 2)}
                          </pre>
                        ) : null}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="暂无审计记录" description="调整筛选条件，或先执行一次登录、Agent 动作确认、撤销等操作。" />
        )}
      </Panel>
    </>
  )
}
