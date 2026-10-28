import { MessageSquareText } from 'lucide-react'
import { useInRouterContext, useNavigate } from 'react-router-dom'

import { secondaryButton } from '../../components/Ui'
import type { ChatContextRef, ChatRole } from './types'

export function AskAgentButton({ role, context, className = '' }: { role: ChatRole; context: ChatContextRef; className?: string }) {
  const inRouter = useInRouterContext()
  if (!inRouter) return <button type="button" className={`${secondaryButton} ${className}`} disabled><MessageSquareText size={17} />询问 Agent</button>
  return <RoutedAskAgentButton role={role} context={context} className={className} />
}

function RoutedAskAgentButton({ role, context, className }: { role: ChatRole; context: ChatContextRef; className: string }) {
  const navigate = useNavigate()
  return <button type="button" className={`${secondaryButton} ${className}`} onClick={() => navigate(role === 'student' ? '/student/assistant' : '/counselor/assistant', { state: { context } })}><MessageSquareText size={17} />询问 Agent</button>
}
