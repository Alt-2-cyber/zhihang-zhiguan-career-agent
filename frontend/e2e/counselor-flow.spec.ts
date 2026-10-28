import { expect, test } from '@playwright/test'

test('counselor sees explainable risk facts', async ({ page }) => {
  await page.goto('/')
  await page.getByLabel('账号').fill('counselor_demo')
  await page.getByLabel('密码').fill('Counselor123!')
  await page.getByRole('button', { name: '登录' }).click()

  await expect(page.getByRole('heading', { name: '班级就业概览' })).toBeVisible()
  await expect(page.getByText('连续 14 天无投递记录')).toBeVisible()
  await expect(page.getByText('张同学').first()).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBe(
    await page.evaluate(() => document.documentElement.clientWidth),
  )
})
