import { AlertCircle, CheckCircle2, LoaderCircle } from 'lucide-react'
import type { ReactNode } from 'react'

export function PageHeader({
  title,
  description,
  action,
}: {
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <header className="page-header">
      <div className="page-header-copy">
        <span className="page-kicker">CAREER OS / WORKSPACE</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action ? <div className="page-header-action">{action}</div> : null}
    </header>
  )
}

export function Panel({
  title,
  children,
  className = '',
}: {
  title?: string
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`ui-panel ${className}`}>
      {title ? (
        <header className="ui-panel-header">
          <h2>{title}</h2>
          <span className="ui-panel-marker" aria-hidden="true" />
        </header>
      ) : null}
      <div className="ui-panel-body">{children}</div>
    </section>
  )
}

export function LoadingState() {
  return (
    <div className="ui-loading" role="status" aria-live="polite">
      <span className="ui-loading-ring" aria-hidden="true"><LoaderCircle className="animate-spin" size={18} /></span>
      <span>正在加载工作区</span>
    </div>
  )
}

export function EmptyState({ title, description }: { title: string; description: string }) {
  return (
    <div className="ui-empty-state">
      <span className="ui-empty-mark" aria-hidden="true" />
      <p className="ui-empty-title">{title}</p>
      <p className="ui-empty-description">{description}</p>
    </div>
  )
}

export function Notice({
  children,
  tone = 'info',
}: {
  children: ReactNode
  tone?: 'info' | 'success' | 'warning' | 'danger'
}) {
  const styles = {
    info: 'ui-notice-info',
    success: 'ui-notice-success',
    warning: 'ui-notice-warning',
    danger: 'ui-notice-danger',
  }
  const Icon = tone === 'success' ? CheckCircle2 : AlertCircle
  return (
    <div className={`ui-notice ${styles[tone]}`} role={tone === 'danger' ? 'alert' : undefined}>
      <Icon className="ui-notice-icon" aria-hidden="true" size={16} />
      <span>{children}</span>
    </div>
  )
}

export const primaryButton = 'ui-button ui-button-primary'
export const secondaryButton = 'ui-button ui-button-secondary'
export const inputClass = 'ui-input'
