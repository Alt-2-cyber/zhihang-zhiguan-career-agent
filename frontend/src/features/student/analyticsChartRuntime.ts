import { LineChart, RadarChart } from 'echarts/charts'
import { GridComponent, LegendComponent, RadarComponent, TooltipComponent } from 'echarts/components'
import { init, use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

use([LineChart, RadarChart, GridComponent, LegendComponent, RadarComponent, TooltipComponent, CanvasRenderer])

type RadarItem = {
  skill_name: string
  baseline: number
  current: number
  target: number
  evidence_count: number
  latest_exam_score: number | null
  latest_training_score: number | null
  data_status: string
  score_reason: string
}
type TrendItem = { period: string; average_score: number | null; completed_tasks: number; exam_count: number }

export function initLearningRadar(element: HTMLDivElement, items: RadarItem[]) {
  const chart = init(element)
  chart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: () => items.map((item) => `${item.skill_name}<br/>当前评估：${item.current} / 目标：${item.target}<br/>诊断基线：${item.baseline} · 有效证据：${item.evidence_count} 条`).join('<br/><br/>'),
    },
    legend: { bottom: 0, data: ['当前水平', '目标水平'] },
    radar: {
      indicator: items.map((item) => ({ name: `${item.skill_name}\n${item.current}/${item.target}`, max: 100 })),
      radius: '62%',
      splitNumber: 4,
      axisName: { color: '#475569', fontSize: 11 },
    },
    series: [{
      type: 'radar',
      data: [
        { value: items.map((item) => item.current), name: '当前水平', areaStyle: { color: 'rgba(15, 118, 110, 0.16)' }, lineStyle: { color: '#0f766e' }, itemStyle: { color: '#0f766e' } },
        { value: items.map((item) => item.target), name: '目标水平', areaStyle: { color: 'rgba(14, 165, 233, 0.10)' }, lineStyle: { color: '#0284c7' }, itemStyle: { color: '#0284c7' } },
      ],
    }],
  })
  return chart
}

export function initLearningTrend(element: HTMLDivElement, items: TrendItem[]) {
  const chart = init(element)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0, data: ['考试平均分', '完成任务'] },
    grid: { top: 20, right: 18, bottom: 48, left: 42 },
    xAxis: { type: 'category', data: items.map((item) => item.period.slice(5)), axisLabel: { color: '#64748b' } },
    yAxis: [
      { type: 'value', min: 0, max: 100, axisLabel: { color: '#64748b' } },
      { type: 'value', min: 0, axisLabel: { color: '#64748b' } },
    ],
    series: [
      { name: '考试平均分', type: 'line', smooth: true, connectNulls: true, data: items.map((item) => item.average_score), itemStyle: { color: '#0f766e' }, lineStyle: { color: '#0f766e' } },
      { name: '完成任务', type: 'line', yAxisIndex: 1, smooth: true, data: items.map((item) => item.completed_tasks), itemStyle: { color: '#0284c7' }, lineStyle: { color: '#0284c7' } },
    ],
  })
  return chart
}
