import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ServerDemoBanner } from './ServerDemoBanner'

describe('ServerDemoBanner', () => {
  it('explains the capabilities missing from a low-resource server demo', () => {
    render(
      <ServerDemoBanner
        deploymentMode="server-demo"
        limitations={[
          'BGE-M3 未部署，Agent 不提供语义知识库检索。',
          'FunASR 和 MeloTTS 未部署，语音输入与朗读不可用。',
        ]}
      />,
    )

    expect(screen.getByRole('status')).toHaveTextContent('服务器演示版')
    expect(screen.getByRole('status')).toHaveTextContent('BGE-M3 未部署')
    expect(screen.getByRole('status')).toHaveTextContent('语音输入与朗读不可用')
  })

  it('does not render for the full deployment', () => {
    const { container } = render(<ServerDemoBanner deploymentMode="full" limitations={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
