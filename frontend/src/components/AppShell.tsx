import {
  Activity,
  BookOpenCheck,
  BriefcaseBusiness,
  Building2,
  ClipboardCheck,
  FileText,
  Gauge,
  LogOut,
  Menu,
  MessageSquareText,
  RefreshCw,
  ScrollText,
  SearchCheck,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { NavLink } from 'react-router-dom'

import { apiFetch } from '../app/api'
import { useSession } from '../app/session'
import type { AiCapabilities } from '../features/chat/types'
import { ServerDemoBanner } from './ServerDemoBanner'

type NavigationItem = {
  to: string
  label: string
  icon: typeof Gauge
  end?: boolean
}
type NavigationSection = {
  label: string
  items: NavigationItem[]
}

const studentNav: NavigationSection[] = [
  {
    label: '总览',
    items: [
      { to: '/student', label: '工作台', icon: Gauge, end: true },
      { to: '/student/assistant', label: '就业助手', icon: MessageSquareText },
    ],
  },
  {
    label: '规划与成长',
    items: [
      { to: '/student/profile', label: '就业画像', icon: Users },
      { to: '/student/plan', label: '求职计划', icon: ClipboardCheck },
      { to: '/student/learning', label: '学习成长', icon: BookOpenCheck },
      { to: '/student/training', label: '训练中心', icon: Sparkles },
    ],
  },
  {
    label: '入职后成长',
    items: [
      { to: '/student/workplace', label: '职场训练', icon: Building2 },
    ],
  },
  {
    label: '求职行动',
    items: [
      { to: '/student/jobs', label: '岗位匹配', icon: SearchCheck },
      { to: '/student/intelligence', label: '岗位情报', icon: Building2 },
      { to: '/student/resume', label: '简历优化', icon: FileText },
      { to: '/student/interview', label: '模拟面试', icon: MessageSquareText },
      { to: '/student/applications', label: '投递管理', icon: BriefcaseBusiness },
      { to: '/student/employment', label: '入职跟踪', icon: ShieldCheck },
      { to: '/student/review', label: '每周复盘', icon: RefreshCw },
    ],
  },
]

const counselorNav: NavigationSection[] = [
  {
    label: '总览',
    items: [
      { to: '/counselor', label: '班级概览', icon: Gauge, end: true },
      { to: '/counselor/assistant', label: '就业助手', icon: MessageSquareText },
    ],
  },
  {
    label: '学生服务',
    items: [
      { to: '/counselor/students', label: '学生进展', icon: Users },
      { to: '/counselor/interventions', label: '帮扶任务', icon: ClipboardCheck },
      { to: '/counselor/quality', label: '就业质量', icon: ShieldCheck },
    ],
  },
  {
    label: '系统治理',
    items: [
      { to: '/counselor/agent-usage', label: 'Agent 运行统计', icon: Activity },
      { to: '/counselor/audit', label: '审计日志', icon: ScrollText },
    ],
  },
]

function Navigation({
  sections,
  role,
  displayName,
  onNavigate,
  onLogout,
}: {
  sections: NavigationSection[]
  role: string | undefined
  displayName: string | undefined
  onNavigate: () => void
  onLogout: () => void
}) {
  let index = 0
  return (
    <>
      <div className="app-brand">
        <span className="app-brand-mark" aria-hidden="true">
          <BriefcaseBusiness size={19} strokeWidth={2.1} />
        </span>
        <div>
          <p className="app-brand-name">职航智管</p>
          <p className="app-brand-subtitle">就业事务智能工作台</p>
        </div>
      </div>

      <div className="app-nav-caption">
        <span>WORKSPACE</span>
        <span className="app-nav-caption-line" aria-hidden="true" />
      </div>
      <nav className="app-nav" aria-label="主导航">
        {sections.map((section) => (
          <div className="app-nav-section" key={section.label}>
            <p className="app-nav-section-label">{section.label}</p>
            {section.items.map(({ to, label, icon: Icon, end }) => {
              index += 1
              return (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  onClick={onNavigate}
                  className={({ isActive }) => `app-nav-link${isActive ? ' is-active' : ''}`}
                >
                  <span className="app-nav-index">{String(index).padStart(2, '0')}</span>
                  <Icon aria-hidden="true" size={17} strokeWidth={1.8} />
                  <span>{label}</span>
                </NavLink>
              )
            })}
          </div>
        ))}
      </nav>

      <div className="app-sidebar-footer">
        <div className="app-workspace-note">
          <span className="app-workspace-dot" aria-hidden="true" />
          <span>{role === 'student' ? '学生工作区' : '辅导员工作区'}</span>
        </div>
        <div className="app-user-card">
          <span className="app-user-avatar" aria-hidden="true">
            {(displayName ?? '职').slice(0, 1)}
          </span>
          <div className="app-user-copy">
            <strong>{displayName ?? '当前用户'}</strong>
            <span>{role === 'student' ? '毕业生' : '就业辅导员'}</span>
          </div>
          <button type="button" className="app-logout" onClick={onLogout} aria-label="退出登录" title="退出登录">
            <LogOut aria-hidden="true" size={16} />
          </button>
        </div>
      </div>
    </>
  )
}

export function AppShell({ children }: { children: ReactNode }) {
  const { token, user, logout } = useSession()
  const [menuOpen, setMenuOpen] = useState(false)
  const capabilitiesQuery = useQuery({
    queryKey: ['ai-capabilities'],
    queryFn: () => apiFetch<AiCapabilities>('/ai/capabilities', {}, token ?? undefined),
    enabled: Boolean(token),
    staleTime: 30_000,
  })
  const deploymentMode = capabilitiesQuery.data?.deployment_mode
  const sections = user?.role === 'student' ? studentNav : counselorNav
  const roleLabel = user?.role === 'student' ? '学生工作台' : '辅导员工作台'

  return (
    <div className="app-shell">
      <aside className={`app-sidebar${menuOpen ? ' is-open' : ''}`}>
        <Navigation
          sections={sections}
          role={user?.role}
          displayName={user?.display_name}
          onNavigate={() => setMenuOpen(false)}
          onLogout={logout}
        />
      </aside>

      {menuOpen ? (
        <button type="button" className="app-sidebar-scrim" aria-label="关闭导航" onClick={() => setMenuOpen(false)} />
      ) : null}

      <div className="app-viewport">
        <header className="app-topbar">
          <button type="button" className="app-menu-button" aria-label="打开导航" title="打开导航" onClick={() => setMenuOpen(true)}>
            <Menu aria-hidden="true" size={19} />
          </button>
          <div className="app-context">
            <span className="app-context-kicker">CAREER OS</span>
            <span className="app-context-separator" aria-hidden="true" />
            <span className="app-context-current">{roleLabel}</span>
          </div>
          <div className="app-topbar-meta">
            <span className="app-live-label"><span aria-hidden="true" />{deploymentMode === 'server-demo' ? '服务器演示版' : '本地工作区'}</span>
            <span className="app-topbar-user">{user?.display_name ?? '当前用户'}</span>
          </div>
        </header>
        <ServerDemoBanner
          deploymentMode={deploymentMode}
          limitations={capabilitiesQuery.data?.limitations}
        />
        <main className="app-content">
          <div className="app-content-noise" aria-hidden="true" />
          <div className="app-content-inner">{children}</div>
        </main>
      </div>

      {menuOpen ? (
        <button type="button" className="app-mobile-close" aria-label="关闭导航" title="关闭导航" onClick={() => setMenuOpen(false)}>
          <X aria-hidden="true" size={18} />
        </button>
      ) : null}
    </div>
  )
}
