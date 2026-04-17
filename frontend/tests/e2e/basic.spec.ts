import { test, expect } from '@playwright/test';

test('页面加载成功', async ({ page }) => {
  await page.goto('http://localhost:5173');
  await expect(page.locator('h1')).toContainText('控制理论导师');
});

test('欢迎页面显示正确', async ({ page }) => {
  await page.goto('http://localhost:5173');

  // 检查主标题
  await expect(page.locator('h1')).toContainText('控制理论导师');

  // 检查副标题
  await expect(page.locator('.subtitle')).toContainText('AI 驱动的个性化学习系统');

  // 检查欢迎标题
  await expect(page.locator('h2')).toContainText('欢迎来到控制理论学习平台');

  // 检查特性卡片存在
  await expect(page.locator('.feature-card')).toHaveCount(3);

  // 检查特性卡片内容
  await expect(page.locator('.feature-card').nth(0)).toContainText('知识图谱');
  await expect(page.locator('.feature-card').nth(1)).toContainText('自适应学习');
  await expect(page.locator('.feature-card').nth(2)).toContainText('AI 导师');
});
