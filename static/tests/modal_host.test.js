import { beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(`${code}\n//# sourceURL=${relativePath}`);
}

describe('YuplanModalHost', () => {
  beforeEach(() => {
    delete window.YuplanModalHost;
    document.body.innerHTML = '';
    document.body.className = '';
  });

  it('opens and closes a child-owned-card host with focus restore and iframe reset', () => {
    document.body.innerHTML = `
      <button id="trigger" type="button">Open</button>
      <section class="yp-modal-host" hidden aria-hidden="true" data-modal-host-mode="child-owned-card">
        <div class="yp-modal-host__backdrop" data-backdrop></div>
        <div class="yp-modal-host__panel" tabindex="-1">
          <iframe class="yp-modal-host__frame" title="Frame"></iframe>
        </div>
      </section>
    `;

    loadScript('../../static/js/modal_host.js');

    const root = document.querySelector('.yp-modal-host');
    const trigger = document.getElementById('trigger');
    const host = window.YuplanModalHost.create(root, {
      backdropSelector: '[data-backdrop]',
      panelSelector: '.yp-modal-host__panel',
      frameSelector: '.yp-modal-host__frame',
      bodyClass: 'yp-modal-open',
      mode: 'child-owned-card',
      resetFrameSrc: 'about:blank',
      shouldCloseOnMessage(payload) {
        return payload && payload.type === 'close-me';
      },
    });

    trigger.focus();
    host.open({
      src: '/builder-editor-host?composition_id=comp_123',
      trigger,
      mode: 'child-owned-card',
    });

    const frame = root.querySelector('iframe');
    expect(root.hidden).toBe(false);
    expect(root.getAttribute('aria-hidden')).toBe('false');
    expect(document.body.classList.contains('yp-modal-open')).toBe(true);
    expect(root.dataset.modalHostMode).toBe('child-owned-card');
    expect(frame.getAttribute('src')).toContain('/builder-editor-host?composition_id=comp_123');

    const backdrop = root.querySelector('[data-backdrop]');
    backdrop.dispatchEvent(new MouseEvent('click', { bubbles: true }));

    expect(root.hidden).toBe(true);
    expect(root.getAttribute('aria-hidden')).toBe('true');
    expect(document.body.classList.contains('yp-modal-open')).toBe(false);
    expect(frame.getAttribute('src')).toContain('about:blank');
    expect(document.activeElement).toBe(trigger);
  });

  it('closes on Escape and on same-origin postMessage', () => {
    document.body.innerHTML = `
      <button id="trigger" type="button">Open</button>
      <section class="yp-modal-host" hidden aria-hidden="true">
        <div class="yp-modal-host__backdrop"></div>
        <div class="yp-modal-host__panel" tabindex="-1">
          <iframe class="yp-modal-host__frame" title="Frame"></iframe>
        </div>
      </section>
    `;

    loadScript('../../static/js/modal_host.js');

    const root = document.querySelector('.yp-modal-host');
    const trigger = document.getElementById('trigger');
    const host = window.YuplanModalHost.create(root, {
      backdropSelector: '.yp-modal-host__backdrop',
      panelSelector: '.yp-modal-host__panel',
      frameSelector: '.yp-modal-host__frame',
      bodyClass: 'yp-modal-open',
      resetFrameSrc: 'about:blank',
      closeMessageTypes: ['menu-picker-close'],
      shouldCloseOnMessage(payload) {
        return payload && payload.type === 'builder-host-close';
      },
    });

    host.open({
      src: '/builder-composition-picker',
      trigger,
    });

    expect(root.hidden).toBe(false);

    window.dispatchEvent(new MessageEvent('message', {
      data: { type: 'builder-host-close' },
      origin: window.location.origin,
      source: root.querySelector('iframe').contentWindow,
    }));

    expect(root.hidden).toBe(true);
    expect(document.body.classList.contains('yp-modal-open')).toBe(false);

    host.open({
      src: '/builder-composition-picker',
      trigger,
    });
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(root.hidden).toBe(true);
  });
});
