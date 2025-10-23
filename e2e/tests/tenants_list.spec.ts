import { test, expect } from '@playwright/test';
import { loginAsSuperuser } from './utils/auth';

test('tenants list renders and navigates to detail', async ({ page }) => {
  await loginAsSuperuser(page);
  await page.goto('/tenants');
  const list = page.getByTestId('tenants-list');
  await expect(list).toBeVisible();
  // If empty, create one via dashboard modal
  if ((await page.getByTestId('tenant-link').count()) === 0) {
    await page.goto('/superuser/dashboard');
    await page.getByTestId('qa-create-tenant').click();
    const dlg = page.getByRole('dialog', { name: /Skapa tenant/i });
    await dlg.getByLabel(/Namn/i).fill('Lista Tenant ' + Date.now());
    await dlg.getByRole('button', { name: /Skapa|Spara|Create/i }).click();
    await page.goto('/tenants');
  }
  const first = page.getByTestId('tenant-link').first();
  await expect(first).toBeVisible();
  const href = await first.getAttribute('href');
  await first.click();
  await expect(page).toHaveURL(href!);
  await expect(page.getByTestId('tenant-title')).toBeVisible();
});
