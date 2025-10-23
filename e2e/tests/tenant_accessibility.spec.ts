import { test, expect } from '@playwright/test';
import { loginAsSuperuser } from './utils/auth';

test('Tenantsidan sätter fokus på H1 och har ARIA-korrekta tabs', async ({ page }) => {
  await loginAsSuperuser(page);
  await page.goto('/superuser/dashboard');
  await page.getByTestId('qa-create-tenant').click();
  const name = `Varbergs kommun ${Date.now()}`;
  const dlg = page.getByRole('dialog', { name: /Skapa tenant/i });
  await dlg.getByLabel(/Namn/i).fill(name);
  await dlg.getByRole('button', { name: /Skapa|Spara|Create/i }).click();
  await page.getByRole('link', { name: /Öppna/i }).first().click();

  // H1 focus
  const h1 = page.getByTestId('tenant-title');
  await expect(h1).toBeVisible();
  await expect(h1).toBeFocused();

  // Tabs – role and aria-selected
  const overview = page.getByRole('tab', { name: /Översikt/i });
  await expect(overview).toHaveAttribute('aria-selected', 'true');
  const org = page.getByRole('tab', { name: /Org-enheter/i });
  await expect(org).toHaveAttribute('aria-selected', 'false');

  // Panel linkage
  const panelOverview = page.locator('#panel-overview');
  await expect(panelOverview).toHaveAttribute('role', 'tabpanel');
  await expect(panelOverview).toHaveAttribute('aria-labelledby', /tab-overview/);
});
