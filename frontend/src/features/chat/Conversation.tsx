import { Bot, Send, UserRound } from 'lucide-react'
import { useEffect, useRef, type FormEvent } from 'react'

import { AttachmentComposer } from './AttachmentComposer'
import { MessageAudioButton } from './MessageAudioButton'
import type { AgentRunView, AiCapabilities, ChatMessage } from './types'
import { VoiceComposer } from './VoiceComposer'

const answerSectionHeadings = new Set(['综合建议', '参考资源', '下一步行动'])

function AnswerContent({ content }: { content: string }) {
  return (
    <div className="space-y-2 break-words">
      {content.split(/\r?\n/).map((rawLine, index) => {
        const line = rawLine.trim()
        if (!line) return null
        if (answerSectionHeadings.has(line)) {
          return <h3 key={`${line}-${index}`} className="pt-1 text-sm font-extrabold text-[#102015]">{line}</h3>
        }
        const numbered = line.match(/^(\d{1,2})\.\s+(.+)$/)
        if (numbered) {
          return <div key={`${line}-${index}`} className="flex items-start gap-2"><span className="shrink-0 font-extrabold text-[#b24531]">{numbered[1]}.</span><p className="min-w-0">{numbered[2]}</p></div>
        }
        return <p key={`${line}-${index}`}>{line}</p>
      })}
    </div>
  )
}

export function Conversation({
  messages,
  run,
  draft,
  disabled,
  disabledReason,
  sendError,
  sessionId,
  token,
  onDraftChange,
  onAttachmentsChange,
  onAttachmentBusyChange,
  onSubmit,
  capabilities,
}: {
  messages: ChatMessage[]
  run: AgentRunView
  draft: string
  disabled: boolean
  disabledReason?: string | null
  sendError?: string | null
  sessionId: string
  token: string
  onDraftChange: (value: string) => void
  onAttachmentsChange: (ids: string[]) => void
  onAttachmentBusyChange: (busy: boolean) => void
  onSubmit: () => void
  capabilities?: AiCapabilities
}) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const submitTitle = disabled
    ? disabledReason ?? '当前暂时不能发送'
    : '发送消息'
  const showRunAnswer = Boolean(run.answer) && !messages.some((message) =>
    message.sender === 'assistant'
    && (message.id === run.answerMessageId || message.content.trim() === run.answer.trim()),
  )
  const onlyUserMessages = messages.length > 0 && messages.every((message) => message.sender === 'user')
  const attachmentServicesReady = capabilities
    ? capabilities.services.ocr.ready && capabilities.services.embedding.ready
    : true
  const speechReady = capabilities ? capabilities.services.speech.ready : true
  const attachmentDisabledReason = attachmentServicesReady ? undefined : 'OCR 或 BGE-M3 未就绪，暂不能上传简历/附件'
  const speechDisabledReason = speechReady ? undefined : '语音识别 / TTS 服务未就绪'
  useEffect(() => {
    const target = bottomRef.current
    if (target && typeof target.scrollIntoView === 'function') {
      target.scrollIntoView({ block: 'nearest' })
    }
  }, [messages.length, run.answer])
  const submit = (event: FormEvent) => { event.preventDefault(); onSubmit() }

  return (
    <section className="flex min-h-0 min-w-0 flex-col bg-[#edf2e9]" aria-label="就业助手对话">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 sm:px-7">
        {!messages.length && !run.answer ? (
          <div className="mx-auto mt-16 max-w-md border border-dashed border-[#102015]/25 bg-white/70 px-6 py-10 text-center shadow-[5px_5px_0_rgba(16,32,21,0.11)]">
            <span className="mx-auto grid size-11 place-items-center rounded-md bg-[#102015] text-[#c7ff4c]"><Bot size={22} /></span>
            <h2 className="mt-4 text-lg font-extrabold text-[#102015]">从当前求职问题开始</h2>
            <p className="mt-2 text-sm leading-6 text-[#526051]">可以分析岗位、优化简历、制定计划或梳理投递进展。</p>
          </div>
        ) : null}
        {onlyUserMessages && !showRunAnswer && run.status === 'idle' ? (
          <div className="mx-auto mb-5 max-w-[780px] border border-dashed border-[#102015]/25 bg-white/75 px-4 py-3 text-sm text-[#526051]">
            这条历史消息尚未生成回复。可以继续补充问题，或新建对话重新开始。
          </div>
        ) : null}
        <div className="mx-auto max-w-[780px] space-y-5">
          {messages.map((message) => (
            <article key={message.id} className={`flex gap-3 ${message.sender === 'user' ? 'flex-row-reverse' : ''}`}>
              <span className={`grid size-8 shrink-0 place-items-center rounded-md ${message.sender === 'user' ? 'bg-[#102015] text-[#c7ff4c]' : 'bg-[#c7ff4c] text-[#102015] shadow-[2px_2px_0_#102015]'}`}>
                {message.sender === 'user' ? <UserRound size={16} /> : <Bot size={16} />}
              </span>
              <div className={`max-w-[85%] rounded-md px-4 py-3 text-sm leading-6 ${message.sender === 'user' ? 'bg-[#102015] text-white shadow-[4px_4px_0_rgba(16,32,21,0.2)]' : 'border border-[#102015]/18 bg-[#fbfdf8] text-[#102015] shadow-[4px_4px_0_rgba(16,32,21,0.1)]'}`}>
                <AnswerContent content={message.content} />
                {message.provider ? <p className="mt-2 text-[11px] opacity-60">{message.provider}</p> : null}
                {message.citations.length ? (
                  <div className="mt-3 border-t border-[#102015]/15 pt-2 text-xs text-[#647460]">
                    <span>来源：</span>
                    <ul className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
                      {message.citations.filter((citation, index, items) => {
                        const label = citation.label ?? citation.title ?? citation.source ?? '业务数据'
                        return items.findIndex((item) =>
                          (item.label ?? item.title ?? item.source ?? '业务数据') === label && item.url === citation.url,
                        ) === index
                      }).map((citation, index) => {
                        const label = citation.label ?? citation.title ?? citation.source ?? '业务数据'
                        return (
                          <li key={`${citation.url ?? label}-${index}`} className="break-words">
                            {citation.url ? <a className="text-[#38642f] underline underline-offset-2 hover:text-[#102015]" href={citation.url} target="_blank" rel="noreferrer">{label}</a> : <span>{label}</span>}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                ) : null}
                {message.sender === 'assistant' && !message.optimistic ? <MessageAudioButton messageId={message.id} token={token} disabled={!speechReady} disabledReason={speechDisabledReason} /> : null}
              </div>
            </article>
          ))}
          {showRunAnswer ? (
            <article className="flex gap-3">
              <span className="grid size-8 shrink-0 place-items-center rounded-md bg-[#c7ff4c] text-[#102015] shadow-[2px_2px_0_#102015]"><Bot size={16} /></span>
              <div className="max-w-[85%] rounded-md border border-[#102015]/18 bg-[#fbfdf8] px-4 py-3 text-sm leading-6 text-[#102015] shadow-[4px_4px_0_rgba(16,32,21,0.1)]">
                <div aria-live="polite"><AnswerContent content={run.answer} /></div>
                {run.status === 'queued' || run.status === 'running' ? <span className="mt-2 inline-block h-4 w-1 animate-pulse bg-[#c7ff4c]" aria-label="正在流式生成回答" /> : null}
                {run.provider ? <p className="mt-2 text-[11px] text-slate-400">{run.provider}</p> : null}
              </div>
            </article>
          ) : null}
          {run.status === 'queued' || run.status === 'running' ? <p className="ml-11 inline-flex border border-[#102015]/18 bg-[#c7ff4c] px-3 py-2 text-xs font-bold text-[#102015]">{run.answer ? '正在流式生成回答...' : 'Agent 正在协同处理...'}</p> : null}
          {run.status === 'failed' ? (
            <div className="ml-11 border border-[#ff7358]/45 bg-[#fff0eb] px-3 py-2 text-xs leading-5 text-[#8c2f1f]">
              <p className="font-medium">Agent 执行失败：{run.errorCode ?? 'agent_run_failed'}</p>
              {run.errorMessage ? <p className="mt-1">{run.errorMessage}</p> : null}
            </div>
          ) : null}
          <div ref={bottomRef} />
        </div>
      </div>
      <form className="border-t border-[#102015]/15 bg-[#e9eee5] p-3 sm:p-4" onSubmit={submit}>
        {sendError ? (
          <div className="mx-auto mb-2 max-w-3xl rounded-lg border border-[#ff7358]/45 bg-[#fff0eb] px-3 py-2 text-xs leading-5 text-[#8c2f1f]">
            {sendError}
          </div>
        ) : disabledReason ? (
          <div className="mx-auto mb-2 max-w-3xl rounded-lg border border-[#ff7358]/45 bg-[#fff0eb] px-3 py-2 text-xs leading-5 text-[#8c2f1f]">
            {disabledReason}
          </div>
        ) : null}
        <div className="relative mx-auto flex max-w-[820px] items-end gap-2 rounded-xl border border-[#102015]/20 bg-white p-2 shadow-[0_8px_24px_rgba(16,32,21,0.10)] transition focus-within:border-[#6e9b2b] focus-within:shadow-[0_0_0_3px_rgba(110,155,43,0.16),0_8px_24px_rgba(16,32,21,0.10)]">
          <AttachmentComposer sessionId={sessionId} token={token} disabled={disabled || !attachmentServicesReady} disabledReason={attachmentDisabledReason ?? disabledReason ?? undefined} onReadyChange={onAttachmentsChange} onBusyChange={onAttachmentBusyChange} />
          <VoiceComposer sessionId={sessionId} token={token} disabled={disabled || !speechReady} disabledReason={speechDisabledReason} onTranscript={onDraftChange} />
          <label className="min-w-0 flex-1">
            <span className="sr-only">发送给就业助手</span>
            <textarea aria-label="发送给就业助手" value={draft} onChange={(event) => onDraftChange(event.target.value)} rows={2} maxLength={12000} placeholder="输入你的求职问题" className="block min-h-16 max-h-36 w-full resize-y rounded-lg border-0 bg-transparent px-3 py-2 text-[15px] leading-6 text-[#102015] outline-none placeholder:text-[#7b8a80] focus:ring-0" />
          </label>
          <button type="submit" className="grid size-11 shrink-0 place-items-center rounded-lg border border-[#102015] bg-[#102015] text-[#c7ff4c] shadow-[3px_3px_0_rgba(16,32,21,0.18)] transition hover:-translate-y-0.5 hover:bg-[#c7ff4c] hover:text-[#102015] disabled:cursor-wait disabled:opacity-35 disabled:hover:translate-y-0" disabled={disabled || !draft.trim()} aria-label="发送消息" title={submitTitle}><Send size={18} /></button>
        </div>
      </form>
    </section>
  )
}
