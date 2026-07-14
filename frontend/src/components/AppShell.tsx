import {
  BriefcaseBusiness,
  ClipboardCheck,
  FileText,
  Gauge,
  LogOut,
  Menu,
  MessageSquareText,
  SearchCheck,
  RefreshCw,
  Users,
  X,
} from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import { useSession } from '../app/session'

const studentNav = [
  { to: '/student', label: '工作台', icon: Gauge, end: true },
  { to: '/student/profile', label: '就业画像', icon: Users },
  { to: '/student/plan', label: '求职计划', icon: ClipboardCheck },
  { to: '/student/jobs', label: '岗位匹配', icon: SearchCheck },
  { to: '/student/resume', label: '简历优化', icon: FileText },
  { to: '/student/interview', label: '模拟面试', icon: MessageSquareText },
  { to: '/student/applications', label: '投递管理', icon: BriefcaseBusiness },
  { to: '/student/review', label: '每周复盘', icon: RefreshCw },
]

const counselorNav = [
  { to: '/counselor', label: '班级概览', icon: Gauge, end: true },
  { to: '/counselor/students', label: '学生进展', icon: Users },
  { to: '/counselor/interventions', label: '帮扶任务', icon: ClipboardCheck },
]

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)
  const items = user?.role === 'student' ? studentNav : counselorNav

  const navigation = (
    <>
      <div className="flex h-16 items-center gap-3 border-b border-slate-800 px-5">
        <span className="grid size-9 place-items-center rounded-md bg-teal-600 text-white">
          <BriefcaseBusiness aria-hidden="true" size={19} />
        </span>
        <div>
          <p className="text-sm font-semibold text-white">职航智管</p>
          <p className="text-[11px] text-slate-400">就业事务智能体</p>
        </div>
      </div>
      <nav className="flex-1 space-y-1 px-3 py-5" aria-label="主导航">
        {items.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            onClick={() => setMenuOpen(false)}
            className={({ isActive }) =>
              `flex h-10 items-center gap-3 rounded-md px-3 text-sm transition ${
                isActive
                  ? 'bg-teal-600 text-white'
                  : 'text-slate-300 hover:bg-slate-800 hover:text-white'
              }`
            }
          >
            <Icon aria-hidden="true" size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-slate-800 p-3">
        <div className="mb-2 px-3 py-2">
          <p className="truncate text-sm font-medium text-white">{user?.display_name}</p>
          <p className="mt-0.5 text-xs text-slate-400">{user?.role === 'student' ? '毕业生' : '就业辅导员'}</p>
        </div>
        <button
          type="button"
          onClick={logout}
          className="flex h-10 w-full items-center gap-3 rounded-md px-3 text-sm text-slate-300 hover:bg-slate-800 hover:text-white"
        >
          <LogOut aria-hidden="true" size={18} />
          退出登录
        </button>
      </div>
    </>
  )

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-60 flex-col bg-slate-950 lg:flex">{navigation}</aside>
      {menuOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button className="absolute inset-0 bg-slate-950/50" aria-label="关闭导航" onClick={() => setMenuOpen(false)} />
          <aside className="relative flex h-full w-72 flex-col bg-slate-950">
            <button className="absolute right-3 top-4 grid size-9 place-items-center text-slate-300" aria-label="关闭导航" onClick={() => setMenuOpen(false)}>
              <X size={20} />
            </button>
            {navigation}
          </aside>
        </div>
      ) : null}
      <div className="lg:pl-60">
        <header className="sticky top-0 z-20 flex h-16 items-center border-b border-slate-200 bg-white/95 px-4 backdrop-blur lg:px-8">
          <button type="button" className="grid size-10 place-items-center rounded-md text-slate-700 lg:hidden" aria-label="打开导航" onClick={() => setMenuOpen(true)}>
            <Menu size={21} />
          </button>
          <div className="ml-auto text-right">
            <p className="text-xs text-slate-500">当前身份</p>
            <p className="text-sm font-medium">{user?.role === 'student' ? '毕业生' : '就业辅导员'}</p>
          </div>
        </header>
        <main className="mx-auto max-w-[1440px] px-4 py-6 lg:px-8 lg:py-8">{children}</main>
      </div>
    </div>
  )
}
