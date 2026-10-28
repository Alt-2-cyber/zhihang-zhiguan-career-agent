import { expect, test } from '@playwright/test'

test('student can inspect evidence-based job matching', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('账号').fill('student_demo')
  await page.getByLabel('密码').fill('Student123!')
  await page.getByRole('button', { name: '登录' }).click()

  if (page.viewportSize()!.width < 1024) {
    await page.getByRole('button', { name: '打开导航' }).click()
  }
  await expect(page.getByRole('link', { name: '工作台' })).toBeVisible()
  await page.getByRole('link', { name: '岗位匹配' }).click()
  await page.getByRole('button', { name: /数据分析师.*星云科技.*上海/ }).click()
  await page.getByRole('button', { name: '开始五维匹配' }).click()

  await expect(page.getByText('综合匹配度')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('硬性条件', { exact: true })).toBeVisible()
  await expect(page.getByText('技能匹配', { exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    await page.evaluate(() => document.documentElement.clientWidth),
  )
})
