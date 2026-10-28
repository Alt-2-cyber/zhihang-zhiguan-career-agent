import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Building2, Clock3, Globe2, Link2, LoaderCircle, MapPin, Radar, RefreshCw, TrendingUp } from 'lucide-react'

import { apiFetch } from '../../app/api'
import { EmptyState, LoadingState, Notice, PageHeader, Panel, primaryButton } from '../../components/Ui'
import { AskAgentButton } from '../chat/AskAgentButton'

type CountRow = { name: string; count: number }
type Source = {
  id: string
  name: string
  base_url: string
  source_type: string
  adapter_key: string
  adapter_name: string
  access_policy: string
  terms_url: string | null
  status: string
  refresh_interval_hours: number
  last_success_at: string | null
  last_checked_at: string | null
  freshness: { status: 'fresh' | 'stale' | 'error' | 'never_checked'; age_hours: number | null; message: string }
}
type Crawl = {
  id: string
  source_name: string
  status: string
  items_seen: number
  items_imported: number
  error_code: string | null
  started_at: string | null
  completed_at: string | null
}
type Intelligence = {
  metrics: { active_jobs: number; public_jobs: number; stale_jobs: number; active_sources: number }
  locations: CountRow[]
  roles: CountRow[]
  companies: CountRow[]
  sources: Source[]
  recent_crawls: Crawl[]
  freshness_alerts: Array<{ source_id: string; source_name: string; status: string; message: string }>
  generated_at: string
}
type RefreshSummary = {
  checked: number
  succeeded: number
  failed: number
  items_imported: number
}

function Ranking({ title, rows, icon: Icon }: { title: string; rows: CountRow[]; icon: typeof TrendingUp }) {
  const max = Math.max(1, ...rows.map((item) => item.count))
  return (
    <Panel title={title}>
      {rows.length ? <div className="space-y-3">{rows.map((row) => <div key={row.name}><div className="flex items-center justify-between gap-3 text-sm"><span className="flex min-w-0 items-center gap-2 truncate"><Icon className="shrink-0 text-teal-700" size={16} />{row.name}</span><span className="font-semibold">{row.count}</span></div><div className="mt-1.5 h-2 bg-slate-100"><div className="h-full bg-teal-700" style={{ width: `${Math.round(row.count * 100 / max)}%` }} /></div></div>)}</div> : <EmptyState title="暂无趋势数据" description="岗位库导入后自动生成分布统计。" />}
    </Panel>
  )
}

export function JobIntelligencePage({ token }: { token: string }) {
  const queryClient = useQueryClient()
  const query = useQuery({ queryKey: ['job-intelligence'], queryFn: () => apiFetch<Intelligence>('/intelligence/overview', {}, token) })
  const refresh = useMutation({
    mutationFn: () => apiFetch<RefreshSummary>('/intelligence/sources/refresh?force=true', { method: 'POST' }, token, 120_000),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['job-intelligence'] }),
        queryClient.invalidateQueries({ queryKey: ['jobs'] }),
      ])
    },
  })
  if (query.isLoading) return <LoadingState />
  if (!query.data) return <EmptyState title="岗位情报暂不可用" description="请刷新页面或检查后端服务。" />
  const data = query.data
  return (
    <>
      <PageHeader
        title="岗位情报"
        description="聚合公开招聘来源、岗位时效、区域分布和企业需求，帮助学生选岗，也帮助学校观察市场变化。"
        action={
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              className={primaryButton}
              onClick={() => refresh.mutate()}
              disabled={refresh.isPending}
              aria-label="同步公开岗位"
            >
              {refresh.isPending ? <LoaderCircle className="animate-spin" size={17} /> : <RefreshCw size={17} />}
              {refresh.isPending ? '正在抓取' : '同步公开岗位'}
            </button>
            <AskAgentButton role="student" context={{ type: 'job_intelligence', id: 'overview' }} />
          </div>
        }
      />
      {refresh.isError ? <div className="mb-5"><Notice tone="danger">岗位同步失败：{refresh.error.message}</Notice></div> : null}
      {refresh.data ? (
        <div className="mb-5">
          <Notice tone={refresh.data.failed ? 'warning' : 'success'}>
            本次已检查 {refresh.data.checked} 个来源，成功 {refresh.data.succeeded} 个，导入 {refresh.data.items_imported} 条岗位。
            {refresh.data.failed ? ` ${refresh.data.failed} 个来源失败，请查看下方采集记录。` : ''}
          </Notice>
        </div>
      ) : null}
      <div className="mb-6"><Notice>当前为真实公开来源入口数据：系统只记录合规入口、岗位来源和人工核验状态，不绕过登录、验证码或站点访问限制，也不会自动投递。</Notice></div>
      {data.freshness_alerts.length ? <div className="mb-6"><Notice tone="warning"><span className="flex items-start gap-2"><AlertTriangle size={16} className="mt-0.5 shrink-0" />{data.freshness_alerts.length} 个岗位来源需要刷新或人工核验。</span></Notice></div> : null}
      <section className="grid border border-slate-200 bg-white sm:grid-cols-4">
        {[
          { label: '有效岗位', value: data.metrics.active_jobs, icon: Radar },
          { label: '公开来源岗位', value: data.metrics.public_jobs, icon: Globe2 },
          { label: '活跃来源', value: data.metrics.active_sources, icon: Link2 },
          { label: '超过 30 天', value: data.metrics.stale_jobs, icon: Clock3 },
        ].map((item, index) => <div key={item.label} className={`p-5 ${index ? 'border-t border-slate-200 sm:border-l sm:border-t-0' : ''}`}><div className="flex items-center justify-between"><p className="text-xs text-slate-500">{item.label}</p><item.icon className="text-teal-700" size={18} /></div><p className="mt-3 text-3xl font-semibold">{item.value}</p></div>)}
      </section>
      <div className="mt-6 grid gap-6 xl:grid-cols-3">
        <Ranking title="热门岗位" rows={data.roles} icon={TrendingUp} />
        <Ranking title="热门城市" rows={data.locations} icon={MapPin} />
        <Ranking title="活跃企业" rows={data.companies} icon={Building2} />
      </div>
      <div className="mt-6 grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
        <Panel title="合规信息来源">
          {data.sources.length ? <div className="divide-y divide-slate-200">{data.sources.map((source) => <article key={source.id} className="py-4 first:pt-0 last:pb-0"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-medium">{source.name}</p><span className={`rounded px-2 py-1 text-xs ${source.freshness.status === 'fresh' ? 'bg-emerald-50 text-emerald-700' : 'bg-amber-50 text-amber-700'}`}>{source.freshness.status === 'fresh' ? '新鲜' : '需核验'}</span></div><p className="mt-2 break-all text-xs text-slate-500">{source.base_url}</p><p className="mt-2 text-xs text-slate-500">适配器：{source.adapter_name} · 类型：{source.source_type} · 状态：{source.status}</p><p className="mt-1 text-xs text-slate-500">刷新周期：{source.refresh_interval_hours} 小时 · 最近成功：{source.last_success_at ? new Date(source.last_success_at).toLocaleString() : '暂无'} · {source.freshness.message}</p></article>)}</div> : <EmptyState title="暂无来源" description="可配置学校就业网、人社局、招聘会或企业官网公开来源。" />}
        </Panel>
        <Panel title="最近采集记录">
          {data.recent_crawls.length ? <div className="space-y-3">{data.recent_crawls.map((crawl) => <div key={crawl.id} className="rounded-md border border-slate-200 p-3"><div className="flex items-center justify-between gap-3"><p className="text-sm font-medium">{crawl.source_name}</p><span className={crawl.status === 'succeeded' ? 'text-xs font-medium text-emerald-700' : 'text-xs font-medium text-amber-700'}>{crawl.status}</span></div><p className="mt-2 text-xs text-slate-500">看到 {crawl.items_seen} 条，入库 {crawl.items_imported} 条</p>{crawl.error_code ? <p className="mt-1 text-xs text-red-700">错误：{crawl.error_code}</p> : null}</div>)}</div> : <EmptyState title="暂无采集记录" description="信息源任务运行后会显示状态、数量和错误码。" />}
        </Panel>
      </div>
    </>
  )
}
