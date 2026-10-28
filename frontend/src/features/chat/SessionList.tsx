import { Archive, MessageSquarePlus, Search } from 'lucide-react'

import type { ChatSession } from './types'

function displayTitle(title: string) {
  const normalized = title.trim()
  return normalized && !/^\?+$/.test(normalized) ? normalized : '未命名历史会话'
}

export function SessionList({
  sessions,
  selectedId,
  search,
  busy,
  onSearch,
  onSelect,
  onCreate,
  onArchive,
}: {
  sessions: ChatSession[]
  selectedId: string | null
  search: string
  busy: boolean
  onSearch: (value: string) => void
  onSelect: (id: string) => void
  onCreate: () => void
  onArchive: (id: string) => void
}) {
  return (
    <aside className="flex h-full min-h-0 flex-col overflow-hidden bg-[#112219] text-white" aria-label="对话历史">
      <div className="border-b border-white/10 p-3">
        <button type="button" className="action-button-primary flex h-10 w-full items-center justify-center gap-2 rounded-md px-3 text-sm font-bold disabled:opacity-60" disabled={busy} onClick={onCreate}>
          <MessageSquarePlus size={17} />新建对话
        </button>
        <label className="relative mt-3 block">
          <span className="sr-only">搜索对话</span>
          <Search className="absolute left-3 top-2.5 text-[#9eae9c]" size={16} />
          <input value={search} onChange={(event) => onSearch(event.target.value)} placeholder="搜索对话" className="h-10 w-full rounded-md border border-white/15 bg-white/[0.06] pl-9 pr-3 text-sm text-white outline-none placeholder:text-[#9eae9c] hover:border-white/30 focus:border-[#c7ff4c]" />
        </label>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2.5">
        {sessions.length ? sessions.map((session) => {
          const active = selectedId === session.id
          return (
            <div key={session.id} className={`group mb-1 flex border ${active ? 'border-[#c7ff4c] bg-[#c7ff4c] text-[#102015] shadow-[3px_3px_0_rgba(255,255,255,0.21)]' : 'border-transparent text-[#cfdbc9] hover:border-white/10 hover:bg-white/[0.07]'}`}>
              <button type="button" className="min-w-0 flex-1 px-3 py-3 text-left" onClick={() => onSelect(session.id)}>
                <p className="truncate text-sm font-bold">{displayTitle(session.title)}</p>
                <p className={`mt-1 text-[11px] ${active ? 'text-[#476142]' : 'text-[#9eae9c]'}`}>{new Date(session.updated_at).toLocaleDateString('zh-CN')}</p>
              </button>
              {session.status === 'active' ? <button type="button" className={`grid w-9 place-items-center opacity-0 transition focus:opacity-100 group-hover:opacity-100 ${active ? 'hover:text-[#102015]' : 'hover:text-white'}`} aria-label={`归档${displayTitle(session.title)}`} title="归档" onClick={() => onArchive(session.id)}><Archive size={15} /></button> : null}
            </div>
          )
        }) : <p className="px-3 py-8 text-center text-sm text-[#9eae9c]">没有匹配的对话</p>}
      </div>
    </aside>
  )
}
