(function () {
  'use strict';

  function normalizeKey(value) {
    return String(value || '').trim().toLowerCase();
  }

  function normalizeTrackList(values) {
    return Array.from(new Set((values || []).map(normalizeKey).filter(Boolean)));
  }

  function readStoredKeys(storageKey) {
    if (!storageKey || !window.localStorage) {
      return null;
    }
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed.map(normalizeKey).filter(Boolean) : null;
    } catch (error) {
      return null;
    }
  }

  function writeStoredKeys(storageKey, keys) {
    if (!storageKey || !window.localStorage) {
      return;
    }
    try {
      window.localStorage.setItem(storageKey, JSON.stringify(keys));
    } catch (error) {
      // Ignore storage failures in restricted browsers.
    }
  }

  function getFocusable(container) {
    return Array.from(
      container.querySelectorAll(
        'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
      )
    ).filter((element) => element.offsetParent !== null || element === document.activeElement);
  }

  function init() {
    const root = document.querySelector('[data-work-menu-root]');
    if (!root) {
      return;
    }

    const modal = root.querySelector('[data-work-menu-modal]');
    const modalPanel = modal ? modal.querySelector('.offshore-work-menu-modal__panel') : null;
    const modalTitle = root.querySelector('#offshoreWorkMenuModalTitle');
    const modalSummary = root.querySelector('[data-work-menu-modal-summary]');
    const modalPublished = root.querySelector('[data-work-menu-modal-published]');
    const modalEffective = root.querySelector('[data-work-menu-modal-effective]');
    const modalSource = root.querySelector('[data-work-menu-modal-source]');
    const modalBadges = root.querySelector('[data-work-menu-modal-badges]');
    const modalBridge = root.querySelector('[data-work-menu-builder-bridge]');
    const modalBridgeTitle = root.querySelector('[data-work-menu-builder-bridge-title]');
    const modalBridgeSummary = root.querySelector('[data-work-menu-builder-bridge-summary]');
    const modalBridgeComponents = root.querySelector('[data-work-menu-builder-bridge-components]');
    const modalBridgeLink = root.querySelector('[data-work-menu-builder-bridge-link]');
    const builderHost = root.querySelector('[data-work-menu-builder-host]');
    const builderHostFrame = root.querySelector('[data-work-menu-builder-host-frame]');
    const builderHostTitle = root.querySelector('[data-work-menu-builder-host-title]');
    const saveForm = root.querySelector('[data-work-menu-save-form]');
    const resetForm = root.querySelector('[data-work-menu-reset-form]');
    const decisionTypeField = root.querySelector('[data-work-menu-decision-type]');
    const builderField = root.querySelector('[data-work-menu-builder-select]');
    const freeTextField = root.querySelector('[data-work-menu-free-text]');
    const trackToggles = Array.from(root.querySelectorAll('[data-work-menu-track-toggle]'));
    const trackRows = Array.from(root.querySelectorAll('[data-work-menu-track-open]'));
    const trackCards = Array.from(root.querySelectorAll('[data-work-menu-track-row]'));
    const editButtons = Array.from(root.querySelectorAll('[data-work-menu-track-edit]'));
    const mealCards = Array.from(root.querySelectorAll('[data-work-menu-meal]'));
    const mealOpenCards = Array.from(root.querySelectorAll('[data-work-menu-meal-open]'));
    const expandButtons = Array.from(root.querySelectorAll('[data-work-menu-expand-toggle]'));
    const managedRole = root.dataset.managedRole === 'true';
    const storageKey = root.dataset.storageKey || '';
    const defaultVisibleKeys = normalizeTrackList((root.dataset.defaultVisibleKeys || '').split(','));
    const availableKeys = normalizeTrackList(trackToggles.map((checkbox) => checkbox.dataset.trackKey));
    let visibleKeys = normalizeTrackList(readStoredKeys(storageKey) || defaultVisibleKeys);
    let lastActiveElement = null;
    let lastBuilderBridge = null;
    let lastBuilderHostKind = '';
    let lastBuilderHostActiveElement = null;
    let lastBuilderHostScrollX = window.scrollX || 0;
    let lastBuilderHostScrollY = window.scrollY || 0;
    let builderHostRuntimeReady = false;
    let pendingBuilderHostOpen = null;

    function validVisibleKeys(values) {
      const filtered = normalizeTrackList(values).filter((key) => availableKeys.includes(key));
      return filtered.length ? filtered : defaultVisibleKeys.filter((key) => availableKeys.includes(key));
    }

    function syncToggleInputs() {
      trackToggles.forEach((checkbox) => {
        checkbox.checked = visibleKeys.includes(normalizeKey(checkbox.dataset.trackKey));
      });
    }

    function updateTrackVisibility() {
      mealCards.forEach((mealCard) => {
        const mealId = mealCard.dataset.mealId || '';
        const expanded = mealCard.dataset.mealExpanded === 'true';
        const rows = trackCards.filter((row) => row.dataset.mealId === mealId);
        const hiddenCount = rows.reduce((count, row) => {
          const trackKey = normalizeKey(row.dataset.trackKey);
          const show = expanded || visibleKeys.includes(trackKey);
          row.hidden = !show;
          row.classList.toggle('is-hidden-by-filter', !show);
          return count + (show ? 0 : 1);
        }, 0);

        const expandButton = mealCard.querySelector('[data-work-menu-expand-toggle]');
        if (expandButton) {
          const canExpand = hiddenCount > 0;
          expandButton.hidden = !canExpand && !expanded;
          expandButton.setAttribute('aria-expanded', expanded ? 'true' : 'false');
          expandButton.setAttribute('aria-label', expanded ? expandButton.dataset.expandedLabel || '' : expandButton.dataset.collapsedLabel || '');
          const marker = expandButton.querySelector('[aria-hidden="true"]');
          if (marker) {
            marker.textContent = expanded ? '−' : '+';
          }
        }
      });

      writeStoredKeys(storageKey, visibleKeys);
    }

    function applyPreferences() {
      visibleKeys = validVisibleKeys(visibleKeys);
      syncToggleInputs();
      updateTrackVisibility();
    }

    function setMealExpanded(mealCard, expanded) {
      mealCard.dataset.mealExpanded = expanded ? 'true' : 'false';
      updateTrackVisibility();
    }

    function getTrackCard(trackButton) {
      if (!(trackButton instanceof HTMLElement)) {
        return null;
      }
      return trackButton.closest('[data-work-menu-track-row]') || trackButton;
    }

    function closeModal() {
      if (!modal) {
        return;
      }
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
      document.body.classList.remove('offshore-work-menu-modal-open');
      if (lastActiveElement && typeof lastActiveElement.focus === 'function') {
        lastActiveElement.focus();
      }
    }

    function closeBuilderHost() {
      if (!builderHost) {
        return;
      }
      builderHost.hidden = true;
      builderHost.setAttribute('aria-hidden', 'true');
      builderHost.classList.remove('offshore-work-menu-builder-host--open');
      builderHost.classList.remove('offshore-work-menu-builder-host--ready');
      document.body.classList.remove('offshore-work-menu-builder-host-open');
      pendingBuilderHostOpen = null;
      window.scrollTo(lastBuilderHostScrollX, lastBuilderHostScrollY);
      if (lastBuilderHostActiveElement && typeof lastBuilderHostActiveElement.focus === 'function') {
        lastBuilderHostActiveElement.focus();
      }
    }

    function postBuilderHostPing() {
      if (!builderHostFrame || !builderHostFrame.contentWindow) {
        return;
      }
      builderHostFrame.contentWindow.postMessage(
        {
          type: 'builder-host-ping',
          detail: {
            source: 'offshore-work-menu',
          },
        },
        window.location.origin,
      );
    }

    function postBuilderHostOpen(bridge, hostKind = 'composition') {
      if (!builderHostFrame || !builderHostFrame.contentWindow || !bridge || !bridge.composition_id) {
        return;
      }
      builderHostFrame.contentWindow.postMessage(
        {
          type: 'builder-host-open',
          detail: {
            source: 'offshore-work-menu',
            kind: hostKind,
            host_target_id: bridge.composition_id,
          },
        },
        window.location.origin,
      );
    }

    function openBuilderHost(bridge, hostKind = 'composition') {
      if (!builderHost || !builderHostFrame || !bridge || !bridge.composition_id || !bridge.builder_url) {
        return false;
      }
      lastBuilderHostActiveElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      lastBuilderBridge = bridge;
      lastBuilderHostKind = String(hostKind || 'composition');
      if (builderHostTitle) {
        builderHostTitle.textContent = bridge.composition_name || bridge.composition_id;
      }
      lastBuilderHostScrollX = window.scrollX || 0;
      lastBuilderHostScrollY = window.scrollY || 0;
      builderHost.hidden = false;
      builderHost.setAttribute('aria-hidden', 'false');
      builderHost.classList.add('offshore-work-menu-builder-host--open');
      builderHost.classList.remove('offshore-work-menu-builder-host--ready');
      document.body.classList.add('offshore-work-menu-builder-host-open');
      pendingBuilderHostOpen = {
        bridge,
        hostKind: lastBuilderHostKind,
      };
      if (builderHostRuntimeReady) {
        postBuilderHostOpen(bridge, lastBuilderHostKind);
      } else {
        postBuilderHostPing();
      }
      return true;
    }

    function openBuilderHostFromTrack(trackButton) {
      const trackCard = getTrackCard(trackButton);
      if (!trackCard) {
        return false;
      }
      const rawBridge = trackCard.dataset.builderBridge || '';
      if (!rawBridge) {
        return false;
      }
      let bridge = null;
      try {
        bridge = JSON.parse(rawBridge);
      } catch (error) {
        return false;
      }
      if (!bridge || !bridge.composition_id || !bridge.builder_url) {
        return false;
      }
      return openBuilderHost(bridge);
    }

    function syncModalFields(trackButton) {
      const trackCard = getTrackCard(trackButton);
      if (!trackCard) {
        return;
      }
      const serviceEventId = trackCard.dataset.serviceEventId || '';
      const trackKey = trackCard.dataset.trackKey || '';
      const serviceDate = trackCard.dataset.serviceDate || '';
      const decisionType = trackCard.dataset.decisionType || 'use_published';
      const builderCompositionId = trackCard.dataset.builderCompositionId || '';
      const freeText = trackCard.dataset.freeText || '';

      root.querySelectorAll('[data-work-menu-field="service_event_id"]').forEach((field) => {
        field.value = serviceEventId;
      });
      root.querySelectorAll('[data-work-menu-field="menu_track_key"]').forEach((field) => {
        field.value = trackKey;
      });
      root.querySelectorAll('[data-work-menu-field="service_date"]').forEach((field) => {
        field.value = serviceDate;
      });

      if (decisionTypeField) {
        decisionTypeField.value = decisionType;
      }
      if (builderField) {
        builderField.value = builderCompositionId;
      }
      if (freeTextField) {
        freeTextField.value = freeText;
      }
    }

    function syncModalSections(mode) {
      if (!decisionTypeField) {
        return;
      }
      const value = decisionTypeField.value;
      const chooserMode = mode === 'chooser';
      const decisionTypeWrapper = root.querySelector('[data-work-menu-field-wrapper="decision-type"]');
      const builderWrapper = root.querySelector('[data-work-menu-field-wrapper="builder"]');
      const freeTextWrapper = root.querySelector('[data-work-menu-field-wrapper="free-text"]');
      const showBuilder = value === 'use_builder_composition';
      const showFreeText = value === 'use_free_text';
      if (decisionTypeWrapper) {
        decisionTypeWrapper.hidden = chooserMode;
      }
      if (builderWrapper) {
        builderWrapper.hidden = chooserMode ? false : !showBuilder;
      }
      if (freeTextWrapper) {
        freeTextWrapper.hidden = chooserMode ? true : !showFreeText;
      }
      if (builderField) {
        builderField.required = showBuilder;
      }
      if (freeTextField) {
        freeTextField.required = showFreeText;
      }
    }

    function syncBuilderBridge(trackButton) {
      if (!modalBridge || !modalBridgeTitle || !modalBridgeSummary || !modalBridgeComponents || !modalBridgeLink) {
        return;
      }

      modalBridge.hidden = true;
      modalBridgeTitle.textContent = '';
      modalBridgeSummary.textContent = '';
      modalBridgeComponents.innerHTML = '';
      modalBridgeLink.textContent = 'Öppna i Menu Builder';
      modalBridgeLink.removeAttribute('aria-disabled');
      modalBridgeLink.removeAttribute('href');

      const rawBridge = trackButton.dataset.builderBridge || '';
      if (!rawBridge) {
        return;
      }

      let bridge = null;
      try {
        bridge = JSON.parse(rawBridge);
      } catch (error) {
        return;
      }
      if (!bridge || !bridge.composition_id) {
        return;
      }

      lastBuilderBridge = bridge;

      modalBridgeTitle.textContent = bridge.composition_name || bridge.composition_id;
      const componentCount = Number.isFinite(Number(bridge.component_count)) ? Number(bridge.component_count) : 0;
      modalBridgeSummary.textContent = componentCount > 0
        ? `${componentCount} komponenter från den kanoniska Builder-kompositionen.`
        : 'Ingen komponentdata finns ännu för den här Builder-kompositionen.';

      const components = Array.isArray(bridge.components) ? bridge.components : [];
      components.forEach((component) => {
        const item = document.createElement('li');
        const parts = [];
        if (Number.isFinite(Number(component.sort_order))) {
          parts.push(String(component.sort_order));
        }
        parts.push(component.component_name || component.component_id || 'Okänd komponent');
        if (component.role) {
          parts.push(component.role);
        }
        const link = document.createElement('a');
        link.href = component.details_url || bridge.builder_url || '#';
        link.target = '_blank';
        link.rel = 'noreferrer noopener';
        link.textContent = parts.join(' · ');
        item.appendChild(link);
        modalBridgeComponents.appendChild(item);
      });
      if (!components.length) {
        const item = document.createElement('li');
        item.textContent = 'Inga komponenter är kopplade.';
        modalBridgeComponents.appendChild(item);
      }

      if (bridge.builder_url) {
        modalBridgeLink.setAttribute('data-builder-url', bridge.builder_url);
      } else if (bridge.render_url) {
        modalBridgeLink.setAttribute('data-builder-url', bridge.render_url);
      }
      if (bridge.readiness_url) {
        modalBridgeLink.setAttribute('data-readiness-url', bridge.readiness_url);
      }
      modalBridge.hidden = false;
    }

    function openModalFromTrack(trackButton, mode = 'default') {
      if (!modal || !modalPanel || !modalTitle || !modalSummary || !modalPublished || !modalEffective || !modalSource || !modalBadges) {
        return;
      }

      const trackCard = getTrackCard(trackButton);
      if (!trackCard) {
        return;
      }

      lastActiveElement = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      modal.dataset.workMenuMode = mode;

      const mealLabel = trackCard.dataset.mealLabel || '';
      const mealTitle = trackCard.dataset.mealTitle || '';
      const mealTime = trackCard.dataset.mealTime || '';
      const serviceDate = trackCard.dataset.serviceDate || '';
      const title = mode === 'chooser' ? 'Ändra rätt' : (trackCard.dataset.trackLabel || trackCard.dataset.trackKey || '');
      const publishedTitle = trackCard.dataset.publicTitle || '';
      const effectiveTitle = trackCard.dataset.effectiveTitle || '';
      const sourceLabel = trackCard.dataset.sourceLabel || '';
      const badgeLabel = trackCard.dataset.badgeLabel || '';
      const decisionLabel = trackCard.dataset.decisionLabel || '';
      const rowState = trackCard.dataset.rowState || 'published';

      modalTitle.textContent = title;
      modalSummary.textContent = [serviceDate, mealLabel, mealTitle, mealTime].filter(Boolean).join(' · ');
      modalPublished.textContent = publishedTitle || modalPublished.textContent || '';
      modalEffective.textContent = effectiveTitle || modalEffective.textContent || '';
      modalSource.textContent = sourceLabel || '';
      modalBadges.innerHTML = '';

      if (badgeLabel) {
        const badge = document.createElement('span');
        badge.className = 'yp-pill offshore-roadmap-pill';
        badge.textContent = badgeLabel;
        modalBadges.appendChild(badge);
      }
      if (decisionLabel && rowState !== 'published') {
        const badge = document.createElement('span');
        badge.className = 'yp-pill';
        badge.textContent = decisionLabel;
        modalBadges.appendChild(badge);
      }
      if (rowState === 'empty') {
        const badge = document.createElement('span');
        badge.className = 'yp-pill';
        badge.textContent = 'Ofullständig data';
        modalBadges.appendChild(badge);
      }

      syncBuilderBridge(trackCard);

      if (managedRole && saveForm && resetForm) {
        syncModalFields(trackCard);
        if (decisionTypeField && mode === 'chooser') {
          decisionTypeField.value = 'use_builder_composition';
        }
        if (builderField && mode === 'chooser') {
          builderField.value = trackCard.dataset.builderCompositionId || '';
        }
        if (freeTextField && mode === 'chooser') {
          freeTextField.value = '';
        }
        syncModalSections(mode);
      }

      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('offshore-work-menu-modal-open');
      const focusables = getFocusable(modalPanel);
      if (focusables.length) {
        focusables[0].focus();
      } else {
        modalPanel.focus();
      }
    }

    trackToggles.forEach((checkbox) => {
      checkbox.addEventListener('change', () => {
        const nextKeys = trackToggles.filter((input) => input.checked).map((input) => normalizeKey(input.dataset.trackKey));
        visibleKeys = validVisibleKeys(nextKeys);
        syncToggleInputs();
        updateTrackVisibility();
      });
    });

    expandButtons.forEach((button) => {
      button.addEventListener('click', () => {
        const mealCard = button.closest('[data-work-menu-meal]');
        if (!mealCard) {
          return;
        }
        const expanded = mealCard.dataset.mealExpanded === 'true';
        setMealExpanded(mealCard, !expanded);
      });
    });

    mealOpenCards.forEach((card) => {
      card.addEventListener('click', (event) => {
        if (event.target instanceof HTMLElement && event.target.closest('button, a, input, select, textarea, label, [data-work-menu-track-open], [data-work-menu-expand-toggle]')) {
          return;
        }
      });
    });

    trackRows.forEach((row) => {
      row.addEventListener('click', (event) => {
        if (openBuilderHostFromTrack(row)) {
          event.preventDefault();
          event.stopPropagation();
          return;
        }
      });
    });

    editButtons.forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault();
        event.stopPropagation();
        openModalFromTrack(button, 'chooser');
      });
    });

    if (modalBridgeLink) {
      modalBridgeLink.addEventListener('click', (event) => {
        event.preventDefault();
        if (lastBuilderBridge) {
          openBuilderHost(lastBuilderBridge);
        }
      });
    }

    if (builderHostFrame) {
      builderHostFrame.addEventListener('load', () => {
        postBuilderHostPing();
      });
    }

    window.addEventListener('message', (event) => {
      if (event.origin !== window.location.origin) {
        return;
      }
      if (!builderHostFrame || event.source !== builderHostFrame.contentWindow) {
        return;
      }
      const payload = event.data || {};
      const detail = payload.detail || {};
      if (payload.type === 'builder-host-runtime-ready') {
        builderHostRuntimeReady = true;
        if (pendingBuilderHostOpen) {
          postBuilderHostOpen(pendingBuilderHostOpen.bridge, pendingBuilderHostOpen.hostKind);
        }
        return;
      }
      if (!builderHost || builderHost.hidden) {
        return;
      }
      if (!lastBuilderBridge) {
        return;
      }
      if (payload.type === 'builder-host-ready') {
        if (String(detail.host_target_id || '') !== String(lastBuilderBridge.composition_id || '')) {
          return;
        }
        if (String(detail.kind || '') !== lastBuilderHostKind) {
          return;
        }
        builderHost.classList.add('offshore-work-menu-builder-host--ready');
        if (builderHostFrame) {
          try {
            builderHostFrame.focus();
          } catch (error) {
            // Ignore focus failures in restricted environments.
          }
        }
        return;
      }
      if (payload.type !== 'builder-host-close') {
        return;
      }
      if (String(detail.host_target_id || '') !== String(lastBuilderBridge.composition_id || '')) {
        return;
      }
      if (String(detail.kind || '') !== lastBuilderHostKind) {
        return;
      }
      closeBuilderHost();
    });

    if (modal) {
      modal.addEventListener('click', (event) => {
        if (event.target instanceof HTMLElement && event.target.closest('[data-work-menu-modal-close]')) {
          event.preventDefault();
          closeModal();
        }
      });

      document.addEventListener('keydown', (event) => {
        if (!modal.hidden && event.key === 'Escape') {
          event.preventDefault();
          closeModal();
          return;
        }
        if (!modal.hidden && event.key === 'Tab' && modalPanel) {
          const focusables = getFocusable(modalPanel);
          if (!focusables.length) {
            return;
          }
          const first = focusables[0];
          const last = focusables[focusables.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }
      });
    }

    if (decisionTypeField) {
      decisionTypeField.addEventListener('change', () => {
        const mode = modal ? modal.dataset.workMenuMode || 'default' : 'default';
        syncModalSections(mode);
      });
    }

    if (saveForm) {
      saveForm.addEventListener('submit', () => {
        if (modal && modal.dataset.workMenuMode === 'chooser' && decisionTypeField) {
          decisionTypeField.value = 'use_builder_composition';
        }
      });
    }

    applyPreferences();
  }

  document.addEventListener('DOMContentLoaded', init);
})();