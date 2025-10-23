import { test, expect } from '@playwright/test';
import { loginAsSuperuser } from './utils/auth';

test('toggle tenant module on/off', async ({ page }) => {
  await loginAsSuperuser(page);
  // create tenant via dashboard
  await page.goto('/superuser/dashboard');
  await page.getByTestId('qa-create-tenant').click();
  const dlg = page.getByRole('dialog', { name: /Skapa tenant/i });
  await dlg.getByLabel(/Namn/i).fill('ModulTenant ' + Date.now());
  await dlg.getByRole('button', { name: /Skapa|Spara|Create/i }).click();
  // Click the tenant link from the newly added dashboard event (more specific than any generic "Öppna" link)
  await page.locator('#events-list a.link').first().click();
  // go to Moduler
  await page.getByTestId('tab-modules').click();
  const list = page.getByTestId('tm-list');
  await expect(list).toBeVisible();
  const btn = list.locator('button').first();
  await btn.waitFor({ state: 'visible', timeout: 5000 });
  const before = await btn.getAttribute('aria-pressed');
  await btn.click();
  await expect(btn).toHaveAttribute('aria-pressed', before === 'true' ? 'false' : 'true');
});
