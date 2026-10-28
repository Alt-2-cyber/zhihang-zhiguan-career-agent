import { useEffect, useRef, useState } from 'react'

export function useAudioRecorder(
  onRecorded: (blob: Blob) => void,
  messages: {
    unsupported?: string
    denied?: string
    missing?: string
    busy?: string
    failed?: string
  } = {},
) {
  const [recording, setRecording] = useState(false)
  const [error, setError] = useState('')
  const recorderRef = useRef<MediaRecorder | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const mountedRef = useRef(true)
  const callbackRef = useRef(onRecorded)
  callbackRef.current = onRecorded

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
      streamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  const start = async () => {
    setError('')
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setError(messages.unsupported ?? '当前浏览器不支持录音，仍可直接输入文字')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      chunksRef.current = []
      const recorder = new MediaRecorder(stream)
      recorderRef.current = recorder
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunksRef.current.push(event.data)
      }
      recorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        stream.getTracks().forEach((track) => track.stop())
        streamRef.current = null
        recorderRef.current = null
        if (mountedRef.current) {
          setRecording(false)
          if (blob.size) callbackRef.current(blob)
        }
      }
      recorder.start()
      setRecording(true)
    } catch (reason) {
      const name = reason instanceof DOMException ? reason.name : ''
      if (name === 'NotAllowedError' || name === 'SecurityError') {
        setError(messages.denied ?? '麦克风权限被拒绝，请允许访问后重试')
      } else if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
        setError(messages.missing ?? '未检测到可用麦克风，请连接设备后重试')
      } else if (['NotReadableError', 'TrackStartError', 'AbortError'].includes(name)) {
        setError(messages.busy ?? '麦克风可能被其他程序占用，请关闭占用程序后重试')
      } else {
        setError(messages.failed ?? '麦克风启动失败，请检查设备后重试')
      }
    }
  }

  const stop = () => {
    if (recorderRef.current?.state === 'recording') recorderRef.current.stop()
  }

  return { recording, error, start, stop }
}
