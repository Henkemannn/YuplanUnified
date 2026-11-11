import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

describe('Kitchen Weekview tablet layout contract', () => {
  const template = readStatic('../../templates/ui/_partials/week_grid.html');
  const kitchenTemplate = readStatic('../../templates/ui/kitchen_week_v3.html');
  const sharedTemplate = readStatic('../../templates/ui/unified_weekview_all.html');
  const css = readStatic('../../static/css/kitchen_week_v3.css');

  it('keeps the K3 table inside its own horizontal scroll region', () => {
    expect(template).toContain(
      '<div class="kw-grid-scroll" role="region"',
    );
    expect(template).toContain('<table class="grid-table kw-grid"');
    expect(template).toContain('<col class="kw-label-col" />');
    expect(template).toContain('<col class="kw-meal-col" />');
    expect(css).toContain('.kitchen-week .kw-grid-scroll');
    expect(css).toContain('overflow-x: auto;');
    expect(css).toContain('overscroll-behavior-x: contain;');
  });

  it('keeps the shared readonly weekview on the same scroll structure', () => {
    expect(kitchenTemplate).toContain('{% include "ui/_partials/week_grid.html" %}');
    expect(sharedTemplate).toContain('{% set interactive = false %}');
    expect(sharedTemplate).toContain('{% include "ui/_partials/week_grid.html" %}');
    expect(sharedTemplate).toContain('class="app-page kitchen-week"');
    expect(template).toContain('data-readonly="1"');
  });

  it('keeps every first-column cell as a sticky table cell', () => {
    expect(template).toContain('<td class="diet-name boende-label"><span class="diet-name__content">');
    expect(template).toContain('<td class="diet-name"><span class="diet-name__content">');
    expect(css).toContain('.kitchen-week .grid-table th:first-child');
    expect(css).toContain('.kitchen-week .grid-table td.diet-name');
    expect(css).toContain('display: table-cell;');
    expect(css).toContain('.kitchen-week .diet-name__content');
    expect(css).not.toContain('.kitchen-week .diet-name {\n  display: flex;');
  });

  it('reserves readable meal columns and touch-sized completion buttons', () => {
    expect(css).toContain('--kw-label-col-min: 170px;');
    expect(css).toContain('--kw-label-col-min-portrait: 170px;');
    expect(css).toContain('--kw-meal-col-min: 60px;');
    expect(css).toContain('width: max(100%, calc(var(--kw-label-col-width) + (var(--kw-meal-col-min) * 14)));');
    expect(css).toContain('.kitchen-week .kw-grid .kw-meal-col');
    expect(css).toContain('width: var(--kw-meal-col-min);');
    expect(css).toContain('min-width: calc(var(--kw-label-col-width) + (var(--kw-meal-col-min) * 14));');
    expect(css).toContain('min-height: 44px;');
    expect(css).toContain('width: 44px;');
    expect(css).toContain('min-width: 44px;');
  });

  it('preserves the print layout without the tablet minimum width', () => {
    expect(css).toContain('@media print');
    expect(css).toContain('overflow: visible !important;');
    expect(css).toContain('min-width: 0 !important;');
    expect(css).toContain('.kitchen-week .grid-table th');
  });
});
