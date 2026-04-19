import { test, expect } from '@playwright/test';

test('basic page load', async ({ page }) => {
  await page.goto('/');

  // Check page title
  await expect(page).toHaveTitle('控制理论导师');

  // Navbar brand is rendered as text, not a heading element.
  await expect(page.getByText('控制理论导师').first()).toBeVisible();

  // Check initialization message
  await expect(page.getByText('系统初始化中...')).toBeVisible();
});
