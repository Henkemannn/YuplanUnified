(function () {
  'use strict';

  function normalize(value) {
    return String(value || '').trim();
  }

  function init() {
    const root = document.querySelector('.menu-week__grid');
    const hostRoot = document.querySelector('[data-admin-week-builder-host]');
    const hostFrame = document.querySelector('[data-admin-week-builder-host-frame]');
    const inlinePicker = document.querySelector('[data-admin-week-builder-inline-picker]');
    const inlineContext = document.querySelector('[data-admin-week-builder-inline-context]');
    const inlineSearch = document.querySelector('[data-admin-week-builder-inline-search]');
    const inlineStatus = document.querySelector('[data-admin-week-builder-inline-status]');
    const inlineResults = document.querySelector('[data-admin-week-builder-inline-results]');
    const inlineCreate = document.querySelector('[data-admin-week-builder-inline-create]');
    const inlineCloseButtons = Array.from(document.querySelectorAll('[data-admin-week-builder-inline-close]'));
    const builderMenuId = normalize(root && root.dataset.builderMenuId);
    const slotRows = Array.from(document.querySelectorAll('[data-week-slot-row]'));

    if (!root || !builderMenuId || !hostRoot || !hostFrame || !inlinePicker || !inlineSearch || !inlineStatus || !inlineResults) {
      return;
    }
    if (!globalThis.YuplanModalHost || typeof globalThis.YuplanModalHost.create !== 'function') {
      return;
    }

    const inlineHost = globalThis.YuplanModalHost.create(hostRoot, {
      bodyClass: 'yp-modal-open',
      mode: 'shell-owned-card',
      openClass: 'is-open',
      backdropSelector: '[data-admin-week-builder-host-close]',
      panelSelector: '[data-admin-week-builder-host-panel]',
      frameSelector: '[data-admin-week-builder-host-frame]',
      resetFrameSrc: 'about:blank',
    });

    const state = {
      activeRow: null,
      activeMenu: null,
      activePickerContext: null,
      activePickerAction: 'replace',
      compositions: null,
      compositionsPromise: null,
      pickerVisible: false,
    };

    function showElement(element) {
      if (!element) {
        return;
      }
      element.hidden = false;
      element.setAttribute('aria-hidden', 'false');
    }

    function hideElement(element) {
      if (!element) {
        return;
      }
      element.hidden = true;
      element.setAttribute('aria-hidden', 'true');
    }

    function closeMenus() {
      if (state.activeMenu) {
        hideElement(state.activeMenu);
      }
      state.activeMenu = null;
      for (const row of slotRows) {
        const trigger = row.querySelector('[data-week-slot-action-toggle]');
        if (trigger) {
          trigger.setAttribute('aria-expanded', 'false');
        }
      }
    }

    function closeAllOverlays() {
      closeMenus();
      if (state.pickerVisible) {
        closeInlinePicker();
      }
    }

    function rowContext(row) {
      if (!row) {
        return null;
      }
      return {
        row,
        dayKey: normalize(row.dataset.dayKey),
        menuDetailId: normalize(row.dataset.menuDetailId),
        dayLabel: normalize(row.dataset.dayLabel),
        mealLabel: normalize(row.dataset.mealLabel),
        slotKey: normalize(row.dataset.slotKey),
        mealSlot: normalize(row.dataset.mealSlot),
        dishName: normalize(row.dataset.dishName),
        compositionId: normalize(row.dataset.compositionId),
        unresolvedText: normalize(row.dataset.unresolvedText),
      };
    }

    function setInlineContext(context, actionMode) {
      if (!inlineContext) {
        return;
      }
      if (!context) {
        inlineContext.textContent = '';
        return;
      }
      const locationParts = [context.dayLabel, context.mealLabel].filter(Boolean);
      const locationLabel = locationParts.length ? locationParts.join(' · ') : 'Vald plats';
      const dishLabel = normalize(context.unresolvedText || context.dishName);
      const actionLabel = actionMode === 'add' ? 'Lägger till' : 'Byter';
      inlineContext.textContent = dishLabel
        ? actionLabel + ': ' + locationLabel + ' · ' + dishLabel
        : actionLabel + ': ' + locationLabel;
    }

    function setStatus(message, isError) {
      inlineStatus.textContent = String(message || '');
      inlineStatus.dataset.state = isError ? 'error' : 'idle';
    }

    function isCreateModalOpen() {
      return Boolean(globalThis.BuilderDishCreateModal && typeof globalThis.BuilderDishCreateModal.isOpen === 'function' && globalThis.BuilderDishCreateModal.isOpen());
    }

    function renderResults() {
      inlineResults.replaceChildren();

      const query = normalize(inlineSearch.value);
      if (!query) {
        setStatus('Sök efter en rätt.');
        return;
      }

      if (state.compositions === null) {
        setStatus('Laddar rättbiblioteket…');
        return;
      }

      if (!globalThis.BuilderCompositionSearchRuntime || typeof globalThis.BuilderCompositionSearchRuntime.filterCompositionsBySearch !== 'function') {
        setStatus('Rättbibliotekssökningen saknas.', true);
        return;
      }

      const compositions = Array.isArray(state.compositions) ? state.compositions : [];
      const filtered = globalThis.BuilderCompositionSearchRuntime.filterCompositionsBySearch(compositions, query);
      if (!filtered.length) {
        const empty = document.createElement('div');
        empty.className = 'yp-modal-host__inline-empty';
        empty.textContent = 'Inga rätter matchar sökningen.';
        inlineResults.appendChild(empty);
        setStatus('Prova en bredare sökning.');
        return;
      }

      const fragment = document.createDocumentFragment();
      for (const composition of filtered.slice(0, 80)) {
        const compositionId = normalize(composition && composition.composition_id);
        if (!compositionId) {
          continue;
        }
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'yp-modal-host__inline-result';
        button.textContent = normalize(composition.composition_name) || compositionId;
        button.addEventListener('click', () => {
          void applyPickedComposition(state.activePickerContext, compositionId);
        });
        fragment.appendChild(button);
      }
      inlineResults.appendChild(fragment);
      setStatus(filtered.length > 80
        ? 'Visar 80 av ' + String(filtered.length) + ' rätter.'
        : 'Välj en rätt eller skapa en ny.');
    }

    async function loadCompositions() {
      if (Array.isArray(state.compositions)) {
        return state.compositions;
      }
      if (state.compositionsPromise) {
        return state.compositionsPromise;
      }

      setStatus('Laddar rättbiblioteket…');
      state.compositionsPromise = fetch('/api/builder/compositions', {
        method: 'GET',
        credentials: 'same-origin',
      }).then(async (response) => {
        let data;
        try {
          data = await response.json();
        } catch (error) {
          throw new Error('Rättbiblioteket svarade med ogiltig data.');
        }
        if (!(response.ok && data && data.ok && Array.isArray(data.compositions))) {
          throw new Error(String(data && (data.message || data.error) || 'Kunde inte läsa rättbiblioteket.'));
        }
        state.compositions = data.compositions;
        return state.compositions;
      }).finally(() => {
        state.compositionsPromise = null;
      });

      return state.compositionsPromise;
    }

    function openExistingDish(compositionId, triggerElement) {
      const resolvedCompositionId = normalize(compositionId);
      if (!resolvedCompositionId || !globalThis.AdminWeekBuilderHost || typeof globalThis.AdminWeekBuilderHost.openComposition !== 'function') {
        return;
      }
      globalThis.AdminWeekBuilderHost.openComposition(resolvedCompositionId, triggerElement);
    }

    function openInlinePicker(context, initialName, actionMode) {
      const pickerContext = context || rowContext(state.activeRow);
      if (!pickerContext) {
        return;
      }

      closeMenus();
      state.activePickerContext = pickerContext;
      state.activePickerAction = actionMode === 'add' ? 'add' : 'replace';
      state.activeRow = pickerContext.row;
      state.pickerVisible = true;

      setInlineContext(pickerContext, state.activePickerAction);
      inlineSearch.value = normalize(initialName || pickerContext.unresolvedText || pickerContext.dishName);
      showElement(inlinePicker);
      inlineHost.open({
        mode: 'shell-owned-card',
        trigger: pickerContext.row,
      });

      loadCompositions()
        .then(() => {
          renderResults();
          requestAnimationFrame(() => {
            if (typeof inlineSearch.focus === 'function') {
              inlineSearch.focus();
            }
          });
        })
        .catch((error) => setStatus(error && error.message ? error.message : String(error), true));

      renderResults();
    }

    function closeInlinePicker() {
      if (!state.pickerVisible && hostRoot.hidden) {
        return;
      }
      state.pickerVisible = false;
      state.activePickerContext = null;
      hideElement(inlinePicker);
      inlineHost.close();
    }

    async function applyPickedComposition(context, compositionId) {
      const targetContext = context || rowContext(state.activePickerContext || state.activeRow);
      const targetCompositionId = normalize(compositionId);
      if (!targetContext || !targetCompositionId) {
        return;
      }
      const targetMealSlot = targetContext.mealSlot || targetContext.slotKey;
      const hasExistingDetail = Boolean(targetContext.menuDetailId);
      const result = hasExistingDetail
        ? await callJson('/api/builder/menus/' + encodeURIComponent(builderMenuId) + '/rows/' + encodeURIComponent(targetContext.menuDetailId), {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: {
              day: targetContext.dayKey,
              meal_slot: targetMealSlot,
              composition_id: targetCompositionId,
            },
          })
        : await callJson('/api/builder/menus/' + encodeURIComponent(builderMenuId) + '/rows', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: {
              day: targetContext.dayKey,
              meal_slot: targetMealSlot,
              composition_id: targetCompositionId,
            },
          });
      if (!(result.status < 400 && result.data && result.data.ok)) {
        window.alert(String((result.data && result.data.message) || 'Kunde inte välja rätt från biblioteket.'));
        return;
      }
      closeInlinePicker();
      window.location.reload();
    }

    async function callJson(url, options) {
      const response = await fetch(url, {
        method: options && options.method ? options.method : 'GET',
        headers: options && options.headers ? options.headers : {},
        body: options && options.body ? JSON.stringify(options.body) : undefined,
        credentials: 'same-origin',
      });
      let data = null;
      try {
        data = await response.json();
      } catch (error) {
        data = { ok: false, error: 'invalid_json_response' };
      }
      return { status: response.status, data };
    }

    async function deleteRow() {
      const context = rowContext(state.activeRow);
      if (!context || !context.menuDetailId) {
        return;
      }
      const result = await callJson('/api/builder/menus/' + encodeURIComponent(builderMenuId) + '/rows/' + encodeURIComponent(context.menuDetailId), {
        method: 'DELETE',
      });
      if (!(result.status < 400 && result.data && result.data.ok)) {
        window.alert(String((result.data && result.data.message) || 'Kunde inte ta bort från menyn.'));
        return;
      }
      window.location.reload();
    }

    function editResolvedComposition() {
      const context = rowContext(state.activeRow);
      if (!context || !context.compositionId) {
        return;
      }
      return openExistingDish(context.compositionId);
    }

    function openCreateFlow() {
      if (!globalThis.BuilderDishCreateModal || typeof globalThis.BuilderDishCreateModal.open !== 'function') {
        setStatus('Skapa rätt-flödet är inte tillgängligt.', true);
        return;
      }
      globalThis.BuilderDishCreateModal.open({
        title: 'Skapa rätt',
        createEndpoint: '/api/builder/compositions/private',
        includeSeedComponents: false,
        initialName: normalize(inlineSearch.value || (state.activePickerContext && (state.activePickerContext.unresolvedText || state.activePickerContext.dishName))),
        onSuccess(composition) {
          const id = normalize(composition && composition.composition_id);
          if (id) {
            void applyPickedComposition(state.activePickerContext, id);
          }
        },
      });
    }

    function bindRowEvents() {
      for (const row of slotRows) {
        const trigger = row.querySelector('[data-week-slot-action-toggle]');
        const menu = row.querySelector('[data-week-slot-action-menu]');
        const buttons = menu ? Array.from(menu.querySelectorAll('[data-week-slot-action]')) : [];

        if (trigger && menu) {
          trigger.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            if (state.activeMenu && state.activeMenu !== menu) {
              hideElement(state.activeMenu);
              const activeTrigger = state.activeRow ? state.activeRow.querySelector('[data-week-slot-action-toggle]') : null;
              if (activeTrigger) {
                activeTrigger.setAttribute('aria-expanded', 'false');
              }
            }
            if (menu.hidden) {
              showElement(menu);
              state.activeMenu = menu;
              state.activeRow = row;
              trigger.setAttribute('aria-expanded', 'true');
            } else {
              hideElement(menu);
              state.activeMenu = null;
              state.activeRow = null;
              trigger.setAttribute('aria-expanded', 'false');
            }
          });
        }

        if (menu) {
          buttons.forEach((button) => {
            button.addEventListener('click', async (event) => {
              event.preventDefault();
              event.stopPropagation();
              state.activeRow = row;
              closeMenus();
              const action = normalize(button.dataset.weekSlotAction);
              const context = rowContext(row);
              if (action === 'replace') {
                openInlinePicker(context);
                return;
              }
              if (action === 'add') {
                openInlinePicker(context, '', 'add');
                return;
              }
              if (action === 'open') {
                if (context && context.compositionId) {
                  editResolvedComposition();
                }
                return;
              }
              if (action === 'remove') {
                await deleteRow();
              }
            });
          });
        }
      }
    }

    inlineSearch.addEventListener('input', () => {
      renderResults();
    });

    inlineCloseButtons.forEach((button) => {
      button.addEventListener('click', (event) => {
        event.preventDefault();
        closeInlinePicker();
      });
    });

    if (inlineCreate) {
      inlineCreate.addEventListener('click', (event) => {
        event.preventDefault();
        openCreateFlow();
      });
    }

    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape' || !isCreateModalOpen()) {
        return;
      }
      if (globalThis.BuilderDishCreateModal && typeof globalThis.BuilderDishCreateModal.close === 'function') {
        globalThis.BuilderDishCreateModal.close('cancel');
      }
      event.preventDefault();
      event.stopImmediatePropagation();
    }, true);

    document.addEventListener('keydown', (event) => {
      if (event.key !== 'Escape') {
        return;
      }
      if (state.pickerVisible) {
        closeInlinePicker();
        return;
      }
      closeMenus();
    });

    document.addEventListener('click', (event) => {
      const target = event.target instanceof HTMLElement ? event.target : null;
      if (!target) {
        return;
      }
      if (!target.closest('[data-week-slot-action-toggle]') && !target.closest('[data-week-slot-action-menu]')) {
        closeMenus();
      }
    });

    bindRowEvents();
  }

  document.addEventListener('DOMContentLoaded', init);
})();
