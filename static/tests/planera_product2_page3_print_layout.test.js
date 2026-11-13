import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

describe('Planera Page3 A4 print contract', () => {
  it('fits the Normalkost matrix to the printable page width', () => {
    const css = readStatic('../../static/css/planera_product2_page3.css');

    expect(css).toContain('.yp-planera-page3-table--matrix {');
    expect(css).toContain('table-layout: fixed;');
    expect(css).toContain('width: 8rem;');
    expect(css).toContain('min-width: 0;');
    expect(css).toContain('overflow-wrap: anywhere;');
  });

  it('keeps long Normalkost matrices compact across A4 pages', () => {
    const css = readStatic('../../static/css/planera_product2_page3.css');

    expect(css).toContain('display: table-header-group;');
    expect(css).toContain('display: table-row-group;');
    expect(css).not.toContain('display: table-footer-group;');
    expect(css).toContain('break-inside: avoid;');
    expect(css).toContain('page-break-inside: avoid;');
    expect(css).toContain('padding: 0.28rem 0.4rem;');
    expect(css).toContain('font-size: 0.82rem;');
    expect(css).toContain('font-size: 0.74rem;');
    expect(css).toContain('line-height: 1.2;');
  });

  it('keeps host diagnostics out of print while retaining them in screen CSS', () => {
    const printCss = readStatic('../../static/css/yuplan_print.css');

    expect(printCss).toContain('#host-mismatch-banner');
    expect(printCss).toContain('display: none !important;');
  });

  it('uses one readable Normalkost print heading and compact print hierarchy', () => {
    const css = readStatic('../../static/css/planera_product2_page3.css');
    const template = readStatic('../../templates/ui/kitchen_product_planera_page3.html');

    expect(template).toContain('{% if vm.view == "normal" %}Normalkost{%');
    expect(css).toMatch(/\.yp-planera-page3-section__title\s*\{\s*display: none !important;/);
    expect(css).toContain('letter-spacing: 0;');
    expect(css).toContain('text-transform: none;');
    expect(css).toContain('font-variant-numeric: tabular-nums;');
    expect(css).toContain('border-left: 2px solid #b7c1c9;');
  });
});
