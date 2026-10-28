import { Activity, RefreshCw } from 'lucide-react'
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { apiFetch } from '../../app/api'
import { EmptyState, LoadingState, Notice, PageHeader, Panel, secondaryButton } from '../../components/Ui'

type MetricBucket = {
  name: string
  calls: number
  successes: number
  failures: number
  failure_rate: number
  avg_latency_ms: number | null
  p95_latency_ms: number | null
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  cost_micros: number | null
}

type UsageResponse = {
  window: { days: number; since: string; until: string; truncated: boolean }
  totals: MetricBucket
  providers: MetricBucket[]
  operations: MetricBucket[]
  daily: Array<MetricBucket & { date: string }>
}

function cost(value: number | null) {
  return value === null ? '-' : `$${(value / 1_000_000).toFixed(4)}`
}

function percent(value: number) {
  return `${(value * 100).toFixed(1)}%`
}

function latency(value: number | null) {
  return value === null ? '-' : `${value} ms`
}

function tokenCount(value: number | null) {
  return value === null ? '-' : value.toLocaleString()
}

function MetricTable({ rows, label }: { rows: MetricBucket[]; label: string }) {
  if (!rows.length) {
    return <EmptyState title={`暂无${label}`} description="完成一次 Agent 调用后，这里会显示真实聚合数据。" />
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[760px] text-left text-sm">
        <thead className="border-b border-slate-200 text-xs text-slate-500">
          <tr>
            <th className="px-3 py-3 font-medium">维度</th>
            <th className="px-3 py-3 font-medium">调用</th>
            <th className="px-3 py-3 font-medium">失败率</th>
            <th className="px-3 py-3 font-medium">平均 / P95 延迟</th>
            <th className="px-3 py-3 font-medium">Token</th>
            <th className="px-3 py-3 font-medium">费用</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => (
            <tr key={row.name}>
              <td className="px-3 py-3 font-medium text-slate-900">{row.name}</td>
              <td className="px-3 py-3 text-slate-600">{row.calls}</td>
              <td className={`px-3 py-3 ${row.failure_rate ? 'text-rose-700' : 'text-emerald-700'}`}>
                {percent(row.failure_rate)}
              </td>
              <td className="px-3 py-3 text-slate-600">
                {latency(row.avg_latency_ms)} / {latency(row.p95_latency_ms)}
              </td>
              <td className="px-3 py-3 text-slate-600">{tokenCount(row.total_tokens)}</td>
              <td className="px-3 py-3 text-slate-600">{cost(row.cost_micros)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function AgentUsagePage({ token }: { token: string }) {
  const [days, setDays] = useState('7')
  const query = useQuery({
    queryKey: ['agent-usage', days],
    queryFn: () => apiFetch<UsageResponse>(`/agents/usage?days=${days}`, {}, token),
  })

  if (query.isLoading) return <LoadingState />

  return (
    <>
      <PageHeader
        title="Agent 运行统计"
        description="查看 Agent 模型调用量、失败率、延迟、Token 和费用，帮助定位 Provider 故障与成本异常。"
        action={
          <div className="flex items-center gap-2">
            <label className="sr-only" htmlFor="usage-days">统计周期</label>
            <select id="usage-days" value={days} onChange={(event) => setDays(event.target.value)} className="ui-input usage-period-select">
              <option value="1">最近 24 小时</option>
              <option value="7">最近 7 天</option>
              <option value="30">最近 30 天</option>
            </select>
            <button type="button" className={secondaryButton} onClick={() => query.refetch()} disabled={query.isFetching}>
              <RefreshCw size={16} className={query.isFetching ? 'animate-spin' : ''} />
              刷新
            </button>
          </div>
        }
      />

      {query.isError ? <Notice tone="danger">统计接口读取失败：{query.error.message}</Notice> : null}
      {query.data ? (
        <>
          {query.data.window.truncated ? (
            <div className="mb-5"><Notice tone="warning">数据量超过统计上限，当前结果已截取最新窗口内的前 50,000 条调用。</Notice></div>
          ) : null}

          <section className="usage-stat-grid">
            {[
              ['调用次数', query.data.totals.calls.toLocaleString()],
              ['失败率', percent(query.data.totals.failure_rate)],
              ['P95 延迟', latency(query.data.totals.p95_latency_ms)],
              ['费用', cost(query.data.totals.cost_micros)],
            ].map(([label, value]) => (
              <div key={label} className="usage-stat-card">
                <div className="usage-stat-label"><Activity size={15} />{label}</div>
                <p className="usage-stat-value">{value}</p>
              </div>
            ))}
          </section>

          <div className="mt-5 grid gap-5 xl:grid-cols-2">
            <Panel title="按 Provider"><MetricTable rows={query.data.providers} label="Provider 调用" /></Panel>
            <Panel title="按操作"><MetricTable rows={query.data.operations} label="操作调用" /></Panel>
          </div>

          <Panel title="按日期" className="mt-5">
            {query.data.daily.length ? (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[680px] text-left text-sm">
                  <thead className="border-b border-slate-200 text-xs text-slate-500">
                    <tr><th className="px-3 py-3 font-medium">日期</th><th className="px-3 py-3 font-medium">调用</th><th className="px-3 py-3 font-medium">失败</th><th className="px-3 py-3 font-medium">Token</th><th className="px-3 py-3 font-medium">费用</th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {query.data.daily.map((row) => (
                      <tr key={row.date}>
                        <td className="px-3 py-3 font-medium">{row.date}</td>
                        <td className="px-3 py-3">{row.calls}</td>
                        <td className="px-3 py-3 text-rose-700">{row.failures}</td>
                        <td className="px-3 py-3">{tokenCount(row.total_tokens)}</td>
                        <td className="px-3 py-3">{cost(row.cost_micros)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <EmptyState title="暂无调用数据" description="当前统计窗口内没有完成的模型调用。" />}
          </Panel>
        </>
      ) : (
        <EmptyState title="统计数据暂不可用" description="请检查 Agent 统计服务是否完成迁移，或稍后刷新重试。" />
      )}
    </>
  )
}
