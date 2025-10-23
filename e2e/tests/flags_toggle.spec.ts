import { test, expect } from '@playwright/test';
import { loginAsSuperuser } from './utils/auth';

test('toggle a feature flag on/off without reload', async ({ page }) => {
  await loginAsSuperuser(page);
  await page.goto('/feature-flags');
  const list = page.getByTestId('ff-list');
  await expect(list).toBeVisible();

  const first = list.locator('button').first();
  await first.waitFor({ state: 'visible', timeout: 5000 });
  const before = await first.getAttribute('aria-pressed');
  await first.click();
  await expect(first).toHaveAttribute('aria-pressed', before === 'true' ? 'false' : 'true');
});
