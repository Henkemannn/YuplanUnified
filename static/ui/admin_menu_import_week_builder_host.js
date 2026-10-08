(function () {
  'use strict';

  function normalizeId(value) {
    return String(value || '').trim();
  }

  function init() {
    const root = document.querySelector('[data-admin-week-builder-host]') || null;
    const frame = document.querySelector('[data-admin-week-builder-host-frame]') || null;
    if (!root || !frame) {
      return;
    }

    if (!window.YuplanModalHost || typeof window.YuplanModalHost.create !== 'function') {
      throw new Error('YuplanModalHost is required before AdminWeekBuilderHost initialises.');
    }

    const openerRoot = document.querySelector('.menu-week__grid') || document;
    let activeCompositionId = '';
    const host = window.YuplanModalHost.create(root, {
      bodyClass: 'yp-modal-open',
      mode: 'child-owned-card',
      openClass: 'is-open',
      backdropSelector: '[data-admin-week-builder-host-close]',
      panelSelector: '[data-admin-week-builder-host-panel]',
      frameSelector: '[data-admin-week-builder-host-frame]',
      resetFrameSrc: 'about:blank',
      shouldCloseOnMessage(payload) {
        const messageType = String(payload && payload.type || '');
        if (messageType === 'menu-picker-close') {
          return true;
        }
        if (messageType !== 'builder-host-close') {
          return false;
        }
        const detail = payload && payload.detail ? payload.detail : {};
        return String(detail.kind || '') === 'composition' && String(detail.host_target_id || '') === activeCompositionId;
      },
    });

    function closeHost() {
      activeCompositionId = '';
      host.close();
    }

    function open(url, triggerElement, compositionId) {
      const path = String(url || '').trim();
      if (!path || !path.startsWith('/') || path.startsWith('//')) {
        return;
      }
      activeCompositionId = normalizeId(compositionId);
      host.open({
        src: path,
        trigger: triggerElement instanceof HTMLElement
          ? triggerElement
          : document.activeElement instanceof HTMLElement
            ? document.activeElement
            : null,
        mode: 'child-owned-card',
        resetFrameSrc: 'about:blank',
      });
    }

    function openComposition(compositionId, triggerElement) {
      const resolvedCompositionId = normalizeId(compositionId);
      if (!resolvedCompositionId) {
        return;
      }
      open(
        '/builder-editor-host?composition_id=' + encodeURIComponent(resolvedCompositionId),
        triggerElement,
        resolvedCompositionId,
      );
    }

    globalThis.AdminWeekBuilderHost = {
      open,
      openComposition,
      close: closeHost,
    };

    openerRoot.addEventListener('click', (event) => {
      const button = event.target instanceof HTMLElement ? event.target.closest('[data-admin-week-builder-open]') : null;
      if (!button) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      openComposition(button.dataset.builderCompositionId || '', button);
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();
