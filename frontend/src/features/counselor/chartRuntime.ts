import { PieChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import { init, use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

use([PieChart, TooltipComponent, CanvasRenderer])

export function initOverviewChart(
  element: HTMLDivElement,
  normalCount: number,
  riskCount: number,
) {
  const chart = init(element)
  chart.setOption({
    tooltip: { trigger: 'item' },
    color: ['#0f766e', '#d97706'],
    series: [
      {
        type: 'pie',
        radius: ['55%', '78%'],
        label: { show: false },
        data: [
          { name: '正常跟进', value: normalCount },
          { name: '需要关注', value: riskCount },
        ],
      },
    ],
  })
  return chart
}

