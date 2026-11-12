import { describe, expect, it } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

describe('Kitchen Builder modal host geometry', () => {
  it('lets the backdrop receive clicks outside the embedded Builder card', () => {
    const css = readStatic('../../static/css/kitchen_menu_overview.css').replace(/\r\n/g, '\n');
    expect(css).toContain(
      '.yp-modal-host.kitchen-menu__builder-modal-host[data-admin-week-builder-host][data-modal-host-mode="child-owned-card"] {\n'
      + '  position: fixed;\n'
      + '  inset: 0;\n'
      + '  width: 100vw;',
    );
    expect(css).toContain(
      '.yp-modal-host.kitchen-menu__builder-modal-host[data-admin-week-builder-host][data-modal-host-mode="child-owned-card"] .yp-modal-host__panel {\n'
      + '  position: relative;\n'
      + '  inset: auto;\n'
      + '  width: min(1120px, calc(100vw - 32px));',
    );
    expect(css).toContain(
      '.yp-modal-host.kitchen-menu__builder-modal-host[data-admin-week-builder-host][data-modal-host-mode="child-owned-card"] .yp-modal-host__frame',
    );
    expect(css).toContain('  width: 100%;');
    expect(css).not.toContain(
      '.yp-modal-host.kitchen-menu__builder-modal-host[data-admin-week-builder-host][data-modal-host-mode="child-owned-card"] .yp-modal-host__panel,\n'
      + '.yp-modal-host.kitchen-menu__builder-modal-host[data-admin-week-builder-host][data-modal-host-mode="child-owned-card"] .yp-modal-host__frame',
    );
    expect(css).not.toContain('clip-path:');
  });

  it('keeps the Kitchen host centered without changing shared modal CSS', () => {
    const css = readStatic('../../static/css/kitchen_menu_overview.css');

    expect(css).toContain('display: grid;');
    expect(css).toContain('place-items: center;');
    expect(css).not.toContain('transform:');
  });
});
