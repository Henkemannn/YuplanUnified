import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

describe('Department Portal week scroll contract', () => {
  it('keeps all days in the normal document flow', () => {
    const css = readStatic('../../static/css/portal_department_week.css');
    const weekRule = css.match(
      /#portal-week-scroll\.portal-week-grid \{[\s\S]*?\n  \}/,
    )?.[0] || '';

    expect(weekRule).toContain('padding: 0;');
    expect(weekRule).toContain('border: 0;');
    expect(weekRule).toContain('background: transparent;');
    expect(weekRule).not.toContain('max-height:');
    expect(weekRule).not.toContain('overflow:');

    expect(css).not.toContain('max-height: clamp(500px, calc(100dvh - 11rem), 780px);');
    expect(css).not.toContain('max-height: clamp(470px, calc(100dvh - 10.5rem), 820px);');
    expect(css).not.toContain('scrollbar-width: none;');
    expect(css).not.toContain('-ms-overflow-style: none;');
    expect(css).not.toContain('::-webkit-scrollbar');
    expect(css).not.toContain('#portal-week-scroll[data-scroll-owner]::before');
    expect(css).not.toContain('#portal-week-scroll[data-scroll-owner]::after');
  });
});
