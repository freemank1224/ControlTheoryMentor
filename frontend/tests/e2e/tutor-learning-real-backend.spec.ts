import { test, expect } from '@playwright/test';

const FIXTURE_GRAPH_ID = 'graph-fixture-e2e-real';

test.describe('Tutor Learning Real Backend (Docker)', () => {
  test('runs full tutor flow with real backend fixture data', async ({ page }) => {
    test.setTimeout(120_000);

    const learnerId = `learner-docker-e2e-${Date.now()}`;

    await page.goto('/tutor');

    await page.getByPlaceholder('输入学习问题').fill('How does PID reduce steady-state error?');
    await page.getByPlaceholder('graph id').fill(FIXTURE_GRAPH_ID);
    await page.getByPlaceholder('learner id (用于学习闭环)').fill(learnerId);

    await page.getByRole('button', { name: '启动会话' }).click();
    await expect(page.locator('.tutor-page__status').filter({ hasText: '状态: ready' }).first()).toBeVisible();

    const nextButton = page.locator('.tutor-page__actions').getByRole('button', {
      name: '下一步',
      exact: true,
    });

    const stepHeading = page.locator('.tutor-page__panel-header h3').first();
    await nextButton.click();
    await expect(stepHeading).toContainText('当前步骤:');

    const responseInput = page.getByPlaceholder('请输入你对当前步骤的回答');
    if (await responseInput.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await responseInput.fill('Integral action accumulates error over time and helps remove steady-state offset.');
      await page.getByRole('button', { name: '提交回答' }).click();
      await expect(page.locator('.tutor-page__status').filter({ hasText: '导师反馈:' }).first()).toBeVisible();
    }

    if (await nextButton.isEnabled()) {
      await nextButton.click();
      await expect(stepHeading).toContainText('当前步骤:');
    }

    const feedbackSelect = page.locator('#feedback-difficulty');
    if (await feedbackSelect.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await feedbackSelect.selectOption('too_hard');
      await page.getByRole('button', { name: '提交学习反馈' }).click();
      await expect(page.locator('.tutor-page__learning')).toContainText('feedback: 1');
      await expect(page.locator('.tutor-page__learning')).toContainText('待复习 concept-pid');
    }

    await page.getByPlaceholder('输入学习问题').fill('What should I practice next?');
    await page.getByRole('button', { name: '启动会话' }).click();
    await expect(page.locator('.tutor-page__learning')).toContainText('待复习 concept-pid');

    const transferCheckButton = page.getByRole('button', { name: '理解检查与迁移' });
    if (await transferCheckButton.isVisible({ timeout: 2_000 }).catch(() => false)) {
      await transferCheckButton.click();
      await expect(page.locator('.tutor-page__messages')).toContainText('优先提到 concept-pid');
    }
  });
});
