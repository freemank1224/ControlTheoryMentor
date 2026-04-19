import { test, expect } from '@playwright/test';

test.describe('PDF 上传功能', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/upload');
  });

  test('显示上传卡片', async ({ page }) => {
    await expect(page.locator('text=上传教材 PDF')).toBeVisible();
    await expect(page.locator('button:has-text("选择 PDF 文件")')).toBeVisible();
  });

  test('点击上传按钮打开文件选择器', async ({ page }) => {
    const fileChooserPromise = page.waitForEvent('filechooser');
    await page.click('button:has-text("选择 PDF 文件")');
    const fileChooser = await fileChooserPromise;
    expect(fileChooser).toBeTruthy();
  });

  test('样式验证 - DESIGN.md 规范', async ({ page }) => {
    const uploadCard = page.locator('text=上传教材 PDF').locator('..');

    // Verify background color
    const backgroundColor = await uploadCard.evaluate(el =>
      window.getComputedStyle(el).backgroundColor
    );
    expect(backgroundColor).toBe('rgb(250, 249, 245)'); // Ivory
  });
});
