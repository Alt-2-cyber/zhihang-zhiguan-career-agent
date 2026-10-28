import { Headphones, LoaderCircle, Pause, Radio, Volume2 } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'

import { displayInterviewQuestion } from './interview-api'

const interviewerImageUrl = '/ai-interviewer.jpg?v=20260807-cn-v2'

export type DigitalHumanState = 'idle' | 'speaking' | 'listening' | 'thinking' | 'complete'

type Props = {
  modeLabel: string
  question: string | null
  competency?: string | null
  state: DigitalHumanState
  audioUrl?: string | null
  audioLoading?: boolean
  audioError?: string | null
  className?: string
}

const stateLabel: Record<DigitalHumanState, string> = {
  idle: '等待开始',
  speaking: '数字人正在提问',
  listening: '正在听你的回答',
  thinking: 'AI 正在评分',
  complete: '本场已完成',
}

export function DigitalHumanStage({
  modeLabel,
  question,
  competency,
  state,
  audioUrl,
  audioLoading = false,
  audioError,
  className = '',
}: Props) {
  const audioRef = useRef<HTMLAudioElement | null>(null)
  const [playing, setPlaying] = useState(false)
  const [autoplayBlocked, setAutoplayBlocked] = useState(false)

  useEffect(() => {
    const audio = audioRef.current
    if (!audioUrl || !audio) {
      setPlaying(false)
      setAutoplayBlocked(false)
      return
    }
    setAutoplayBlocked(false)
    audio.load()
    const result = audio.play()
    if (result) {
      result.then(() => setPlaying(true)).catch(() => setAutoplayBlocked(true))
    }
  }, [audioUrl])

  const playAudio = () => {
    const audio = audioRef.current
    if (!audio) return
    if (playing) {
      audio.pause()
      setPlaying(false)
      return
    }
    void audio.play().then(() => {
      setPlaying(true)
      setAutoplayBlocked(false)
    }).catch(() => setAutoplayBlocked(true))
  }

  const visualState = playing ? 'speaking' : state
  const visibleQuestion = displayInterviewQuestion(question)
  return (
    <section className={`digital-human-stage ${className}`} aria-label="数字人面试官">
      <div className="digital-human-stage__header">
        <div>
          <p className="digital-human-stage__eyebrow"><Radio size={13} />数字人面试官</p>
          <p className="digital-human-stage__mode">{modeLabel} · AI 出题与评分</p>
        </div>
        <span className={`digital-human-stage__status digital-human-stage__status--${visualState}`}>
          <span className="digital-human-stage__status-dot" />{stateLabel[visualState]}
        </span>
      </div>
      <div className={`digital-human-stage__visual digital-human-stage__visual--${visualState}`}>
        <div className="digital-human-stage__scanline" />
        <div className="digital-human-avatar" aria-hidden="true">
          <div className="digital-human-avatar__halo" />
          <img className="digital-human-avatar__photo" src={interviewerImageUrl} alt="亚洲女性专业面试官" />
          <span className="digital-human-avatar__signal" />
        </div>
        <div className="digital-human-stage__telemetry" aria-hidden="true">
          <span>语音 / 中文</span><span>AI 评分量表</span><span>实时</span>
        </div>
      </div>
      <div className="digital-human-stage__question">
        <div className="flex items-center justify-between gap-3">
          <p className="digital-human-stage__label">当前问题{competency ? ` · ${competency}` : ''}</p>
          {audioUrl ? (
            <button type="button" className="digital-human-stage__audio-button" onClick={playAudio} aria-label={playing ? '暂停问题语音' : '播放问题语音'}>
              {playing ? <Pause size={15} /> : <Volume2 size={15} />}{playing ? '暂停' : autoplayBlocked ? '点击播放' : '重播'}
            </button>
          ) : audioLoading ? <span className="digital-human-stage__audio-state"><LoaderCircle className="animate-spin" size={14} />语音生成中</span> : null}
        </div>
        <p className="digital-human-stage__prompt">{visibleQuestion ?? '面试开始后，AI 会在这里自动提出第一个问题。'}</p>
        {audioError ? <p className="digital-human-stage__error">{audioError}，可直接阅读文字问题。</p> : null}
        <div className="digital-human-stage__hint"><Headphones size={14} />支持数字人朗读、语音回答和文字回答；回答评分与可选的摄像头表达稳定度分开计算。</div>
      </div>
      {audioUrl ? <audio ref={audioRef} src={audioUrl} className="sr-only" onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => setPlaying(false)} onError={() => { setPlaying(false); setAutoplayBlocked(true) }} aria-label="数字人问题语音" /> : null}
    </section>
  )
}
