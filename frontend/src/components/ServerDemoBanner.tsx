import { AlertTriangle, ChevronDown } from 'lucide-react'

export function ServerDemoBanner({
  deploymentMode,
  limitations,
}: {
  deploymentMode?: string
  limitations?: string[]
}) {
  if (deploymentMode !== 'server-demo') return null

  return (
    <section className="border-b border-amber-800/20 bg-[#fff6df] px-4 py-2.5 text-[#49380e] sm:px-6" role="status" aria-live="polite">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs leading-5">
        <AlertTriangle size={15} aria-hidden="true" className="shrink-0 text-amber-800" />
        <strong>服务器演示版</strong>
        <span>业务记录按数据库实际内容提供；在线 Agent 依赖外部模型配置与网络；扫描件 OCR、语义知识检索、语音及摄像头分析未部署。</span>
        {limitations?.length ? (
          <details className="basis-full sm:basis-auto">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1 font-semibold underline underline-offset-2">
              查看当前能力范围
              <ChevronDown size={13} aria-hidden="true" />
            </summary>
            <ul className="mt-1 list-inside list-disc space-y-0.5 pl-5">
              {limitations.map((limitation) => <li key={limitation}>{limitation}</li>)}
            </ul>
          </details>
        ) : null}
      </div>
    </section>
  )
}
