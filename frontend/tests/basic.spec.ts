import { test, expect } from '@playwright/test';

test('basic page load', async ({ page }) => {
  await page.goto('/');

  // Check page title
  await expect(page).toHaveTitle('控制理论导师');

  // Check main heading
  const heading = page.getByRole('heading', { name: '控制理论导师' });
  await expect(heading).toBeVisible();

  // Check initialization message
  await expect(page.getByText('系统初始化中...')).toBeVisible();
});
