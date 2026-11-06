import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

describe('Department Portal week theme contract', () => {
  it('uses Yuplan surface, text, border, muted, and accent tokens', () => {
    const portalCss = readStatic('../../static/css/portal_department_week.css');
    const appShellCss = readStatic('../../static/css/app_shell.css');

    expect(portalCss).toContain('background: var(--surface);');
    expect(portalCss).toContain('background: var(--surface-2);');
    expect(portalCss).toContain('color: var(--text);');
    expect(portalCss).toContain('color: var(--muted);');
    expect(portalCss).toContain('border: 1px solid var(--border);');
    expect(portalCss).toContain('border-color: var(--accent);');
    expect(portalCss).toContain('background: var(--accent);');

    expect(portalCss).not.toContain('#ffffff');
    expect(portalCss).not.toContain('#0f172a');
    expect(portalCss).not.toContain('#475569');
    expect(portalCss).not.toContain('rgba(255, 255, 255');

    expect(appShellCss).toContain('html.yp-theme-dark .app-shell');
    expect(appShellCss).toContain('--yp-shell-surface: #0b1f34;');
    expect(appShellCss).toContain('--yp-shell-text: #eaf7f8;');
    expect(appShellCss).toContain('--yp-shell-action: #02aec3;');
  });

  it('keeps touch targets and readable secondary information', () => {
    const portalCss = readStatic('../../static/css/portal_department_week.css');

    expect(portalCss).toContain('min-height: 2.75rem;');
    expect(portalCss).toContain('font-size: 0.85rem;');
    expect(portalCss).toContain('line-height: 1.35;');
  });
});
