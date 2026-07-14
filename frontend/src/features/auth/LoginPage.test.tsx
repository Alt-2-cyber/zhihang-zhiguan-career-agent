import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { LoginPage } from './LoginPage'


describe('LoginPage', () => {
  it('submits credentials and reports invalid login without persisting a session', async () => {
    const login = vi.fn().mockRejectedValue(new Error('用户名或密码错误'))
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <LoginPage onLogin={login} />
        </MemoryRouter>
      </QueryClientProvider>,
    )

    await user.type(screen.getByLabelText('账号'), 'student1')
    await user.type(screen.getByLabelText('密码'), 'wrong')
    await user.click(screen.getByRole('button', { name: '登录' }))

    expect(login).toHaveBeenCalledWith('student1', 'wrong')
    expect(await screen.findByRole('alert')).toHaveTextContent('用户名或密码错误')
  })
})

