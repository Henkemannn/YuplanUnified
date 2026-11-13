import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

describe('Kitchen Menu Overview A4 print contract', () => {
  it('keeps the screen grid and print table as separate structures', () => {
    const template = readStatic('../../templates/ui/kitchen_menu_overview.html');
    const css = readStatic('../../static/css/kitchen_menu_overview.css');

    expect(template).toContain('kitchen-menu__screen-grid');
    expect(template).toContain('class="kitchen-menu__print-only"');
    expect(template).toContain('class="kitchen-menu__print-list"');
    expect(template).toContain('class="kitchen-menu__print-row"');
    expect(template).toContain('class="kitchen-menu__print-cell kitchen-menu__print-cell--empty"');
    expect(template).toContain('{% elif loop.last %}');
    expect(template).toContain('loop.index0 % 2 == 0');
    expect(css).toMatch(/\.kitchen-menu__print-only\s*\{\s*display: none;/);
  });

  it('uses four non-table print rows with isolated block-flow cards', () => {
    const printCss = readStatic('../../static/css/yuplan_print.css');

    expect(printCss).toContain('.kitchen-menu .kitchen-menu__screen-grid');
    expect(printCss).toContain('.kitchen-menu .kitchen-menu__print-only');
    expect(printCss).toContain('.kitchen-menu .kitchen-menu__print-list');
    expect(printCss).toContain('.kitchen-menu .kitchen-menu__print-row');
    expect(printCss).toContain('display: inline-block !important;');
    expect(printCss).toContain('min-height: 0 !important;');
    expect(printCss).toContain('transform: none !important;');
    expect(printCss).toContain('-webkit-column-break-inside: avoid !important;');
    expect(printCss).toContain('page-break-inside: avoid !important;');
    expect(printCss).not.toContain('.kitchen-menu .kitchen-menu__print-table');
    expect(printCss).toContain('.kitchen-menu .kitchen-menu__print-card');
    expect(printCss).toContain('display: block !important;');
    expect(printCss).toContain('box-sizing: border-box !important;');
    expect(printCss).toContain('font-size: 10.5pt !important;');
    expect(printCss).toContain('font-size: 9.5pt !important;');
    expect(printCss).not.toContain('min-height: 232mm !important;');
  });
});
