import { Camera, CameraOff, LoaderCircle, ScanFace, ShieldCheck } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'

import { apiFetch } from '../../app/api'
import type { EmotionObservation } from './interview-api'

type Props = {
  sessionId: string
  token: string
  disabled?: boolean
  unavailable?: boolean
}

type CameraState = 'off' | 'starting' | 'active' | 'error'

const SAMPLE_INTERVAL_MS = 1_000

export function EmotionCamera({ sessionId, token, disabled = false, unavailable = false }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<number | null>(null)
  const inFlightRef = useRef(false)
  const [state, setState] = useState<CameraState>('off')
  const [error, setError] = useState('')
  const [observation, setObservation] = useState<EmotionObservation | null>(null)

  const stop = useCallback(() => {
    if (timerRef.current !== null) window.clearInterval(timerRef.current)
    timerRef.current = null
    streamRef.current?.getTracks().forEach((track) => track.stop())
    streamRef.current = null
    if (videoRef.current) videoRef.current.srcObject = null
    setState('off')
  }, [])

  const sample = useCallback(async () => {
    const video = videoRef.current
    if (!video || !video.videoWidth || inFlightRef.current || state !== 'active') return
    inFlightRef.current = true
    try {
      const canvas = document.createElement('canvas')
      const scale = Math.min(1, 640 / video.videoWidth)
      canvas.width = Math.max(1, Math.round(video.videoWidth * scale))
      canvas.height = Math.max(1, Math.round(video.videoHeight * scale))
      canvas.getContext('2d')?.drawImage(video, 0, 0, canvas.width, canvas.height)
      const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.72))
      if (!blob) return
      const body = new FormData()
      body.append('file', blob, 'emotion-frame.jpg')
      const result = await apiFetch<EmotionObservation>(
        `/interviews/${sessionId}/emotion/analyze`,
        { method: 'POST', body },
        token,
        25_000,
      )
      setObservation(result)
      if (result.warning) setError(result.warning)
      else setError('')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : '情绪分析服务暂时不可用')
    } finally {
      inFlightRef.current = false
    }
  }, [sessionId, state, token])

  const start = async () => {
    if (disabled || unavailable || state === 'active' || state === 'starting') return
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('当前浏览器不支持摄像头访问')
      setState('error')
      return
    }
    setState('starting')
    setError('')
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
        audio: false,
      })
      streamRef.current = stream
      if (!videoRef.current) throw new Error('摄像头预览初始化失败')
      videoRef.current.srcObject = stream
      await videoRef.current.play()
      setState('active')
    } catch (reason) {
      streamRef.current?.getTracks().forEach((track) => track.stop())
      streamRef.current = null
      setState('error')
      setError(reason instanceof Error ? reason.message : '摄像头启动失败，请检查浏览器权限')
    }
  }

  useEffect(() => stop, [stop])
  useEffect(() => {
    if (state !== 'active') return
    void sample()
    timerRef.current = window.setInterval(() => void sample(), SAMPLE_INTERVAL_MS)
    return () => {
      if (timerRef.current !== null) window.clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [sample, state])
  useEffect(() => {
    if (disabled) stop()
  }, [disabled, stop])

  return (
    <section className="border border-[#102015]/12 bg-white/70 p-4" aria-label="面试摄像头情绪分析">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2 text-sm font-bold text-[#102015]"><ScanFace size={17} className="text-[#0f766e]" />摄像头表达分析</div>
          <p className="mt-1 text-xs leading-5 text-[#647460]">{unavailable ? '当前服务器演示版未部署 YOLO 与本地表情模型，摄像头分析不可用。' : 'YOLO 人脸检测 + 本地表情模型，每 1 秒采样一次，仅保存统计结果。'}</p>
        </div>
        <button
          type="button"
          className="inline-flex items-center gap-2 border border-[#102015]/20 bg-white px-3 py-2 text-xs font-semibold text-[#102015] transition hover:border-[#0f766e] disabled:cursor-not-allowed disabled:opacity-50"
          onClick={() => (state === 'active' ? stop() : void start())}
          disabled={disabled || unavailable || state === 'starting'}
        >
          {state === 'active' ? <CameraOff size={15} /> : state === 'starting' ? <LoaderCircle size={15} className="animate-spin" /> : <Camera size={15} />}
          {state === 'active' ? '停止分析' : state === 'starting' ? '启动中' : '开启摄像头'}
        </button>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-[180px_minmax(0,1fr)]">
        <div className="relative aspect-[4/3] overflow-hidden bg-[#102015]">
          <video ref={videoRef} muted playsInline className="h-full w-full object-cover" aria-label="摄像头预览" />
          {state === 'active' && observation?.face_boxes?.length ? <div className="pointer-events-none absolute inset-0" aria-label="YOLO 人脸标注框">
            {observation.face_boxes.map((box, index) => <div
              key={`${box.x}-${box.y}-${box.width}-${box.height}-${index}`}
              className="absolute border-2 border-[#c7ff4c] shadow-[0_0_0_1px_rgba(16,32,21,0.55)]"
              style={{ left: `${box.x * 100}%`, top: `${box.y * 100}%`, width: `${box.width * 100}%`, height: `${box.height * 100}%` }}
            >
              <span className="absolute -top-5 left-0 whitespace-nowrap bg-[#c7ff4c] px-1.5 py-0.5 text-[10px] font-bold text-[#102015]">人脸 {index + 1} · {Math.round(box.confidence * 100)}%</span>
            </div>)}
          </div> : null}
          {state !== 'active' ? <div className="absolute inset-0 grid place-items-center px-4 text-center text-[11px] leading-5 text-[#cfdbc9]">{unavailable ? '当前服务器演示版未部署摄像头分析服务' : '开启后，画面仅用于当前面试的分析请求，不保存原始视频'}</div> : null}
          {state === 'active' ? <span className="absolute left-2 top-2 inline-flex items-center gap-1 bg-[#c7ff4c] px-2 py-1 text-[10px] font-bold text-[#102015]"><span className="size-1.5 rounded-full bg-[#0f766e]" />分析中</span> : null}
        </div>
        <div className="min-w-0 text-xs text-[#526051]">
          <div className="flex items-center gap-2 font-semibold text-[#102015]"><ShieldCheck size={15} className="text-[#0f766e]" />训练参考，不用于录用判断</div>
          {unavailable ? <p className="mt-3 leading-5">此部署不采集摄像头画面，也不会生成表情或情绪分析结果。</p> : observation ? <div className="mt-3 grid grid-cols-2 gap-2">
            <div className="border border-[#102015]/10 bg-white/70 p-2"><span className="block text-[11px] text-[#647460]">当前表情</span><strong className="mt-1 block text-[#102015]">{observation.dominant_emotion_label}</strong></div>
            <div className="border border-[#102015]/10 bg-white/70 p-2"><span className="block text-[11px] text-[#647460]">人脸检测</span><strong className="mt-1 block text-[#102015]">{observation.face_count} 张 · {Math.round(observation.confidence * 100)}%</strong></div>
          </div> : <p className="mt-3 leading-5">尚未采集样本。不开启摄像头时，不会生成情绪分数。</p>}
          {error ? <p className="mt-2 text-[#b64935]">{error}</p> : null}
        </div>
      </div>
    </section>
  )
}
