(function () {
  'use strict';

  const modalState = {
    currentBuilderComposition: null,
    currentBuilderDishTab: 'overview',
    currentDishAllergenSummaryToken: 0,
    currentDishCalculationSummaryToken: 0,
    selectedComponentId: null,
    pendingComponentCreateForCompositionId: null,
    pendingComponentCreateForCompositionName: null,
    pendingComponentCreateReturnTab: 'components',
    pendingComponentCreateComponentId: null,
    _activeComponentDetailId: '',
    _activeComponentDetailTab: 'overview',
    _componentDetailDirty: false,
    _componentDetailTagsDraft: [],
  };

  const state = {
    cachedComponents: [],
    cachedCompositions: [],
    controller: null,
    compositionId: '',
    componentId: '',
    hostKind: '',
    hostTargetId: '',
  };

  const componentLoadPromises = new Map();
  const compositionLoadPromises = new Map();

  function normalizeId(value) {
    return String(value || '').trim();
  }

  function readTarget() {
    const url = new URL(window.location.href);
    const compositionId = normalizeId(url.searchParams.get('composition_id'));
    const componentId = normalizeId(url.searchParams.get('component_id'));
    const hostKind = compositionId ? 'composition' : (componentId ? 'component' : '');
    const hostTargetId = compositionId || componentId;
    return { compositionId, componentId, hostKind, hostTargetId };
  }

  async function callApi(url, options = {}) {
    const response = await fetch(url, {
      method: String(options.method || 'GET').toUpperCase(),
      headers: {
        ...(options.headers || {}),
      },
      body: options.body ? JSON.stringify(options.body) : undefined,
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

  function getBuilderOut() {
    return document.getElementById('builderOut');
  }

  function getHostStatusRoot() {
    return document.getElementById('builderEditorHostStatus');
  }

  function showLoading(targetId) {
    const element = document.getElementById(String(targetId || ''));
    if (element) {
      element.textContent = 'Laddar...';
    }
  }

  function showJson(targetId, value) {
    const element = document.getElementById(String(targetId || ''));
    if (!element) {
      return;
    }
    const payload = value && typeof value === 'object' && 'data' in value ? value.data : value;
    element.textContent = typeof payload === 'string' ? payload : JSON.stringify(payload, null, 2);
  }

  function openSimpleModal(modalId) {
    const modal = document.getElementById(String(modalId || ''));
    if (!modal) {
      return;
    }
    modal.classList.remove('hidden');
    modal.removeAttribute('hidden');
    modal.setAttribute('aria-hidden', 'false');
    modal.style.display = '';
    modal.inert = false;
  }

  function closeModalById(modalId) {
    const modal = document.getElementById(String(modalId || ''));
    if (!modal) {
      return;
    }
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    modal.style.display = '';
    modal.inert = false;
  }

  function getCachedComponents() {
    return state.cachedComponents;
  }

  function getCachedCompositions() {
    return state.cachedCompositions;
  }
  function upsertCachedComponent(component) {
    const componentId = normalizeId(component && component.component_id);
    if (!componentId) {
      return null;
    }
    const next = { ...(component || {}), component_id: componentId };
    const index = state.cachedComponents.findIndex(
      (item) => normalizeId(item && item.component_id) === componentId
    );
    if (index >= 0) {
      state.cachedComponents[index] = next;
    } else {
      state.cachedComponents.push(next);
    }
    return next;
  }

  function upsertCachedComposition(composition) {
    const compositionId = normalizeId(composition && composition.composition_id);
    if (!compositionId) {
      return null;
    }
    const next = { ...(composition || {}), composition_id: compositionId };
    const index = state.cachedCompositions.findIndex(
      (item) => normalizeId(item && item.composition_id) === compositionId
    );
    if (index >= 0) {
      state.cachedCompositions[index] = next;
    } else {
      state.cachedCompositions.push(next);
    }
    return next;
  }

  function renderComponentPalette() {}
  function filterLibraryComponents() {}
  function updateComponentCategoryChipCounts() {}
  function currentComponentSearchQuery() { return ''; }
  function resolveComponentCategoryThemeKey(component) {
    return normalizeId(component && component.category) || 'neutral';
  }

  async function loadAllCompositions() {
    const result = await callApi('/api/builder/compositions', { method: 'GET' });
    if (!(result && result.status < 400 && result.data && result.data.ok && Array.isArray(result.data.compositions))) {
      throw new Error('Could not load compositions.');
    }
    state.cachedCompositions = result.data.compositions.slice();
    return state.cachedCompositions;
  }

  async function loadAllComponents() {
    const result = await callApi('/api/builder/components', { method: 'GET' });
    if (!(result && result.status < 400 && result.data && result.data.ok && Array.isArray(result.data.components))) {
      throw new Error('Could not load components.');
    }
    state.cachedComponents = result.data.components.slice();
    return state.cachedComponents;
  }

  async function loadComponentById(componentId) {
    const idValue = normalizeId(componentId);
    if (!idValue) {
      return null;
    }
    const cached = state.cachedComponents.find(
      (item) => normalizeId(item && item.component_id) === idValue
    );
    if (cached) {
      return cached;
    }

    if (componentLoadPromises.has(idValue)) {
      return componentLoadPromises.get(idValue);
    }

    const loadPromise = (async () => {
      const result = await callApi('/api/builder/components/' + encodeURIComponent(idValue), { method: 'GET' });
      if (!(result && result.status < 400 && result.data && result.data.ok && result.data.component)) {
        throw new Error('Could not load component.');
      }
      return upsertCachedComponent(result.data.component);
    })();

    componentLoadPromises.set(idValue, loadPromise);

    try {
      return await loadPromise;
    } finally {
      componentLoadPromises.delete(idValue);
    }
  }

  async function loadCompositionById(compositionId) {
    const idValue = normalizeId(compositionId);
    if (!idValue) {
      return null;
    }
    const cached = state.cachedCompositions.find(
      (item) => normalizeId(item && item.composition_id) === idValue
    );
    if (cached) {
      return cached;
    }

    if (compositionLoadPromises.has(idValue)) {
      return compositionLoadPromises.get(idValue);
    }

    const loadPromise = (async () => {
      const result = await callApi('/api/builder/compositions/' + encodeURIComponent(idValue), { method: 'GET' });
      if (!(result && result.status < 400 && result.data && result.data.ok && result.data.composition)) {
        throw new Error('Could not load composition.');
      }
      return upsertCachedComposition(result.data.composition);
    })();

    compositionLoadPromises.set(idValue, loadPromise);

    try {
      return await loadPromise;
    } finally {
      compositionLoadPromises.delete(idValue);
    }
  }

  async function loadLibrary() {
    await Promise.all([loadAllCompositions(), loadAllComponents()]);
  }

  async function resolveComponentById(componentId) {
    const idValue = normalizeId(componentId);
    if (!idValue) {
      return null;
    }
    const cached = state.cachedComponents.find(
      (item) => normalizeId(item && item.component_id) === idValue
    );
    if (cached) {
      return cached;
    }
    return loadComponentById(idValue);
  }

  async function resolveCompositionById(compositionId) {
    const idValue = normalizeId(compositionId);
    if (!idValue) {
      return null;
    }
    const cached = state.cachedCompositions.find(
      (item) => normalizeId(item && item.composition_id) === idValue
    );
    if (cached) {
      return cached;
    }
    return loadCompositionById(idValue);
  }

  function getCurrentComposition() {
    return state.controller && typeof state.controller.getCurrentComposition === 'function'
      ? state.controller.getCurrentComposition()
      : null;
  }

  async function refreshCurrentCompositionView() {
    const currentComposition = getCurrentComposition();
    const compositionId = normalizeId(currentComposition && currentComposition.composition_id);
    if (!compositionId) {
      return;
    }
    const refreshed = await resolveCompositionById(compositionId);
    if (refreshed && state.controller && typeof state.controller.renderBuilderPanel === 'function') {
      state.controller.renderBuilderPanel(refreshed);
    }
  }

  async function loadCompositionTextPreviewForCurrentComposition(previewId, emptyMessage, loadingMessage, failureMessage) {
    const preview = document.getElementById(String(previewId || ''));
    if (!preview) {
      return;
    }
    const currentComposition = getCurrentComposition();
    const compositionId = normalizeId(currentComposition && currentComposition.composition_id);
    if (!compositionId) {
      preview.textContent = String(emptyMessage || '');
      return;
    }
    preview.textContent = String(loadingMessage || '');
    const result = await callApi('/api/builder/compositions/' + encodeURIComponent(compositionId) + '/render/text', { method: 'GET' });
    if (result && result.status < 400 && result.data && result.data.ok) {
      preview.textContent = String((result.data && result.data.text) || currentComposition.composition_name || emptyMessage || '');
      return;
    }
    preview.textContent = String(failureMessage || '');
  }

  async function attachExistingComponentToCurrentComposition(componentId) {
    const currentComposition = getCurrentComposition();
    const compositionId = normalizeId(currentComposition && currentComposition.composition_id);
    const resolvedComponentId = normalizeId(componentId);
    if (!compositionId || !resolvedComponentId) {
      return { status: 0, data: { ok: false, error: 'no_composition_selected' } };
    }
    const result = await callApi(
      '/api/builder/compositions/' + encodeURIComponent(compositionId) + '/components/attach',
      {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: { component_id: resolvedComponentId },
      },
    );
    if (result && result.status < 400 && result.data && result.data.ok && result.data.composition) {
      await refreshCurrentCompositionView();
    }
    return result;
  }

  async function reopenPendingCompositionForReturn() {
    const compositionId = normalizeId(state.controller && typeof state.controller.getState === 'function'
      ? state.controller.getState('pendingComponentCreateForCompositionId')
      : '');
    if (!compositionId) {
      return null;
    }
    const composition = await resolveCompositionById(compositionId);
    if (!composition || !state.controller || typeof state.controller.openComposition !== 'function') {
      return null;
    }
    state.controller.openComposition(composition, 'components');
    return composition;
  }

  function clearPendingComponentCreateForComposition() {
    if (!state.controller || typeof state.controller.setState !== 'function') {
      return;
    }
    state.controller.setState('pendingComponentCreateForCompositionId', null);
    state.controller.setState('pendingComponentCreateForCompositionName', null);
    state.controller.setState('pendingComponentCreateReturnTab', 'components');
    state.controller.setState('pendingComponentCreateComponentId', null);
  }

  function notifyHostClose(detail) {
    if (!state.hostTargetId) {
      return;
    }
    const payload = {
      type: 'builder-host-close',
      detail: {
        source: 'builder-editor-host',
        host_target_id: state.hostTargetId,
        ...detail,
      },
    };
    if (window.parent && window.parent !== window) {
      window.parent.postMessage(payload, window.location.origin);
    }
  }

  function notifyHostReady(detail) {
    if (!state.hostTargetId) {
      return;
    }
    const payload = {
      type: 'builder-host-ready',
      detail: {
        source: 'builder-editor-host',
        host_target_id: state.hostTargetId,
        ...detail,
      },
    };
    if (window.parent && window.parent !== window) {
      window.parent.postMessage(payload, window.location.origin);
    }
  }

  function setHostStatus(ready, errorText = '') {
    document.body.classList.toggle('builder-editor-host-ready', Boolean(ready));
    document.body.classList.toggle('builder-editor-host-failed', !ready);
    if (!ready) {
      const status = getHostStatusRoot();
      if (status) {
        status.textContent = String(errorText || 'Kunde inte öppna den kanoniska Builder-redigeraren.');
      }
    }
  }

  async function openRequestedTarget() {
    if (!state.hostTargetId) {
      setHostStatus(false, 'Saknar composition_id eller component_id.');
      return;
    }

    try {
      if (state.hostKind === 'composition') {
        const composition = await resolveCompositionById(state.compositionId);
        if (!composition) {
          throw new Error('Kompositionen kunde inte hittas.');
        }
        state.controller.openComposition(composition, 'overview');
      } else {
        const component = await resolveComponentById(state.componentId);
        if (!component) {
          throw new Error('Komponenten kunde inte hittas.');
        }
        await state.controller.openComponentDetailEditor(state.componentId, 'overview');
      }
      setHostStatus(true);
      notifyHostReady({ kind: state.hostKind });
    } catch (error) {
      showJson('builderOut', { status: 0, data: { ok: false, error: String(error && error.message || error) } });
      notifyHostClose({ kind: state.hostKind, error: String(error && error.message || error) });
      setHostStatus(false, String(error && error.message || error));
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    const target = readTarget();
    state.compositionId = target.compositionId;
    state.componentId = target.componentId;
    state.hostKind = target.hostKind;
    state.hostTargetId = target.hostTargetId;

    state.controller = createBuilderModalController({
      compositionRoot: document.getElementById('resolveModal'),
      componentRoot: document.getElementById('componentDetailEditorModal'),
      callApi,
      state: {
        get(key) {
          return modalState[key];
        },
        set(key, value) {
          modalState[key] = value;
          return value;
        },
      },
      loadLibrary,
      getCachedComponents,
      getCachedCompositions,
      resolveComponentById,
      resolveComponentCategoryThemeKey,
      filterLibraryComponents,
      currentComponentSearchQuery,
      updateComponentCategoryChipCounts,
      upsertCachedComponent,
      showLoading,
      showJson,
      openSimpleModal,
      closeModalById,
      renderComponentPalette,
      loadCompositionTextPreviewForCurrentComposition,
      refreshCurrentCompositionView,
      reopenPendingCompositionForReturn,
      attachExistingComponentToCurrentComposition,
      clearPendingComponentCreateForComposition,
      notifyHostReady,
      notifyHostClose,
      initialState: {
        ...modalState,
      },
    });

    await openRequestedTarget();
  });
})();