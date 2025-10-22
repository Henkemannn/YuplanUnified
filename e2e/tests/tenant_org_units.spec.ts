import { test, expect, Page } from '@playwright/test';

const BASE = process.env.E2E_BASE_URL || 'http://127.0.0.1:5000';

async function login(page: Page) {
  await page.goto(BASE + '/ui/login', { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="email"]', process.env.SUPERUSER_EMAIL || process.env.E2E_SUPERUSER_EMAIL || 'admin@example.com');
  await page.fill('input[name="password"]', process.env.SUPERUSER_PASSWORD || process.env.E2E_SUPERUSER_PASSWORD || 'Passw0rd!');
  await page.click('button[type="submit"]');
  try {
    await page.waitForURL(/\/(superuser\/dashboard|workspace)(?:$|[?#])/, { timeout: 8000 });
  } catch {
    await page.goto(BASE + '/superuser/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
  }
}

function uniqueName(prefix: string) {
  const t = new Date().toISOString().replace(/[:.TZ-]/g, '').slice(0, 14);
  return `${prefix} ${t}`;
}

test.describe('Tenant org-enheter', () => {
  test('create org unit via modal and verify it appears in list', async ({ page }) => {
    await login(page);
    await page.goto(BASE + '/superuser/dashboard');

    // Create a new tenant via dashboard modal
    await page.getByTestId('qa-create-tenant').click();
    const dlg = page.getByRole('dialog', { name: /Skapa tenant/i });
    await expect(dlg).toBeVisible();

    const tenantName = uniqueName('OrgUnits Tenant');
    await dlg.getByLabel(/Namn/i).fill(tenantName);
    // Slug auto-fills; proceed to create
    await dlg.getByRole('button', { name: /Skapa|Spara|Create/i }).click();
    await expect(dlg).toBeHidden();

    // Click the latest event "Öppna" link to navigate to tenant page
    const firstEvent = page.getByTestId('event-item').first();
    const openLink = firstEvent.getByRole('link', { name: /Öppna/i });
    await openLink.click();

    // On tenant page
    const title = page.getByTestId('tenant-title');
    await expect(title).toBeVisible();

    // Open the Org-enheter tab (this triggers initial load)
    await page.getByTestId('tab-org').click();
    const list = page.locator('#org-list');
    await expect(list).toBeVisible();

    // Open the org unit modal from overview button
    await page.getByRole('button', { name: /Lägg till org-enhet/i }).click();
    const orgDlg = page.getByRole('dialog', { name: /Ny org-enhet/i });
    await expect(orgDlg).toBeVisible();

    const unitName = uniqueName('Kök Alpha');
    await orgDlg.getByLabel(/Namn/i).fill(unitName);
    await orgDlg.getByLabel(/Typ/i).selectOption('kitchen');
    await orgDlg.getByRole('button', { name: /Spara|Save/i }).click();
    await expect(orgDlg).toBeHidden();

    // The list should update; assert the item appears
    // Ensure the org tab is visible (if user stayed on Overview)
    await page.getByTestId('tab-org').click();
    const lastItem = list.locator('li').last();
    await expect(lastItem).toContainText(/Kök Alpha/);

    // Optional: focus moved to the new item
    await expect(lastItem).toBeFocused({ timeout: 2000 }).catch(() => {});
  });
});
