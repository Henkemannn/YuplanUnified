import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

describe('App Shell responsive topbar contract', () => {
  it('reserves the same responsive height used by the fixed topbar and body offset', () => {
    const css = readStatic('../../static/css/app_shell.css');

    expect(css).toContain('--topbar-offset: calc(var(--topbar-height) + var(--safe-area-top));');
    expect(css).toContain('height: var(--topbar-offset);');
    expect(css).toContain('--topbar-height: 116px;');
    expect(css).toContain('--topbar-height: 148px;');
    expect(css).toContain('@media (min-width: 901px) and (max-width: 1366px)');
    expect(css).toContain('@media (min-width: 1367px)');
    expect(css).toContain('max-width: calc(100% - 180px);');
    expect(css).toContain('flex-wrap: nowrap;');
    expect(css).toContain('padding: calc(var(--topbar-offset) + 24px) 24px 32px;');
  });

  it('keeps wrapped badges readable and preserves the safe-area inset on mobile', () => {
    const css = readStatic('../../static/css/app_shell.css');

    expect(css).toContain('flex-wrap: wrap;');
    expect(css).toContain('white-space: normal;');
    expect(css).toContain('line-height: 1.25;');
    expect(css).toContain('padding: var(--safe-area-top) 16px 0;');
    expect(css).toContain('max-width: calc(100% - 120px);');
  });
});
