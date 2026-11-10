import fs from 'node:fs';
import path from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(code + `\n//# sourceURL=${relativePath}`);
}

function dispatchReady() {
  document.dispatchEvent(new Event('DOMContentLoaded'));
}

describe('family print selection', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    window.history.replaceState({}, '', '/ui/test?view=addons');
    window.print = vi.fn();
  });

  it('filters only selected Page3 families and keeps selection after print', () => {
    document.body.innerHTML = `
      <main id="yp-product-app">
        <button data-page3-print></button>
        <section data-page3-panel="addons">
          <section data-page3-addon-family="family-0">
            <button data-page3-addon-family-toggle="family-0" data-page3-addon-family-name="MOS" aria-pressed="true"></button>
          </section>
          <section data-page3-addon-family="family-1">
            <button data-page3-addon-family-toggle="family-1" data-page3-addon-family-name="PASTA" aria-pressed="true"></button>
          </section>
        </section>
      </main>
    `;
    loadScript('../js/planera_product2_page3.js');
    dispatchReady();

    const toggles = [...document.querySelectorAll('[data-page3-addon-family-toggle]')];
    toggles[1].click();
    expect(toggles[1].getAttribute('aria-pressed')).toBe('false');

    document.querySelector('[data-page3-print]').click();

    expect(window.print).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[data-page3-addon-family="family-0"]').classList.contains('is-print-inactive')).toBe(false);
    expect(document.querySelector('[data-page3-addon-family="family-1"]').classList.contains('is-print-inactive')).toBe(true);

    window.dispatchEvent(new Event('afterprint'));
    expect(toggles[1].getAttribute('aria-pressed')).toBe('false');
  });

  it('does not print when all Page3 families are unselected', () => {
    document.body.innerHTML = `
      <main id="yp-product-app">
        <button data-page3-print></button>
        <p data-page3-print-selection-feedback hidden></p>
        <section data-page3-panel="addons">
          <section data-page3-addon-family="family-0">
            <button data-page3-addon-family-toggle="family-0" aria-pressed="true"></button>
          </section>
        </section>
      </main>
    `;
    loadScript('../js/planera_product2_page3.js');
    dispatchReady();

    document.querySelector('[data-page3-addon-family-toggle]').click();
    document.querySelector('[data-page3-print]').click();

    expect(window.print).not.toHaveBeenCalled();
    expect(document.querySelector('[data-page3-print-selection-feedback]').textContent).toContain('Välj minst en familj');
  });

  it('uses the same selection behavior for production list addons', () => {
    document.body.innerHTML = `
      <main data-production-lists-addons-root>
        <button data-production-lists-print-all></button>
        <p data-production-lists-print-feedback hidden></p>
        <section data-family-key="family-0">
          <button data-production-lists-family-toggle="family-0" data-family-name="MOS" aria-pressed="true"></button>
        </section>
        <section data-family-key="family-1">
          <button data-production-lists-family-toggle="family-1" data-family-name="PASTA" aria-pressed="true"></button>
        </section>
      </main>
    `;
    loadScript('../js/production_lists_addons.js');
    dispatchReady();

    const toggle = document.querySelector('[data-production-lists-family-toggle="family-1"]');
    toggle.click();
    document.querySelector('[data-production-lists-print-all]').click();

    expect(window.print).toHaveBeenCalledTimes(1);
    expect(document.querySelector('[data-family-key="family-0"]').classList.contains('is-print-inactive')).toBe(false);
    expect(document.querySelector('[data-family-key="family-1"]').classList.contains('is-print-inactive')).toBe(true);
    expect(toggle.getAttribute('aria-pressed')).toBe('false');
  });

  it('keeps the Page3 family icon markup and CSS in parity with production lists', () => {
    const page3Template = fs.readFileSync(path.resolve('templates/ui/kitchen_product_planera_page3.html'), 'utf8');
    const productionTemplate = fs.readFileSync(path.resolve('templates/ui/production_lists_addons.html'), 'utf8');
    const page3Path = page3Template.match(/data-page3-addon-family-toggle[\s\S]*?<path d="([^"]+)"/)?.[1];
    const productionPath = productionTemplate.match(/data-production-lists-family-toggle[\s\S]*?<path d="([^"]+)"/)?.[1];
    const page3Css = fs.readFileSync(path.resolve('static/css/planera_product2_page3.css'), 'utf8');

    expect(page3Path).toBe(productionPath);
    expect(page3Css).toContain('.yp-planera-page3-addons-family-toggle svg');
    expect(page3Css).toMatch(/\.yp-planera-page3-addons-family-toggle svg\s*\{[^}]*width:\s*20px;[^}]*height:\s*20px;[^}]*fill:\s*none;[^}]*stroke:\s*currentColor;[^}]*stroke-linecap:\s*round;[^}]*stroke-linejoin:\s*round;[^}]*stroke-width:\s*1\.8;/s);
  });
});
