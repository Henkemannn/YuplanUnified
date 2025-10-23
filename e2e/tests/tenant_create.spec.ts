import { test, expect } from '@playwright/test';
import { loginAsSuperuser } from './utils/auth';

test('create tenant from dashboard modal updates KPI and events', async ({ page }) => {
  await loginAsSuperuser(page);
  await page.goto('/superuser/dashboard');

  // Öppna modal
  await page.getByTestId('qa-create-tenant').click();
  const dlg = page.getByRole('dialog', { name: /Skapa tenant/i });
  await expect(dlg).toBeVisible();

  // Fyll fält
  const name = `Varbergs kommun ${Date.now()}`;
  await dlg.getByLabel(/Namn/i).fill(name);
  // Slug fylls auto – valfritt: asserta att slugfältet fått värde
  const slugInput = dlg.getByLabel(/Slug/i);
  await expect(slugInput).toHaveValue(/varbergs-komm/);

  // Läs KPI före
  const kpiBefore = await page.getByTestId('kpi-tenants').locator('[data-kpi-value]').innerText();

  // Skicka
  await dlg.getByRole('button', { name: /Skapa|Spara|Create/i }).click();

  // Modal stängd
  await expect(dlg).toBeHidden();

  // KPI uppdaterad (enklast: värde ändras från tidigare text)
  await expect(page.getByTestId('kpi-tenants').locator('[data-kpi-value]')).not.toHaveText(kpiBefore);

  // Event syns högst upp (minst en rad)
  const firstEvent = page.getByTestId('event-item').first();
  await expect(firstEvent).toBeVisible();
  await expect(firstEvent).toContainText(/Tenant skapad|skapad/i);

  // Navigera till tenantsidan via länken "Öppna"
  const openLink = firstEvent.getByRole('link', { name: /Öppna/i });
  await openLink.click();
  await expect(page.locator('[data-testid="tenant-title"]')).toBeVisible();

  // (Valfritt) Öppna tenant-länk om du visar en snackbar/länk efter create
  // await page.getByRole('link', { name: new RegExp(name, 'i') }).click();
  // await expect(page).toHaveURL(/\/tenants\/\w+/);
});
