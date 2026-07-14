import { expect, test } from '@playwright/test'

test('student can inspect evidence-based job matching', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('账号').fill('student_demo')
  await page.getByLabel('密码').fill('Student123!')
  await page.getByRole('button', { name: '登录' }).click()
  await expect(page.getByRole('heading', { name: '学生工作台' })).toBeVisible()

  if (page.viewportSize()!.width < 1024) {
    await page.getByRole('button', { name: '打开导航' }).click()
  }
  await page.getByRole('link', { name: '岗位匹配' }).click()
  await page.getByRole('button', { name: /数据分析师.*星云科技.*上海/ }).click()
  await page.getByRole('button', { name: '开始五维匹配' }).click()

  await expect(page.getByText('综合匹配度')).toBeVisible()
  await expect(page.getByText('硬性条件', { exact: true })).toBeVisible()
  await expect(page.getByText(/依据：要求 Python/).first()).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    await page.evaluate(() => document.documentElement.clientWidth),
  )
})
