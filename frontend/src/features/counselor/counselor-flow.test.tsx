import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '../../app/api'
import { CounselorDashboard } from './CounselorDashboard'

vi.mock('../../app/api', async () => {
  const actual = await vi.importActual<typeof import('../../app/api')>('../../app/api')
  return { ...actual, apiFetch: vi.fn() }
})

describe('counselor dashboard', () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset())

  it('shows the risk fact instead of an opaque score', async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      student_count: 1,
      application_count: 0,
      risk_count: 1,
      students: [{ id: 'student-1', display_name: '张同学', username: 'student1', risk_count: 1 }],
      risks: [
        {
          id: 'risk-1',
          student_id: 'student-1',
          rule_code: 'no_recent_application',
          level: 'intervention',
          facts: { message: '连续 14 天无投递记录', value: 14 },
        },
      ],
    })

    render(
      <QueryClientProvider client={new QueryClient()}>
        <CounselorDashboard token="token" />
      </QueryClientProvider>,
    )

    expect(await screen.findByText('连续 14 天无投递记录')).toBeInTheDocument()
    expect(screen.getByText('张同学')).toBeInTheDocument()
  })
})

