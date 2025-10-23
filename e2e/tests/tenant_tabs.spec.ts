import { test, expect } from '@playwright/test';
import { loginAsSuperuser } from './utils/auth';

// This test is optional but helps validate the ARIA + visibility for tabs
// It creates a tenant via the modal and navigates using the "Öppna" link

test('tabs switch with click and update ARIA/visibility', async ({ page }) => {
  await loginAsSuperuser(page);
  await page.goto('/superuser/dashboard');

  // Open create-tenant modal
  await page.getByTestId('qa-create-tenant').click();
  const dlg = page.getByRole('dialog', { name: /Skapa tenant/i });

  const name = `Varbergs kommun ${Date.now()}`;
  await dlg.getByLabel(/Namn/i).fill(name);
  // Submit
  await dlg.getByRole('button', { name: /Skapa|Spara|Create/i }).click();

  // Go to tenant page
  await page.getByRole('link', { name: /Öppna/i }).first().click();

  // Click to Org-enheter tab
  const tabOrg = page.getByTestId('tab-org');
  const panelOrg = page.getByTestId('panel-org');
  await tabOrg.click();
  await expect(tabOrg).toHaveAttribute('aria-selected', 'true');
  await expect(panelOrg).toBeVisible();

  // Overview should be unselected/hidden
  const tabOverview = page.getByTestId('tab-overview');
  const panelOverview = page.getByTestId('panel-overview');
  await expect(tabOverview).toHaveAttribute('aria-selected', 'false');
  await expect(panelOverview).toBeHidden();
});
