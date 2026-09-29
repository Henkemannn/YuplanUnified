(function () {
  'use strict';

  function normalizeId(value) {
    return String(value || '').trim();
  }

  function init() {
    const root = document.querySelector('[data-admin-week-builder-host]') || null;
    const frame = document.querySelector('[data-admin-week-builder-host-frame]') || null;
    const openerRoot = document.querySelector('.menu-week__grid') || document;
    if (!root || !frame) {
      return;
    }

    let activeCompositionId = '';
    let lastActiveElement = null;

    function openHost(compositionId, triggerElement) {
      const resolvedCompositionId = normalizeId(compositionId);
      if (!resolvedCompositionId) {
        return;
      }
      lastActiveElement = triggerElement instanceof HTMLElement ? triggerElement : document.activeElement instanceof HTMLElement ? document.activeElement : null;
      activeCompositionId = resolvedCompositionId;
      root.hidden = false;
      root.setAttribute('aria-hidden', 'false');
      document.body.classList.add('menu-editor-builder-host-open');
      frame.src = '/builder-editor-host?composition_id=' + encodeURIComponent(resolvedCompositionId);
    }

    function closeHost() {
      if (root.hidden) {
        return;
      }
      root.hidden = true;
      root.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('menu-editor-builder-host-open');
      activeCompositionId = '';
      frame.src = 'about:blank';
      if (lastActiveElement && typeof lastActiveElement.focus === 'function') {
        try {
          lastActiveElement.focus();
        } catch (error) {
          // Ignore focus failures in restricted browsers.
        }
      }
    }

    openerRoot.addEventListener('click', (event) => {
      const button = event.target instanceof HTMLElement ? event.target.closest('[data-admin-week-builder-open]') : null;
      if (!button) {
        return;
      }
      event.preventDefault();
      event.stopPropagation();
      openHost(button.dataset.builderCompositionId || '', button);
    });

    root.addEventListener('click', (event) => {
      const closeTarget = event.target instanceof HTMLElement ? event.target.closest('[data-admin-week-builder-host-close]') : null;
      if (!closeTarget) {
        return;
      }
      event.preventDefault();
      closeHost();
    });

    window.addEventListener('message', (event) => {
      if (!frame.contentWindow || event.origin !== window.location.origin || event.source !== frame.contentWindow) {
        return;
      }
      const payload = event.data || {};
      if (payload.type === 'builder-host-ready') {
        return;
      }
      if (payload.type !== 'builder-host-close') {
        return;
      }
      const detail = payload.detail || {};
      if (String(detail.kind || '') !== 'composition') {
        return;
      }
      if (String(detail.host_target_id || '') !== activeCompositionId) {
        return;
      }
      closeHost();
    });
  }

  document.addEventListener('DOMContentLoaded', init);
})();