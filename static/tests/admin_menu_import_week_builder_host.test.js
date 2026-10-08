import { beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(`${code}\n//# sourceURL=${relativePath}`);
}

describe('AdminWeekBuilderHost adapter', () => {
  beforeEach(() => {
    delete window.YuplanModalHost;
    delete window.AdminWeekBuilderHost;
    document.body.innerHTML = '';
    document.body.className = '';
  });

  it('delegates lifecycle to YuplanModalHost and preserves the public API', () => {
    document.body.innerHTML = `
      <button id="trigger" type="button">Open</button>
      <div class="menu-week__grid"></div>
      <section class="yp-modal-host" hidden aria-hidden="true" data-modal-host-mode="child-owned-card" data-admin-week-builder-host>
        <div class="yp-modal-host__backdrop" data-admin-week-builder-host-close></div>
        <div class="yp-modal-host__panel" tabindex="-1" data-admin-week-builder-host-panel>
          <iframe class="yp-modal-host__frame" title="Menyimportredigerare" src="about:blank" data-admin-week-builder-host-frame></iframe>
        </div>
      </section>
    `;

    loadScript('../../static/js/modal_host.js');
    loadScript('../../static/ui/admin_menu_import_week_builder_host.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));

    expect(window.AdminWeekBuilderHost).toBeTruthy();
    expect(typeof window.AdminWeekBuilderHost.open).toBe('function');
    expect(typeof window.AdminWeekBuilderHost.openComposition).toBe('function');
    expect(typeof window.AdminWeekBuilderHost.close).toBe('function');

    const trigger = document.getElementById('trigger');
    window.AdminWeekBuilderHost.openComposition('comp_123', trigger);

    const root = document.querySelector('[data-admin-week-builder-host]');
    const frame = document.querySelector('[data-admin-week-builder-host-frame]');
    expect(root.hidden).toBe(false);
    expect(document.body.classList.contains('yp-modal-open')).toBe(true);
    expect(frame.getAttribute('src')).toContain('/builder-editor-host?composition_id=comp_123');

    window.dispatchEvent(new MessageEvent('message', {
      data: {
        type: 'builder-host-close',
        detail: {
          kind: 'composition',
          host_target_id: 'comp_123',
        },
      },
      origin: window.location.origin,
      source: frame.contentWindow,
    }));

    expect(root.hidden).toBe(true);
    expect(document.body.classList.contains('yp-modal-open')).toBe(false);

    window.AdminWeekBuilderHost.open('/builder-composition-picker?site_id=1', trigger);
    expect(frame.getAttribute('src')).toContain('/builder-composition-picker?site_id=1');
  });

  it('closes on picker close messages without changing children', () => {
    document.body.innerHTML = `
      <button id="trigger" type="button">Open</button>
      <div class="menu-week__grid"></div>
      <section class="yp-modal-host" hidden aria-hidden="true" data-modal-host-mode="child-owned-card" data-admin-week-builder-host>
        <div class="yp-modal-host__backdrop" data-admin-week-builder-host-close></div>
        <div class="yp-modal-host__panel" tabindex="-1" data-admin-week-builder-host-panel>
          <iframe class="yp-modal-host__frame" title="Menyimportredigerare" src="about:blank" data-admin-week-builder-host-frame></iframe>
        </div>
      </section>
    `;

    loadScript('../../static/js/modal_host.js');
    loadScript('../../static/ui/admin_menu_import_week_builder_host.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));

    const trigger = document.getElementById('trigger');
    window.AdminWeekBuilderHost.open('/builder-composition-picker', trigger);

    const root = document.querySelector('[data-admin-week-builder-host]');
    const frame = document.querySelector('[data-admin-week-builder-host-frame]');

    window.dispatchEvent(new MessageEvent('message', {
      data: { type: 'menu-picker-close' },
      origin: window.location.origin,
      source: frame.contentWindow,
    }));

    expect(root.hidden).toBe(true);
    expect(document.body.classList.contains('yp-modal-open')).toBe(false);
    expect(window.AdminWeekBuilderHost).toBeTruthy();
  });
});
