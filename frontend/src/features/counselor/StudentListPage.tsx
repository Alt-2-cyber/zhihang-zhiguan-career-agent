import { useQuery } from '@tanstack/react-query'
import { Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { apiFetch } from '../../app/api'
import { EmptyState, PageHeader, Panel } from '../../components/Ui'
import { AskAgentButton } from '../chat/AskAgentButton'
import type { CounselorData } from './CounselorDashboard'

export function StudentListPage({ token }: { token: string }) {
  const [search, setSearch] = useState('')
  const query = useQuery({ queryKey: ['counselor-dashboard'], queryFn: () => apiFetch<CounselorData>('/dashboard/counselor', {}, token) })
  const students = useMemo(() => query.data?.students.filter((item) => `${item.display_name}${item.username}`.toLowerCase().includes(search.toLowerCase())) ?? [], [query.data, search])
  return <><PageHeader title="学生就业进展" description="按姓名或账号检索班级学生，并优先处理存在明确风险事实的学生。" action={<label className="relative"><Search className="absolute left-3 top-3 text-slate-400" size={16} /><span className="sr-only">搜索学生</span><input aria-label="搜索学生" value={search} onChange={(e) => setSearch(e.target.value)} className="h-10 rounded-md border border-slate-300 bg-white pl-9 pr-3 text-sm" placeholder="搜索学生" /></label>} /><Panel>{students.length ? <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead className="border-b border-slate-200 text-xs text-slate-500"><tr><th className="px-3 py-3 font-medium">学生</th><th className="px-3 py-3 font-medium">账号</th><th className="px-3 py-3 font-medium">风险数量</th><th className="px-3 py-3 font-medium">当前状态</th><th className="px-3 py-3 font-medium">操作</th></tr></thead><tbody className="divide-y divide-slate-100">{students.map((student) => <tr key={student.id}><td className="px-3 py-4 font-medium">{student.display_name}</td><td className="px-3 py-4 text-slate-500">{student.username}</td><td className="px-3 py-4">{student.risk_count}</td><td className={`px-3 py-4 ${student.risk_count ? 'text-amber-700' : 'text-emerald-700'}`}>{student.risk_count ? '需要关注' : '正常跟进'}</td><td className="px-3 py-4"><AskAgentButton role="counselor" context={{ type: 'student', id: student.id }} className="h-8 px-2 text-xs" /></td></tr>)}</tbody></table></div> : <EmptyState title="没有匹配的学生" description="调整搜索词后重试。" />}</Panel></>
}

