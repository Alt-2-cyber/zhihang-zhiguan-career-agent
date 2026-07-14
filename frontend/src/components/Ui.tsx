import { AlertCircle, CheckCircle2, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'

export function PageHeader({ title, description, action }: { title: string; description: string; action?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-col gap-4 border-b border-slate-200 pb-6 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <h1 className="text-2xl font-semibold text-slate-950">{title}</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{description}</p>
      </div>
      {action}
    </header>
  )
}

export function Panel({ title, children, className = '' }: { title?: string; children: ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 overflow-hidden rounded-md border border-slate-200 bg-white ${className}`}>
      {title ? <h2 className="border-b border-slate-200 px-5 py-4 text-sm font-semibold text-slate-900">{title}</h2> : null}
      <div className="p-5">{children}</div>
    </section>
  )
}

export function LoadingState() {
  return <div className="flex min-h-40 items-center justify-center gap-2 text-sm text-slate-500"><LoaderCircle className="animate-spin" size={18} />正在加载</div>
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="border border-dashed border-slate-300 bg-slate-50 px-5 py-10 text-center">
      <p className="text-sm font-medium text-slate-800">{title}</p>
      <p className="mx-auto mt-2 max-w-md text-xs leading-5 text-slate-500">{description}</p>
    </div>
  )
}

export function Notice({ children, tone = 'info' }: { children: ReactNode; tone?: 'info' | 'success' | 'warning' | 'danger' }) {
  const styles = {
    info: 'border-teal-600 bg-teal-50 text-teal-900',
    success: 'border-emerald-600 bg-emerald-50 text-emerald-900',
    warning: 'border-amber-500 bg-amber-50 text-amber-950',
    danger: 'border-red-600 bg-red-50 text-red-900',
  }
  const Icon = tone === 'success' ? CheckCircle2 : AlertCircle
  return <div className={`flex items-start gap-2 border-l-2 px-3 py-2 text-sm ${styles[tone]}`}><Icon className="mt-0.5 shrink-0" size={16} />{children}</div>
}

export const primaryButton = 'inline-flex h-10 items-center justify-center gap-2 rounded-md bg-teal-700 px-4 text-sm font-semibold text-white transition hover:bg-teal-800 focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2 disabled:cursor-wait disabled:opacity-60'
export const secondaryButton = 'inline-flex h-10 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-4 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-teal-700 focus:ring-offset-2 disabled:opacity-60'
export const inputClass = 'mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2.5 text-sm outline-none transition focus:border-teal-700 focus:ring-2 focus:ring-teal-700/15'
