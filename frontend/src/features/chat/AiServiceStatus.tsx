import { AlertTriangle, CheckCircle2, CircleDashed, ShieldCheck, XCircle } from 'lucide-react'

import type { AiCapabilities } from './types'

function StatePill({ ready, label }: { ready: boolean | null; label: string }) {
  const Icon = ready === null ? CircleDashed : ready ? CheckCircle2 : XCircle
  const className = ready === null
    ? 'border-[#102015]/15 bg-white/60 text-[#647460]'
    : ready
      ? 'border-emerald-700/25 bg-emerald-50 text-emerald-800'
      : 'border-[#ff7358]/40 bg-[#fff0eb] text-[#8c2f1f]'
  return (
    <span className={`inline-flex items-center gap-1 rounded-md border px-2 py-1 text-xs font-semibold ${className}`}>
      <Icon size={13} />
      {label}
    </span>
  )
}

export function AiServiceStatus({
  capabilities,
  loading,
  failed,
}: {
  capabilities?: AiCapabilities
  loading: boolean
  failed: boolean
}) {
  const onlineProviders = capabilities?.agent.providers.filter((item) => item.name !== 'local-rules') ?? []
  const onlineReady = onlineProviders.some((item) => item.configured)
  const strictOnline = capabilities?.agent.strict_online ?? true
  const embeddingReady = capabilities?.services.embedding.ready ?? null
  const ocrReady = capabilities?.services.ocr.ready ?? null
  const speechReady = capabilities?.services.speech.ready ?? null
  const emotionReady = capabilities?.services.emotion?.ready ?? null
  const unhealthy = Boolean(
    failed
    || (capabilities && (
      !onlineReady
      || !embeddingReady
      || !ocrReady
      || !speechReady
      || !emotionReady
    )),
  )
  const providerText = onlineProviders.length
    ? onlineProviders.map((item) => `${item.name}:${item.model}${item.configured ? '' : '(未配置)'}`).join(' → ')
    : '未配置在线模型'

  return (
    <div className={`border-b px-4 py-3 ${unhealthy ? 'border-[#ff7358]/35 bg-[#fff0eb]' : 'border-[#102015]/15 bg-[#f4f8f1]'}`}>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="inline-flex items-center gap-1 font-bold text-[#102015]">
          {unhealthy ? <AlertTriangle size={14} className="text-[#b24531]" /> : <ShieldCheck size={14} className="text-emerald-800" />}
          AI 服务状态
        </span>
        <StatePill ready={loading ? null : onlineReady} label={`在线模型：${providerText}`} />
        <StatePill ready={embeddingReady} label={`BGE-M3：${embeddingReady === null ? '检测中' : embeddingReady ? '可用' : '不可用'}`} />
        <StatePill ready={ocrReady} label={`OCR：${ocrReady === null ? '检测中' : ocrReady ? '可用' : '不可用'}`} />
        <StatePill ready={speechReady} label={`ASR/TTS：${speechReady === null ? '检测中' : speechReady ? '可用' : '不可用'}`} />
        <StatePill ready={emotionReady} label={`摄像头分析：${emotionReady === null ? '未配置' : emotionReady ? '可用' : '不可用'}`} />
        <span className="text-xs font-medium text-[#526051]">
          {strictOnline ? '严格在线：模型失败不使用本地规则代替' : '允许本地规则兜底'}
        </span>
      </div>
      {failed ? (
        <p className="mt-1 text-[11px] text-[#8c2f1f]">能力接口读取失败，请检查后端 /api/ai/capabilities。</p>
      ) : capabilities?.deployment_mode === 'server-demo' ? (
        <p className="mt-1 text-[11px] text-[#8c2f1f]">此服务器演示版使用外部模型 API；BGE-M3、OCR、ASR/TTS 和 YOLO 本地服务未部署，不能执行语义检索、扫描件 OCR、语音或摄像头分析。</p>
      ) : unhealthy ? (
        <p className="mt-1 text-[11px] text-[#8c2f1f]">不可用能力会禁用对应入口；请优先使用 Docker 全量启动并等待模型服务 ready。</p>
      ) : null}
    </div>
  )
}
