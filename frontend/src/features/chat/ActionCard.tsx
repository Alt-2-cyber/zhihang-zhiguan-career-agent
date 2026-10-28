import { Check, RotateCcw, X } from 'lucide-react'

import { secondaryButton } from '../../components/Ui'
import type { ActionProposalView } from './types'

export function ActionCard({
  action,
  busy,
  onConfirm,
  onReject,
  onUndo,
}: {
  action: ActionProposalView
  busy?: boolean
  onConfirm: () => void
  onReject: () => void
  onUndo: () => void
}) {
  const pending = action.status === 'pending'
  return (
    <article className={`border-l-2 px-3 py-3 ${action.risk === 'high_risk' ? 'border-red-600 bg-red-50' : 'border-amber-500 bg-amber-50'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-medium text-slate-900">{action.title}</p>
          <p className="mt-1 truncate text-xs text-slate-600">{action.tool}</p>
        </div>
        <span className="shrink-0 text-xs font-medium text-amber-800">{pending ? '等待确认' : action.status}</span>
      </div>
      {pending ? (
        <div className="mt-3 flex gap-2">
          <button type="button" className={secondaryButton} disabled={busy} onClick={onConfirm}><Check size={16} />确认</button>
          <button type="button" className={secondaryButton} disabled={busy} onClick={onReject}><X size={16} />拒绝</button>
        </div>
      ) : action.status === 'succeeded' ? (
        <button type="button" className={`${secondaryButton} mt-3`} disabled={busy} onClick={onUndo}><RotateCcw size={16} />撤销</button>
      ) : null}
    </article>
  )
}
