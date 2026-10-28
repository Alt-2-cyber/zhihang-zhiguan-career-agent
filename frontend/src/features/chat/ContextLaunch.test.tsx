import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { AskAgentButton } from './AskAgentButton'
import type { ChatContextRef } from './types'

function AssistantTarget() {
  const location = useLocation()
  return <pre>{JSON.stringify({ path: location.pathname, context: location.state?.context })}</pre>
}

describe('AskAgentButton', () => {
  it('navigates with only a typed job reference in router state', async () => {
    const context: ChatContextRef = { type: 'job', id: 'job-1' }
    render(
      <MemoryRouter initialEntries={['/student/jobs']}>
        <Routes>
          <Route path="/student/jobs" element={<AskAgentButton role="student" context={context} />} />
          <Route path="/student/assistant" element={<AssistantTarget />} />
        </Routes>
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole('button', { name: '询问 Agent' }))

    expect(screen.getByText(JSON.stringify({ path: '/student/assistant', context }))).toBeInTheDocument()
    expect(window.localStorage.length).toBe(0)
  })

  it('uses the counselor assistant route for student context', async () => {
    render(
      <MemoryRouter initialEntries={['/counselor/students']}>
        <Routes>
          <Route path="/counselor/students" element={<AskAgentButton role="counselor" context={{ type: 'student', id: 'student-1' }} />} />
          <Route path="/counselor/assistant" element={<AssistantTarget />} />
        </Routes>
      </MemoryRouter>,
    )

    await userEvent.click(screen.getByRole('button', { name: '询问 Agent' }))

    expect(screen.getByText(/counselor\/assistant/)).toBeInTheDocument()
  })
})
