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
    cachedCompositions: [],
    controller: null,
    compositionId: '',
    componentId: '',
    hostKind: '',
    hostTargetId: '',
    hostMode: 'idle',
    createdCompositionId: '',
    createdCompositionReadySent: false,
  };

  let componentLibraryRuntime = null;

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

  function getCachedCompositions() {
    return state.cachedCompositions;
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

  function getComponentLibraryRuntime() {
    if (componentLibraryRuntime) {
      return componentLibraryRuntime;
    }

    const runtime = BuilderComponentLibraryRuntime.create({
      callApi,
      getCurrentComposition,
      attachComponent: (componentId) => attachExistingComponentToCurrentComposition(componentId),
      onAttachSuccess: async (composition) => {
        if (state.controller && typeof state.controller.closeAddComponentModal === 'function') {
          state.controller.closeAddComponentModal();
        }
        if (state.controller && typeof state.controller.setDishBuilderTab === 'function') {
          state.controller.setDishBuilderTab('components');
        }
        if (state.controller && typeof state.controller.renderBuilderPanel === 'function') {
          state.controller.renderBuilderPanel(composition);
        }
        getComponentLibraryRuntime().renderPalette();
      },
    });
    runtime.bindPalette({
      paletteElement: document.getElementById('builderComponentPalette'),
      searchInputElement: document.getElementById('builderPaletteSearch'),
    });
    componentLibraryRuntime = runtime;
    return componentLibraryRuntime;
  }

  const resolveComponentCategoryThemeKey = BuilderComponentTheme.resolveComponentCategoryThemeKey;

  function openBuilderComponentCreateModal() {
    const createController = globalThis.BuilderComponentCreateModal;
    if (createController && typeof createController.open === 'function') {
      createController.open({
        title: 'Skapa komponent',
        createEndpoint: '/api/builder/components/private',
        onSuccess: async (createdComponent) => {
          const createdComponentId = normalizeId(createdComponent && createdComponent.component_id);
          if (createdComponent) {
            getComponentLibraryRuntime().upsertCachedComponent(createdComponent);
          }
          if (createdComponentId) {
            state.controller.setState('pendingComponentCreateComponentId', createdComponentId);
            await state.controller.openComponentDetailEditor(createdComponentId, 'overview');
          }
        },
      });
      return;
    }
    openSimpleModal('componentCreateModal');
    const input = document.getElementById('freeComponentName');
    if (input) {
      input.focus();
    }
  }

  async function loadAllCompositions() {
    const result = await callApi('/api/builder/compositions', { method: 'GET' });
    if (!(result && result.status < 400 && result.data && result.data.ok && Array.isArray(result.data.compositions))) {
      throw new Error('Could not load compositions.');
    }
    state.cachedCompositions = result.data.compositions.slice();
    return state.cachedCompositions;
  }

  async function loadComponentById(componentId) {
    const idValue = normalizeId(componentId);
    if (!idValue) {
      return null;
    }
    const cached = getComponentLibraryRuntime().resolveComponentById(idValue);
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
      return getComponentLibraryRuntime().upsertCachedComponent(result.data.component);
    })();

    componentLoadPromises.set(idValue, loadPromise);

    try {
      return await loadPromise;
    } finally {
      componentLoadPromises.delete(idValue);
    }
  }

  async function preloadLinkedComponents(composition) {
    const linkedComponents = Array.isArray(composition && composition.components)
      ? composition.components
      : [];
    const linkedIds = [];
    const seen = new Set();
    for (const component of linkedComponents) {
      const componentId = normalizeId(component && component.component_id);
      if (!componentId || seen.has(componentId)) {
        continue;
      }
      seen.add(componentId);
      linkedIds.push(componentId);
    }
    if (linkedIds.length === 0) {
      return [];
    }
    return Promise.all(linkedIds.map((componentId) => loadComponentById(componentId)));
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

  async function prepareLinkedComponentForEdit(componentId) {
    const currentComposition = getCurrentComposition();
    const compositionId = normalizeId(currentComposition && currentComposition.composition_id);
    const sourceComponentId = normalizeId(componentId);
    if (!compositionId || !sourceComponentId) {
      return null;
    }
    const result = await callApi(
      '/api/builder/compositions/' + encodeURIComponent(compositionId) + '/components/' + encodeURIComponent(sourceComponentId) + '/edit-target',
      { method: 'POST' }
    );
    if (!(result && result.status < 400 && result.data && result.data.ok && result.data.component && result.data.composition)) {
      throw new Error('Could not prepare linked component for edit.');
    }
    const component = getComponentLibraryRuntime().upsertCachedComponent(result.data.component);
    const composition = upsertCachedComposition(result.data.composition);
    if (composition) {
      state.controller && typeof state.controller.renderBuilderPanel === 'function' && state.controller.renderBuilderPanel(composition);
    }
    return { component: component || result.data.component, composition: composition || result.data.composition };
  }

  async function resolveCompositionEditTarget(compositionId) {
    const idValue = normalizeId(compositionId);
    if (!idValue) {
      return null;
    }
    const result = await callApi('/api/builder/compositions/' + encodeURIComponent(idValue) + '/edit-target', { method: 'POST' });
    if (!(result && result.status < 400 && result.data && result.data.ok && result.data.composition)) {
      throw new Error('Could not resolve composition edit target.');
    }
    const composition = upsertCachedComposition(result.data.composition);
    return composition || null;
  }

  async function loadLibrary() {
    await Promise.all([loadAllCompositions(), getComponentLibraryRuntime().loadAllComponents()]);
  }

  function openCreateCompositionModal() {
    if (!globalThis.BuilderDishCreateModal || typeof globalThis.BuilderDishCreateModal.open !== 'function') {
      throw new Error('Create Dish UI is not available.');
    }
    globalThis.BuilderDishCreateModal.open({
      title: 'Skapa rätt',
      createEndpoint: '/api/builder/compositions/private',
      includeSeedComponents: false,
      onSuccess: async (composition) => {
        state.hostMode = 'create-composition-open';
        state.createdCompositionId = String(composition && composition.composition_id || '').trim();
        state.createdCompositionReadySent = false;
        state.compositionId = state.createdCompositionId;
        state.componentId = '';
        state.hostKind = 'composition';
        state.hostTargetId = state.compositionId;
        state.controller.openComposition(composition, 'components');
        setHostStatus(true);
      },
      onCancel: () => {
        state.createdCompositionId = '';
        state.createdCompositionReadySent = false;
        notifyHostClose({ kind: 'create-composition', cancelled: true });
      },
    });
  }

  function resolveComponentById(componentId) {
    return getComponentLibraryRuntime().resolveComponentById(componentId);
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
    const currentComposition = getCurrentComposition();
    const detailComposition = detail && detail.composition ? detail.composition : null;
    const finalComposition = detailComposition || (!(detail && detail.cancelled) ? currentComposition || null : null);
    const finalCompositionId = normalizeId(finalComposition && finalComposition.composition_id);
    const normalizedDetail = {
      source: 'builder-editor-host',
      host_target_id: state.hostTargetId,
      ...(state.hostMode === 'create-composition-open'
        ? {
            composition: finalComposition || undefined,
          }
        : {
            composition: detailComposition || currentComposition || undefined,
          }),
      ...detail,
    };
    if (
      state.hostMode === 'create-composition-open'
      && !state.createdCompositionReadySent
      && state.createdCompositionId
      && finalCompositionId
      && finalCompositionId === state.createdCompositionId
      && !normalizedDetail.cancelled
    ) {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage(
          {
            type: 'builder-host-created-composition-ready',
            detail: {
              source: 'builder-editor-host',
              host_target_id: state.hostTargetId,
              kind: 'composition',
              composition: finalComposition || undefined,
            },
          },
          window.location.origin,
        );
      }
      state.createdCompositionReadySent = true;
      state.createdCompositionId = '';
      state.hostMode = 'idle';
    }
    if (normalizedDetail.cancelled) {
      state.createdCompositionId = '';
      state.createdCompositionReadySent = false;
      state.hostMode = 'idle';
    }
    const payload = {
      type: 'builder-host-close',
      detail: normalizedDetail,
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

  function notifyHostRuntimeReady() {
    const payload = {
      type: 'builder-host-runtime-ready',
      detail: {
        source: 'builder-editor-host',
      },
    };
    if (window.parent && window.parent !== window) {
      window.parent.postMessage(payload, window.location.origin);
    }
  }

  window.addEventListener('message', async (event) => {
    if (event.origin !== window.location.origin) {
      return;
    }
    if (!window.parent || event.source !== window.parent || window.parent === window) {
      return;
    }
    const payload = event.data || {};
    const detail = payload.detail || {};

    if (payload.type === 'builder-host-ping') {
      notifyHostRuntimeReady();
      return;
    }

    if (payload.type === 'builder-host-create-composition') {
      state.hostMode = 'create-composition';
      state.hostKind = 'create-composition';
      state.hostTargetId = 'create-composition';
      state.compositionId = '';
      state.componentId = '';
      state.createdCompositionId = '';
      state.createdCompositionReadySent = false;
      try {
        openCreateCompositionModal();
        setHostStatus(true);
        notifyHostReady({ kind: 'create-composition' });
      } catch (error) {
        showJson('builderOut', { status: 0, data: { ok: false, error: String(error && error.message || error) } });
        notifyHostClose({ kind: 'create-composition', error: String(error && error.message || error) });
        setHostStatus(false, String(error && error.message || error));
      }
      return;
    }

    if (payload.type !== 'builder-host-open') {
      return;
    }

    const kind = String(detail.kind || '').trim();
    const targetId = String(detail.host_target_id || '').trim();
    if (!targetId || (kind !== 'composition' && kind !== 'component')) {
      return;
    }

    if (kind === 'composition') {
      state.compositionId = targetId;
      state.componentId = '';
      state.hostKind = 'composition';
      state.hostTargetId = targetId;
      state.hostMode = 'composition';
    } else {
      state.componentId = targetId;
      state.compositionId = '';
      state.hostKind = 'component';
      state.hostTargetId = targetId;
      state.hostMode = 'component';
    }

    await openRequestedTarget();
  });

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
      return;
    }

    try {
      if (state.hostKind === 'composition') {
        const sourceCompositionId = state.compositionId;
        const editableComposition = await resolveCompositionEditTarget(sourceCompositionId);
        if (!editableComposition) {
          throw new Error('Kompositionen kunde inte hittas.');
        }
        state.compositionId = editableComposition.composition_id;
        await preloadLinkedComponents(editableComposition);
        state.controller.openComposition(editableComposition, 'overview');
      } else if (state.hostKind === 'create-composition') {
        openCreateCompositionModal();
      } else {
        const component = await loadComponentById(state.componentId);
        if (!component) {
          throw new Error('Komponenten kunde inte hittas.');
        }
        await state.controller.openComponentDetailEditor(component.component_id, 'overview');
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
      getCachedComponents: () => getComponentLibraryRuntime().getCachedComponents(),
      getCachedCompositions,
      resolveComponentById,
      prepareLinkedComponentForEdit,
      resolveComponentCategoryThemeKey,
      upsertCachedComponent: (component) => getComponentLibraryRuntime().upsertCachedComponent(component),
      openComponentCreateModal: openBuilderComponentCreateModal,
      showLoading,
      showJson,
      openSimpleModal,
      closeModalById,
      renderComponentPalette: () => getComponentLibraryRuntime().renderPalette(),
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

    if (globalThis.BuilderDishCreateModal && typeof globalThis.BuilderDishCreateModal.bind === 'function') {
      globalThis.BuilderDishCreateModal.bind({
        includeSeedComponents: false,
      });
    }

    notifyHostRuntimeReady();

    if (target.hostTargetId) {
      await openRequestedTarget();
    }
  });
})();