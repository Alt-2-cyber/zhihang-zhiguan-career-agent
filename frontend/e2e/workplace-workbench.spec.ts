import { expect, test } from '@playwright/test'

test('student completes a post-hire work deliverable workflow', async ({ page }) => {
  await page.goto('/student/workplace')
  await page.getByLabel('账号').fill('student_demo')
  await page.getByLabel('密码').fill('Student123!')
  await page.getByRole('button', { name: '登录' }).click()

  await page.getByRole('link', { name: '职场训练' }).click()
  await expect(page.getByText('职场工作台', { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('工作简报与验收标准', { exact: true })).toBeVisible()
  await expect(page.getByText('选择一个工作问题', { exact: true })).toBeVisible()
  await expect(page.getByText('TRAINING FOCUS', { exact: true })).not.toBeVisible()
  const scenarioCard = page.getByRole('button', { name: /入职第一周任务澄清/ }).first()
  await expect(scenarioCard).toBeVisible({ timeout: 30_000 })
  await scenarioCard.click()
  await page.getByRole('button', { name: /进入工作任务台|继续当前任务|开始一份工作任务/ }).last().click()

  await expect(page.getByText('真实工作任务台', { exact: true })).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('任务简报', { exact: true })).toBeVisible()
  await page.getByLabel('交付物标题').fill('我的任务澄清清单')
  await page.getByLabel('交付物内容').fill(
    '目标是提交销售趋势简报。1. 与直属主管确认数据口径。2. 周五 18:00 前交付，并按照数据可追溯标准验收。3. 记录依赖和风险。',
  )
  await page.getByRole('button', { name: '提交交付物' }).click()
  await expect(page.getByText('交付物已提交，后端已完成结构化评审。')).toBeVisible({ timeout: 30_000 })
  await page.getByRole('button', { name: '完成本次复盘' }).click()
  await expect(page.getByText(/真实工作任务台/)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText(/已完成 ·/)).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('交付历史', { exact: true })).toBeVisible()
})
