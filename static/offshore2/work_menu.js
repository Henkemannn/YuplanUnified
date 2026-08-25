(function () {
  'use strict';

  function normalizeKey(value) {
    return String(value || '').trim().toLowerCase();
  }

  function normalizeTrackList(values) {
    return Array.from(new Set((values || []).map(normalizeKey).filter(Boolean)));
  }

  function formatGroupLabel(value) {
    const raw = String(value || '').trim();
    if (!raw) {
      return '';
    }
    return raw
      .replace(/[_-]+/g, ' ')
      .split(/\s+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }

  function normalizePickerGroup(value) {
    const key = normalizeKey(value);
    if (key === 'kott' || key === 'fisk' || key === 'dessert' || key === 'ovrigt') {
      return key;
    }
    return 'ovrigt';
  }

  function formatPickerGroupLabel(value) {
    return {
      kott: 'Kött',
      fisk: 'Fisk',
      dessert: 'Dessert',
      ovrigt: 'Övrigt',
    }[normalizePickerGroup(value)] || 'Övrigt';
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
    const picker = root.querySelector('[data-work-menu-dish-picker]');
    const pickerContext = root.querySelector('[data-work-menu-picker-context]');
    const pickerCurrent = root.querySelector('[data-work-menu-picker-current]');
    const pickerInstruction = root.querySelector('[data-work-menu-picker-instruction]');
    const pickerSearch = root.querySelector('[data-work-menu-picker-search]');
    const pickerCategories = root.querySelector('[data-work-menu-picker-categories]');
    const pickerRelevantSection = root.querySelector('[data-work-menu-picker-relevant-section]');
    const pickerRelevant = root.querySelector('[data-work-menu-picker-relevant]');
    const pickerBrowse = root.querySelector('[data-work-menu-picker-browse]');
    const pickerResultsSection = root.querySelector('[data-work-menu-picker-results-section]');
    const pickerResultsTitle = root.querySelector('[data-work-menu-picker-results-title]');
    const pickerResults = root.querySelector('[data-work-menu-picker-results]');
    const pickerConfirm = root.querySelector('[data-work-menu-picker-confirm]');
    const pickerConfirmText = root.querySelector('[data-work-menu-picker-confirm-text]');
    const pickerConfirmCurrent = root.querySelector('[data-work-menu-picker-confirm-current]');
    const pickerConfirmSelected = root.querySelector('[data-work-menu-picker-confirm-selected]');
    const pickerConfirmMeta = root.querySelector('[data-work-menu-picker-confirm-meta]');
    const pickerSubmit = root.querySelector('[data-work-menu-picker-submit]');
    const pickerBack = root.querySelector('[data-work-menu-picker-back]');
    const pickerReset = root.querySelector('[data-work-menu-picker-reset]');
    const pickerResetTitle = root.querySelector('[data-work-menu-picker-reset-title]');
    const pickerCreateNew = root.querySelector('[data-dish-picker-create-new]');
    const legacySummary = root.querySelector('[data-work-menu-legacy-summary]');
    const pickerSubmitDefaultLabel = pickerSubmit ? (pickerSubmit.textContent || 'Byt rätt') : 'Byt rätt';
    const compositionOptions = (() => {
      const script = root.querySelector('[data-work-menu-composition-options]');
      if (!script) {
        return [];
      }
      try {
        const parsed = JSON.parse(script.textContent || '[]');
        return Array.isArray(parsed) ? parsed : [];
      } catch (error) {
        return [];
      }
    })();
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
    let pickerActiveTrack = null;
    let pickerSelectedOption = '';
    let pickerActiveCategory = 'all';
    let pickerSearchValue = '';
    let pickerViewMode = 'browse';
    let pickerSubmitting = false;

    function hidePicker() {
      if (picker) {
        picker.hidden = true;
      }
      if (pickerConfirm) {
        pickerConfirm.hidden = true;
      }
      if (pickerBrowse) {
        pickerBrowse.hidden = false;
      }
      pickerViewMode = 'browse';
      pickerActiveTrack = null;
      pickerSelectedOption = '';
      pickerActiveCategory = 'all';
      pickerSearchValue = '';
      if (legacySummary) {
        legacySummary.hidden = false;
      }
      if (modalSummary) {
        modalSummary.hidden = false;
      }
      if (modalPublished) {
        modalPublished.hidden = false;
      }
      if (modalEffective) {
        modalEffective.hidden = false;
      }
      if (modalSource) {
        modalSource.hidden = false;
      }
      if (modalBadges) {
        modalBadges.hidden = false;
      }
      pickerSubmitting = false;
      if (pickerSubmit) {
        pickerSubmit.disabled = false;
        pickerSubmit.textContent = pickerSubmitDefaultLabel;
      }
    }

    function setPickerViewMode(mode) {
      pickerViewMode = mode === 'confirm' ? 'confirm' : 'browse';
      const browsing = pickerViewMode === 'browse';
      if (pickerBrowse) {
        pickerBrowse.hidden = !browsing;
      }
      if (pickerSearch) {
        pickerSearch.hidden = !browsing;
      }
      if (pickerCategories) {
        pickerCategories.hidden = !browsing;
      }
      if (pickerRelevantSection) {
        pickerRelevantSection.hidden = !browsing || pickerRelevantSection.hidden;
      }
      if (pickerResultsTitle) {
        pickerResultsTitle.hidden = !browsing;
      }
      if (pickerResults) {
        pickerResults.hidden = !browsing;
      }
      if (pickerReset) {
        pickerReset.hidden = !browsing;
      }
      if (pickerCreateNew) {
        pickerCreateNew.hidden = !browsing;
      }
      if (pickerConfirm) {
        pickerConfirm.hidden = browsing;
      }
      if (pickerInstruction) {
        pickerInstruction.hidden = !browsing;
      }
    }

    function setPickerResults(items, container, emptyLabel) {
      if (!container) {
        return;
      }
      container.innerHTML = '';
      if (!items.length) {
        const empty = document.createElement('div');
        empty.className = 'offshore-work-menu-picker__context-line';
        empty.textContent = emptyLabel;
        container.appendChild(empty);
        return;
      }
      items.forEach((item) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'offshore-work-menu-picker__result';
        if (String(item.value) === String(pickerSelectedOption)) {
          button.classList.add('offshore-work-menu-picker__result--selected');
        }
        button.dataset.dishPickerValue = String(item.value || '');
        const title = document.createElement('div');
        title.className = 'offshore-work-menu-picker__result-title';
        title.textContent = item.label || item.value || 'Okänd rätt';
        const meta = document.createElement('div');
        meta.className = 'offshore-work-menu-picker__result-meta';
        meta.textContent = formatPickerGroupLabel(item.library_group);
        button.appendChild(title);
        button.appendChild(meta);
        container.appendChild(button);
      });
    }

    function renderPickerCategories() {
      if (!pickerCategories) {
        return;
      }
      const groups = Array.from(new Set(compositionOptions.map((option) => normalizePickerGroup(option.library_group))));
      const chips = [{ key: 'all', label: 'Alla' }].concat(
        groups.map((group) => ({ key: group, label: formatPickerGroupLabel(group) })),
      );
      pickerCategories.innerHTML = '';
      chips.forEach((chip) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'offshore-work-menu-picker__chip';
        button.textContent = chip.label;
        button.dataset.dishPickerCategory = chip.key;
        if (chip.key === pickerActiveCategory) {
          button.classList.add('offshore-work-menu-picker__chip--active');
        }
        pickerCategories.appendChild(button);
      });
    }

    function filterCompositionOptions() {
      const search = normalizeKey(pickerSearchValue);
      return compositionOptions.filter((option) => {
        const optionGroup = normalizePickerGroup(option.library_group);
        const matchesCategory = pickerActiveCategory === 'all' || optionGroup === pickerActiveCategory;
        if (!matchesCategory) {
          return false;
        }
        if (!search) {
          return true;
        }
        const haystack = [option.label, option.value, option.library_group].map(normalizeKey).join(' ');
        return haystack.includes(search);
      });
    }

    function renderPickerResults() {
      if (!picker || !pickerRelevant || !pickerResults) {
        return;
      }
      const filteredItems = filterCompositionOptions();
      const searchActive = Boolean(pickerSearchValue.trim());
      const categoryActive = pickerActiveCategory !== 'all';
      const defaultBrowse = !searchActive && !categoryActive;
      const relevantItems = defaultBrowse ? compositionOptions.slice(0, 4) : [];
      setPickerResults(relevantItems, pickerRelevant, 'Inga relevanta rätter hittades.');
      setPickerResults(defaultBrowse ? [] : filteredItems, pickerResults, 'Inga rätter matchar sökningen.');
      if (pickerResultsTitle) {
        pickerResultsTitle.textContent = searchActive || categoryActive ? 'Resultat' : 'Resultat';
      }
      if (pickerRelevantSection) {
        pickerRelevantSection.hidden = pickerViewMode === 'confirm' || !defaultBrowse || relevantItems.length === 0;
      }
      if (pickerResultsSection) {
        pickerResultsSection.hidden = pickerViewMode === 'confirm' || defaultBrowse;
      }
    }

    function updatePickerConfirm() {
      if (!pickerConfirm || !pickerConfirmText || !pickerConfirmMeta) {
        return;
      }
      const selected = compositionOptions.find((option) => String(option.value) === String(pickerSelectedOption));
      if (!selected) {
        pickerConfirm.hidden = true;
        return;
      }
      pickerConfirm.hidden = false;
      pickerConfirmText.textContent = 'Byt rätt?';
      if (pickerConfirmCurrent) {
        pickerConfirmCurrent.textContent = `Nuvarande rätt: ${pickerActiveTrack ? (pickerActiveTrack.dataset.publishedTitle || pickerActiveTrack.dataset.effectiveTitle || '—') : '—'}`;
      }
      if (pickerConfirmSelected) {
        pickerConfirmSelected.textContent = `→ ${selected.label || 'Vald rätt'}`;
      }
      pickerConfirmMeta.textContent = [pickerActiveTrack ? pickerActiveTrack.dataset.dayLabel : '', pickerActiveTrack ? pickerActiveTrack.dataset.mealLabel : '', formatPickerGroupLabel(selected.library_group)].filter(Boolean).join(' · ');
      if (pickerSubmit) {
        pickerSubmit.disabled = false;
      }
      if (builderField) {
        builderField.value = String(selected.value || '');
      }
      setPickerViewMode('confirm');
    }

    function selectPickerOption(value) {
      pickerSelectedOption = String(value || '');
      renderPickerResults();
      updatePickerConfirm();
    }

    function returnToPickerBrowse() {
      setPickerViewMode('browse');
      if (pickerConfirm) {
        pickerConfirm.hidden = true;
      }
      if (pickerSubmit) {
        pickerSubmit.disabled = false;
        pickerSubmit.textContent = pickerSubmitDefaultLabel;
      }
      pickerSubmitting = false;
      renderPickerResults();
      if (pickerSearch) {
        pickerSearch.focus();
      }
    }

    function openDishPicker(trackButton) {
      if (!picker || !modal || !managedRole) {
        return;
      }
      pickerActiveTrack = getTrackCard(trackButton);
      if (!pickerActiveTrack) {
        return;
      }
        const currentComposition = compositionOptions.find((option) => String(option.value) === String(pickerActiveTrack.dataset.builderCompositionId || '')) || null;
      modal.dataset.workMenuMode = 'chooser';
      modalTitle.textContent = 'Byt rätt';
      modalSummary.hidden = true;
      modalPublished.hidden = true;
      modalEffective.hidden = true;
      modalSource.hidden = true;
      modalBadges.hidden = true;
      if (modalBridge) {
        modalBridge.hidden = true;
      }
      if (legacySummary) {
        legacySummary.hidden = true;
      }
      if (pickerContext) {
        pickerContext.textContent = [pickerActiveTrack.dataset.dayLabel || '', pickerActiveTrack.dataset.mealLabel || '', formatPickerGroupLabel(currentComposition ? currentComposition.library_group : pickerActiveTrack.dataset.trackGroup || '')].filter(Boolean).join(' · ');
      }
      if (pickerCurrent) {
        pickerCurrent.textContent = `Nuvarande rätt: ${currentComposition ? currentComposition.label : (pickerActiveTrack.dataset.publishedTitle || pickerActiveTrack.dataset.effectiveTitle || '—')}`;
      }
      pickerActiveCategory = 'all';
      pickerSelectedOption = '';
      if (pickerSearch) {
        pickerSearch.value = '';
      }
      if (pickerResetTitle) {
        pickerResetTitle.textContent = pickerActiveTrack.dataset.publishedTitle || pickerActiveTrack.dataset.effectiveTitle || '';
      }
      if (picker) {
        picker.hidden = false;
      }
      if (pickerConfirm) {
        pickerConfirm.hidden = true;
      }
      if (pickerSubmit) {
        pickerSubmit.disabled = false;
        pickerSubmit.textContent = pickerSubmitDefaultLabel;
      }
      pickerSubmitting = false;
      setPickerViewMode('browse');
      if (saveForm && resetForm) {
        syncModalFields(pickerActiveTrack);
        if (decisionTypeField) {
          decisionTypeField.value = 'use_builder_composition';
        }
        syncModalSections('chooser');
      }
      renderPickerCategories();
      renderPickerResults();
      updatePickerConfirm();
      modal.hidden = false;
      modal.setAttribute('aria-hidden', 'false');
      document.body.classList.add('offshore-work-menu-modal-open');
      if (pickerSearch) {
        pickerSearch.focus();
      }
    }

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
      hidePicker();
      modal.hidden = true;
      modal.setAttribute('aria-hidden', 'true');
      modal.dataset.workMenuMode = 'default';
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
      const publishedTitle = trackCard.dataset.publicTitle || '';
      const effectiveTitle = trackCard.dataset.effectiveTitle || '';
      const sourceLabel = trackCard.dataset.sourceLabel || '';
      const badgeLabel = trackCard.dataset.badgeLabel || '';
      const decisionLabel = trackCard.dataset.decisionLabel || '';
      const rowState = trackCard.dataset.rowState || 'published';

      if (mode === 'chooser') {
        openDishPicker(trackCard);
        return;
      }

      const title = trackCard.dataset.trackLabel || trackCard.dataset.trackKey || '';

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

    if (trackRows.length) {
      trackRows.forEach((row) => {
        const titleButton = row.querySelector('[data-work-menu-track-open]');
        if (titleButton) {
          titleButton.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            openBuilderHostFromTrack(row);
          });
        }
      });
    }

    if (pickerSearch) {
      pickerSearch.addEventListener('input', () => {
        pickerSearchValue = pickerSearch.value || '';
        setPickerViewMode('browse');
        renderPickerResults();
      });
    }

    if (pickerCategories) {
      pickerCategories.addEventListener('click', (event) => {
        const button = event.target instanceof HTMLElement ? event.target.closest('[data-dish-picker-category]') : null;
        if (!button) {
          return;
        }
        pickerActiveCategory = String(button.dataset.dishPickerCategory || 'all');
        setPickerViewMode('browse');
        if (pickerResultsSection) {
          pickerResultsSection.hidden = false;
        }
        renderPickerCategories();
        renderPickerResults();
      });
    }

    if (pickerResults) {
      pickerResults.addEventListener('click', (event) => {
        const button = event.target instanceof HTMLElement ? event.target.closest('[data-dish-picker-value]') : null;
        if (!button) {
          return;
        }
        selectPickerOption(button.dataset.dishPickerValue || '');
      });
    }

    if (pickerRelevant) {
      pickerRelevant.addEventListener('click', (event) => {
        const button = event.target instanceof HTMLElement ? event.target.closest('[data-dish-picker-value]') : null;
        if (!button) {
          return;
        }
        selectPickerOption(button.dataset.dishPickerValue || '');
      });
    }

    if (pickerSubmit) {
      pickerSubmit.addEventListener('click', (event) => {
        event.preventDefault();
        if (pickerSubmitting || !saveForm || !pickerSelectedOption) {
          return;
        }
        pickerSubmitting = true;
        pickerSubmit.disabled = true;
        pickerSubmit.textContent = 'Byter…';
        if (pickerConfirm) {
          pickerConfirm.hidden = true;
        }
        if (picker) {
          picker.hidden = true;
        }
        if (modal) {
          modal.hidden = true;
          modal.setAttribute('aria-hidden', 'true');
        }
        document.body.classList.remove('offshore-work-menu-modal-open');
        if (decisionTypeField) {
          decisionTypeField.value = 'use_builder_composition';
        }
        if (builderField) {
          builderField.value = pickerSelectedOption;
        }
        if (freeTextField) {
          freeTextField.value = '';
        }
        window.requestAnimationFrame(() => {
          saveForm.requestSubmit ? saveForm.requestSubmit() : saveForm.submit();
        });
      });
    }

    if (pickerBack) {
      pickerBack.addEventListener('click', (event) => {
        event.preventDefault();
        returnToPickerBrowse();
      });
    }

    if (pickerReset) {
      pickerReset.addEventListener('click', (event) => {
        event.preventDefault();
        if (resetForm) {
          resetForm.requestSubmit ? resetForm.requestSubmit() : resetForm.submit();
        }
      });
    }

    if (pickerCreateNew) {
      pickerCreateNew.addEventListener('click', (event) => {
        event.preventDefault();
      });
    }

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