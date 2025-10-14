import { test, expect, Page, BrowserContext } from '@playwright/test';

const base = process.env.E2E_BASE_URL || 'http://localhost:5000';

test.describe('Superuser Login UX', () => {
  test('shows Problem Details alert on invalid login and returns focus to field', async ({ page }) => {
    await page.goto(`${base}/ui/login`);
    // Ensure inline_ui is enabled in the running server for this to work
    const email = page.getByLabel('E-post');
    const password = page.getByLabel('Lösenord');
    await email.fill('nope@example.com');
    await password.fill('wrong');
    await page.getByRole('button', { name: 'Logga in' }).click();

    const alert = page.getByRole('alert');
    await expect(alert).toBeVisible();
    await expect(alert).toContainText(/Fel vid inloggning|invalid|ogiltiga/i);

    // After announcement, focus should return to the first invalid field
    // Give a small delay to allow the setTimeout in code
    await page.waitForTimeout(100);
    const active = await page.evaluate(() => document.activeElement?.id);
    expect(['email', 'password']).toContain(active);
  });

  test('theme persists via localStorage (yu_mode)', async ({ page }: { page: Page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('yu_mode', 'dark');
    });
    await page.goto(`${base}/ui/login`);
    const mode = await page.evaluate(() => document.documentElement.getAttribute('data-mode'));
    expect(mode).toBe('dark');
  });

  test('brand persists via localStorage (yu_brand)', async ({ page }: { page: Page }) => {
    await page.addInitScript(() => {
      localStorage.setItem('yu_brand', 'ocean');
    });
    await page.goto(`${base}/ui/login`);
    const brand = await page.evaluate(() => document.documentElement.getAttribute('data-brand'));
    expect(brand).toBe('ocean');
  });

  test('reduced-motion: alert does not animate', async ({ page, context }: { page: Page, context: BrowserContext }) => {
    // Emulate prefers-reduced-motion
    await context.addInitScript(() => {
      const mql = window.matchMedia;
      // Monkey-patch matchMedia for test; in Chromium this can be set via emulation in future
      // Here we override to return matches=true for the reduced motion media query
      // @ts-ignore
      window.matchMedia = (query: string) => {
        const mm = mql(query);
        if (query.includes('prefers-reduced-motion')) {
          return {
            ...mm,
            matches: true,
          } as MediaQueryList;
        }
        return mm;
      };
    });
    await page.goto(`${base}/ui/login`);
    await page.getByLabel('E-post').fill('x@y.z');
    await page.getByLabel('Lösenord').fill('nope');
    await page.getByRole('button', { name: 'Logga in' }).click();
    const alert = page.getByRole('alert');
    await expect(alert).toBeVisible();
    // Ensure no animation class lingering (CSS turns off animation durations in reduced motion)
  const hasAnimateClass = await alert.evaluate((el: Element) => el.classList.contains('alert--animate'));
    expect(hasAnimateClass).toBeFalsy();
  });

  test('redirects to workspace or superuser dashboard on success', async ({ page }: { page: Page }) => {
    test.skip(!process.env.SUPERUSER_EMAIL || !process.env.SUPERUSER_PASSWORD, 'Set SUPERUSER_EMAIL and SUPERUSER_PASSWORD in the app env to run this test.');
    await page.goto(`${base}/ui/login`);
    const email = page.getByLabel('E-post');
    const password = page.getByLabel('Lösenord');
    // These must match SUPERUSER_EMAIL/PASSWORD in the env of the running app
    await email.fill(process.env.SUPERUSER_EMAIL!);
    await password.fill(process.env.SUPERUSER_PASSWORD!);
    await page.getByRole('button', { name: 'Logga in' }).click();
    // Accept either normal workspace or superuser dashboard redirect
    await page.waitForURL(/\/(workspace|superuser\/dashboard)(?:$|[?#])/, { timeout: 10_000 });
    const url = page.url();
    if (/(\/superuser\/dashboard)(?:$|[?#])/.test(url)) {
      // Dashboard: expect KPI section or title to be present
      await expect(page.getByTestId('kpi-tenants')).toBeVisible({ timeout: 4000 });
    } else {
      // Workspace: expect notes/tasks content
      await expect(page.getByText(/Anteckningar|Tasks|Noteringar/i)).toBeVisible({ timeout: 4000 });
    }
  });
});
