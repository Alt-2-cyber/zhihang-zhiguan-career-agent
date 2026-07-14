import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '../../app/api'
import { StudentInterventions } from './StudentInterventions'

vi.mock('../../app/api', async () => {
  const actual = await vi.importActual<typeof import('../../app/api')>('../../app/api')
  return { ...actual, apiFetch: vi.fn() }
})

describe('StudentInterventions', () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset())

  it('submits student feedback for an assigned intervention', async () => {
    vi.mocked(apiFetch)
      .mockResolvedValueOnce([
        {
          id: 'task-1',
          title: '完成岗位筛选',
          description: '筛选 5 个匹配岗位',
          status: 'assigned',
          feedback: null,
        },
      ])
      .mockResolvedValueOnce({ status: 'submitted' })
      .mockResolvedValueOnce([])
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <StudentInterventions token="token" />
      </QueryClientProvider>,
    )

    await user.type(await screen.findByLabelText('任务反馈'), '已完成 5 个岗位筛选')
    await user.click(screen.getByRole('button', { name: '提交任务反馈' }))

    expect(apiFetch).toHaveBeenCalledWith(
      '/interventions/task-1/submit',
      expect.objectContaining({ method: 'PATCH' }),
      'token',
    )
  })
})

