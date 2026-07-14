import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import { apiFetch } from '../../app/api'
import { ProfilePage } from './ProfilePage'

vi.mock('../../app/api', async () => {
  const actual = await vi.importActual<typeof import('../../app/api')>('../../app/api')
  return { ...actual, apiFetch: vi.fn() }
})

const mockedApi = vi.mocked(apiFetch)

describe('student profile flow', () => {
  beforeEach(() => mockedApi.mockReset())

  it('shows evidence before the student confirms an AI profile', async () => {
    mockedApi
      .mockRejectedValueOnce(new Error('尚未确认画像'))
      .mockResolvedValueOnce({
        id: 'draft-1',
        provider: 'local-demo',
        status: 'pending',
        analysis: {
          summary: '具备数据分析基础',
          strengths: [
            {
              name: 'Python / SQL',
              level: '具备实践基础',
              evidence: [{ source: 'resume', quote: '使用 Python 完成销售数据分析' }],
            },
          ],
          gaps: ['缺少量化结果'],
          constraints: ['目标城市：上海'],
        },
      })
      .mockResolvedValueOnce({ status: 'confirmed' })
      .mockResolvedValueOnce({
        status: 'confirmed',
        summary: '具备数据分析基础',
        strengths: [],
        gaps: [],
        constraints: [],
      })

    const user = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <ProfilePage token="token" />
      </QueryClientProvider>,
    )

    await user.type(screen.getByLabelText('简历文本'), '使用 Python 完成销售数据分析')
    await user.type(screen.getByLabelText('目标城市'), '上海')
    await user.click(screen.getByRole('button', { name: '生成就业画像' }))

    expect(await screen.findByText('具备数据分析基础')).toBeInTheDocument()
    expect(screen.getAllByText('使用 Python 完成销售数据分析')).toHaveLength(2)
    await user.click(screen.getByRole('button', { name: '确认并保存画像' }))
    expect(await screen.findByText('画像已确认')).toBeInTheDocument()
  })
})
