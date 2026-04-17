import { test, expect } from '@playwright/test';

test.describe('应用基础功能', () => {
  test('页面加载成功', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await expect(page.locator('nav h1')).toContainText('控制理论导师');
  });

  test('导航栏存在', async ({ page }) => {
    await page.goto('http://localhost:3000');
    await expect(page.locator('nav')).toBeVisible();
    await expect(page.locator('a[href="/upload"]')).toBeVisible();
    await expect(page.locator('a[href="/tutor"]')).toBeVisible();
  });
});
