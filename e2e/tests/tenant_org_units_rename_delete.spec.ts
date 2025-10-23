import { test, expect } from '@playwright/test';
import { loginAsSuperuser } from './utils/auth';

// Creates a tenant, adds an org unit, renames it (slug updates), then deletes it
// Focuses on chromium for speed in local runs; CI will execute all projects via config

test('org unit rename updates slug and delete via API responds correctly', async ({ page }) => {
  await loginAsSuperuser(page);
  await page.goto('/superuser/dashboard');

  // Create tenant via modal
  await page.getByTestId('qa-create-tenant').click();
  const dlg = page.getByRole('dialog', { name: /Skapa tenant/i });
  const name = `E2E Kommun ${Date.now()}`;
  await dlg.getByLabel(/Namn/i).fill(name);
  await dlg.getByRole('button', { name: /Skapa|Spara|Create/i }).click();

  // Open the newly created tenant (from events list)
  const firstTenantLink = page.locator('#events-list a[href^="/tenants/"]').first();
  await firstTenantLink.waitFor({ state: 'visible' });
  const href = await firstTenantLink.getAttribute('href');
  if (!href) throw new Error('No tenant link found');
  await page.goto(href + '?tab=org');
  
    // Use API to create, rename, and delete the unit (same routes the UI uses)
    // Grab CSRF token from cookie
    const csrf = await page.evaluate(() => (document.cookie.split('; ').find(r=>r.startsWith('csrf_token='))||'').split('=')[1]||'');
    expect(csrf).toBeTruthy();
  
    // Create
    const createRes = await page.request.post(`/api/superuser/tenants/${href.match(/\/(\d+)$/)![1]}/org-units`, {
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      data: { name: 'Kok Bravo', type: 'kitchen' }
    });
    expect(createRes.status()).toBe(201);
    const created = await createRes.json();
    expect(created.slug).toBe('kok-bravo');
  
    const uid = created.id as number;
  
    // Rename (PATCH)
    const patchRes = await page.request.patch(`/api/superuser/tenants/${href.match(/\/(\d+)$/)![1]}/org-units/${uid}`, {
      headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
      data: { name: 'Kok Beta' }
    });
    expect(patchRes.status()).toBe(200);
    const updated = await patchRes.json();
    expect(updated.slug).toBe('kok-beta');
  
    // Delete
    const delRes = await page.request.delete(`/api/superuser/tenants/${href.match(/\/(\d+)$/)![1]}/org-units/${uid}`, {
      headers: { 'X-CSRF-Token': csrf },
    });
    expect(delRes.status()).toBe(204);
  
    // Verify empty list via GET
    const listRes = await page.request.get(`/api/superuser/tenants/${href.match(/\/(\d+)$/)![1]}/org-units`);
    expect(listRes.status()).toBe(200);
    const j = await listRes.json();
    expect((j.items||[]).length).toBe(0);

  // Note: UI list rendering is covered in other tests; here we verify API-level rename/delete correctness and slug behavior.
});
