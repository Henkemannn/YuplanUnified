import { test, expect } from '@playwright/test';
import { loginAsSuperuser } from './utils/auth';

function uniqueName(prefix: string) {
  return `${prefix} ${Date.now()}`;
}

test('org-enheter UI: create, rename (slug visible), delete', async ({ page }) => {
  await loginAsSuperuser(page);
  // create tenant via dashboard
  await page.goto('/superuser/dashboard');
  await page.getByTestId('qa-create-tenant').click();
  const dlg = page.getByRole('dialog', { name: /Skapa tenant/i });
  await expect(dlg).toBeVisible();
  const tenantName = uniqueName('OrgUnits UI Tenant');
  await dlg.getByLabel(/Namn/i).fill(tenantName);
  await dlg.getByRole('button', { name: /Skapa|Spara|Create/i }).click();
  await expect(dlg).toBeHidden();

  // Navigate to the created tenant detail via events list link
  await page.locator('#events-list a.link').first().click();
  await expect(page.getByTestId('tenant-title')).toBeVisible();

  // Create org unit via UI modal (button lives in Overview tab which is default active)
  await page.getByRole('button', { name: /Lägg till org-enhet/i }).click();
  const orgDlg = page.getByRole('dialog', { name: /Ny org-enhet|Redigera org-enhet/i });
  await expect(orgDlg).toBeVisible();

  const unitName = uniqueName('Kök Alpha');
  await orgDlg.getByLabel(/Namn/i).fill(unitName);
  await orgDlg.getByLabel(/Typ/i).selectOption('kitchen');
  await orgDlg.getByRole('button', { name: /Spara|Save/i }).click();
  await expect(orgDlg).toBeHidden();

  // Switch to Org tab and verify item with slug is visible
  await page.getByTestId('tab-org').click();
  const list = page.getByTestId('org-list');
  await expect(list).toBeVisible();
  const row = list.locator('li').filter({ hasText: unitName }).first();
  await expect(row).toBeVisible();
  // Slug is rendered inside a <code.org-slug>
  const slugEl = row.locator('code.org-slug');
  await expect(slugEl).toBeVisible();
  const slugBefore = (await slugEl.textContent())?.trim();
  expect(slugBefore && slugBefore.length > 0).toBeTruthy();

  // Rename via UI (uses the same modal)
  await row.getByTestId('org-edit').click();
  const editDlg = page.getByRole('dialog', { name: /Redigera org-enhet/i });
  await expect(editDlg).toBeVisible();
  const newName = unitName + ' Beta';
  await editDlg.getByLabel(/Namn/i).fill(newName);
  await editDlg.getByRole('button', { name: /Spara|Save/i }).click();
  await expect(editDlg).toBeHidden();

  const row2 = list.locator('li').filter({ hasText: newName }).first();
  await expect(row2).toBeVisible();
  const slugAfter = (await row2.locator('code.org-slug').textContent())?.trim();
  expect(slugAfter && slugAfter.length > 0).toBeTruthy();
  expect(slugAfter).not.toEqual(slugBefore);

  // Delete via UI
  // Confirm dialog appears; Playwright auto-accepts via page.once('dialog', ...)
  page.once('dialog', d => d.accept());
  await row2.getByTestId('org-delete').click();
  await expect(list.locator('li').filter({ hasText: newName })).toHaveCount(0);
});
