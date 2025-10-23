import type { Page } from '@playwright/test';

export async function loginAsSuperuser(page: Page) {
  // Prefer E2E_* envs, fall back to SUPERUSER_* used by app, then to local defaults.
  const email = process.env.E2E_SUPERUSER_EMAIL || process.env.SUPERUSER_EMAIL || 'su@example.com';
  const password = process.env.E2E_SUPERUSER_PASSWORD || process.env.SUPERUSER_PASSWORD || 'changeme';
  await page.goto('/ui/login');
  await page.getByLabel(/E-post/i).fill(email);
  await page.getByLabel(/Lösenord/i).fill(password);
  await page.getByRole('button', { name: /Logga in|Login/i }).click();
  await page.waitForURL(/\/(superuser\/dashboard|workspace)/);
}
