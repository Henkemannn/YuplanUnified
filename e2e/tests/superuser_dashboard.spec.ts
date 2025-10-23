import { test, expect, Page } from '@playwright/test';

// Assumes a seeded superuser and that server is running at BASE_URL (configure via env or default)
const BASE = process.env.E2E_BASE_URL || 'http://localhost:5000';

async function login(page: Page){
  await page.goto(BASE + '/ui/login', { waitUntil: 'domcontentloaded' });
  await page.fill('input[name="email"]', process.env.SUPERUSER_EMAIL || 'admin@example.com');
  await page.fill('input[name="password"]', process.env.SUPERUSER_PASSWORD || 'Passw0rd!');
  await page.click('button[type="submit"]');
  try {
    await page.waitForURL(/\/(superuser\/dashboard|workspace)(?:$|[?#])/, { timeout: 8000 });
  } catch {
    // Fallback: navigate to dashboard explicitly (works if auth succeeded; otherwise server will redirect back)
    await page.goto(BASE + '/superuser/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
  }
}

test.describe('Superuser dashboard', () => {
  test('KPI values load and events empty state when no events', async ({ page }) => {
    await login(page);
    await page.goto(BASE + '/superuser/dashboard');
    // Wait for dashboard main and KPI cards to render
    await expect(page.getByTestId('kpi-tenants')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('kpi-modules')).toBeVisible({ timeout: 5000 });
    await expect(page.getByTestId('kpi-flags')).toBeVisible({ timeout: 5000 });
    // KPI values should change from em-dash to a number within timeout
    const kpiSelectors = ['[data-testid="kpi-tenants"] [data-kpi-value]','[data-testid="kpi-modules"] [data-kpi-value]','[data-testid="kpi-flags"] [data-kpi-value]'];
    for (const sel of kpiSelectors){
      await expect(page.locator(sel)).not.toHaveText('—', { timeout: 10000 });
    }
    // If there are zero events, empty state visible OR list has items
    const emptyVisible = await page.locator('[data-testid="events-empty"]:not([hidden])').count();
    const itemsCount = await page.locator('[data-testid="event-item"]').count();
    expect(emptyVisible === 1 || itemsCount > 0).toBeTruthy();
  });
});
