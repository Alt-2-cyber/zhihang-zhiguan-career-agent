import { createContext, useContext, useMemo, useState, type ReactNode } from 'react'

import { apiFetch } from './api'

export type UserRole = 'student' | 'counselor' | 'admin'

export type SessionUser = {
  id: string
  username: string
  display_name: string
  role: UserRole
  class_id: string | null
}

type StoredSession = {
  version: 1
  token: string
  user: SessionUser
}

type SessionContextValue = {
  token: string | null
  user: SessionUser | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const STORAGE_KEY = 'career-agent.session.v1'
const SessionContext = createContext<SessionContextValue | null>(null)

function readStoredSession(): StoredSession | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as StoredSession
    return parsed.version === 1 && parsed.token && parsed.user ? parsed : null
  } catch {
    window.localStorage.removeItem(STORAGE_KEY)
    return null
  }
}

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<StoredSession | null>(readStoredSession)

  const value = useMemo<SessionContextValue>(
    () => ({
      token: session?.token ?? null,
      user: session?.user ?? null,
      login: async (username, password) => {
        const tokenResponse = await apiFetch<{ access_token: string }>('/auth/login', {
          method: 'POST',
          body: JSON.stringify({ username, password }),
        })
        const user = await apiFetch<SessionUser>(
          '/auth/me',
          { method: 'GET' },
          tokenResponse.access_token,
        )
        const next: StoredSession = { version: 1, token: tokenResponse.access_token, user }
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
        setSession(next)
      },
      logout: () => {
        window.localStorage.removeItem(STORAGE_KEY)
        setSession(null)
      },
    }),
    [session],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext)
  if (!value) throw new Error('useSession must be used inside SessionProvider')
  return value
}

