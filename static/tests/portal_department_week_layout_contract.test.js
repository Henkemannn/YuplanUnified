import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

describe('Department Portal week layout contract', () => {
  it('uses equal desktop lunch columns and full-width secondary rows', () => {
    const css = readStatic('../../static/css/portal_department_week.css');
    const contentRule = css.match(
      /\.portal-day-row__content \{[\s\S]*?\n  \}/,
    )?.[0] || '';

    expect(contentRule).toContain('grid-template-columns: repeat(2, minmax(0, 1fr));');
    expect(css).toMatch(/\.portal-day-row__secondary\s*\{\s*grid-column:\s*1 \/ -1;/);
    expect(css).toMatch(/\.portal-choice-row--readonly\s*\{\s*grid-column:\s*auto;/);
    expect(css).toMatch(/\.portal-day-row__info-row\s*\{\s*grid-column:\s*1 \/ -1;/);
  });

  it('stacks lunch content at tablet and mobile widths', () => {
    const css = readStatic('../../static/css/portal_department_week.css');
    const tabletRule = css.match(
      /@media \(max-width: 1024px\) \{[\s\S]*?\.portal-day-row__content \{[\s\S]*?\n    \}/,
    )?.[0] || '';

    expect(tabletRule).toContain('grid-template-columns: 1fr;');
    expect(css).toContain('overflow-wrap: anywhere;');
    expect(css).toContain('min-height: 2.75rem;');
  });

  it('separates secondary meal information without adding another card layer', () => {
    const css = readStatic('../../static/css/portal_department_week.css');

    expect(css).toContain('border-top: 1px solid var(--border);');
    expect(css).toContain('flex: 1 1 16rem;');
    expect(css).toContain('flex: 0 0 1px;');
    expect(css).toContain('background: var(--border);');
    expect(css).toContain('font-size: 0;');
    expect(css).toMatch(/\.portal-day-row__secondary-separator\s*\{\s*display:\s*none;/);
  });

  it('places the single-option note in the second lunch column', () => {
    const css = readStatic('../../static/css/portal_department_week.css');
    const template = readStatic('../../templates/portal_department_week.html');

    expect(template).toContain(
      'class="portal-choice-row portal-day-row__info-row portal-day-row__single-option-note"',
    );
    expect(template).not.toContain('aria-hidden="true">Endast ett lunchalternativ idag');
    expect(css).toMatch(/\.portal-day-row__single-option-note\s*\{\s*grid-column:\s*auto;/);
    expect(css).toMatch(/\.portal-day-row__single-option-note\s*\{[\s\S]*grid-template-columns:\s*minmax\(0, 1fr\);/);
    expect(css).toMatch(/\.portal-day-row__single-option-note\s*\{[\s\S]*white-space:\s*nowrap;/);
    expect(css).toMatch(/\.portal-day-row__single-option-note\s*\{[\s\S]*overflow-wrap:\s*anywhere;/);
    expect(css).toMatch(/@media \(max-width: 720px\) \{[\s\S]*\.portal-day-row__single-option-note\s*\{[\s\S]*white-space:\s*normal;/);
  });
});
