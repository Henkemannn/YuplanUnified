(function () {
  'use strict';

  function normalizeId(value) {
    return String(value || '').trim();
  }

  function create(options) {
    const state = {
      cachedComponents: [],
      loadPromise: null,
      paletteElement: null,
      searchInputElement: null,
      bound: false,
      currentCompositionGetter: typeof options.getCurrentComposition === 'function' ? options.getCurrentComposition : null,
      attachComponent: typeof options.attachComponent === 'function' ? options.attachComponent : null,
      onAttachSuccess: typeof options.onAttachSuccess === 'function' ? options.onAttachSuccess : null,
      callApi: typeof options.callApi === 'function' ? options.callApi : null,
    };

    function getCurrentComposition() {
      return state.currentCompositionGetter ? state.currentCompositionGetter() : null;
    }

    function getCachedComponents() {
      return state.cachedComponents;
    }

    function upsertCachedComponent(component) {
      const componentId = normalizeId(component && component.component_id);
      if (!componentId) {
        return null;
      }
      const next = { ...(component || {}), component_id: componentId };
      const index = state.cachedComponents.findIndex((item) => normalizeId(item && item.component_id) === componentId);
      if (index >= 0) {
        state.cachedComponents[index] = next;
      } else {
        state.cachedComponents.push(next);
      }
      return next;
    }

    function resolveComponentById(componentId) {
      const idValue = normalizeId(componentId);
      if (!idValue) {
        return null;
      }
      return state.cachedComponents.find((item) => normalizeId(item && item.component_id) === idValue) || null;
    }

    function getSearchValue() {
      return state.searchInputElement ? String(state.searchInputElement.value || '').trim() : '';
    }

    function isAttachedToCurrentComposition(componentId) {
      const currentComposition = getCurrentComposition();
      const linked = Array.isArray(currentComposition && currentComposition.components)
        ? currentComposition.components
        : [];
      const targetId = normalizeId(componentId);
      return linked.some((item) => normalizeId(item && item.component_id) === targetId);
    }

    function renderPalette() {
      const palette = state.paletteElement || document.getElementById('builderComponentPalette');
      if (!palette) {
        return;
      }

      const searchValue = getSearchValue().toLowerCase();
      const components = Array.isArray(state.cachedComponents) ? state.cachedComponents : [];
      const composition = getCurrentComposition();
      const attachedIds = new Set(
        Array.isArray(composition && composition.components)
          ? composition.components.map((item) => normalizeId(item && item.component_id))
          : [],
      );

      palette.innerHTML = '';

      if (!components.length) {
        const empty = document.createElement('div');
        empty.className = 'component-palette-empty';
        empty.textContent = 'No reusable components yet';
        palette.appendChild(empty);
        return;
      }

      let renderedCount = 0;

      for (const component of components) {
        const componentId = normalizeId(component && component.component_id);
        if (!componentId) {
          continue;
        }
        const componentName = String((component && (component.component_name || component.canonical_name)) || componentId).trim() || componentId;
        if (searchValue && !componentName.toLowerCase().includes(searchValue) && !componentId.toLowerCase().includes(searchValue)) {
          continue;
        }

        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'component-palette-pill';
        button.dataset.componentId = componentId;
        button.textContent = componentName;
        button.title = attachedIds.has(componentId) ? 'Already included in this dish' : 'Add component to dish';
        if (component && component.primary_recipe_id) {
          button.classList.add('component-palette-pill-has-data');
        }
        if (attachedIds.has(componentId)) {
          button.classList.add('component-palette-pill-included');
          button.disabled = true;
        } else {
          button.addEventListener('click', async () => {
            button.classList.add('component-palette-pill-pick');
            setTimeout(() => button.classList.remove('component-palette-pill-pick'), 260);
            const attachResult = await handleAttach(componentId);
            if (attachResult && attachResult.data && attachResult.data.ok && attachResult.data.composition && state.onAttachSuccess) {
              await state.onAttachSuccess(attachResult.data.composition, componentId, attachResult);
            }
          });
        }

        palette.appendChild(button);
        renderedCount += 1;
      }

      if (!renderedCount) {
        const empty = document.createElement('div');
        empty.className = 'component-palette-empty';
        empty.textContent = searchValue ? 'No components match search' : 'No reusable components yet';
        palette.appendChild(empty);
      }
    }

    async function loadAllComponents() {
      if (state.loadPromise) {
        return state.loadPromise;
      }
      if (!state.callApi) {
        throw new Error('callApi is required');
      }

      state.loadPromise = (async () => {
        const result = await state.callApi('/api/builder/components', { method: 'GET' });
        if (!(result && result.status < 400 && result.data && result.data.ok && Array.isArray(result.data.components))) {
          throw new Error('Could not load components.');
        }
        state.cachedComponents = result.data.components.slice();
        return state.cachedComponents;
      })();

      try {
        return await state.loadPromise;
      } finally {
        state.loadPromise = null;
      }
    }

    function bindPalette(options) {
      state.paletteElement = options && options.paletteElement ? options.paletteElement : state.paletteElement;
      state.searchInputElement = options && options.searchInputElement ? options.searchInputElement : state.searchInputElement;
      state.currentCompositionGetter = options && typeof options.getCurrentComposition === 'function'
        ? options.getCurrentComposition
        : state.currentCompositionGetter;
      state.attachComponent = options && typeof options.attachComponent === 'function'
        ? options.attachComponent
        : state.attachComponent;
      state.onAttachSuccess = options && typeof options.onAttachSuccess === 'function'
        ? options.onAttachSuccess
        : state.onAttachSuccess;

      if (!state.bound) {
        if (state.searchInputElement) {
          state.searchInputElement.addEventListener('input', () => {
            renderPalette();
          });
        }
        state.bound = true;
      }

      return api;
    }

    async function handleAttach(componentId) {
      if (!state.attachComponent) {
        return { status: 0, data: { ok: false, error: 'attach callback unavailable' } };
      }
      return state.attachComponent(componentId);
    }

    const api = {
      bindPalette,
      loadAllComponents,
      renderPalette,
      getCachedComponents,
      resolveComponentById,
      upsertCachedComponent,
      getSearchValue,
      isAttachedToCurrentComposition,
      handleAttach,
    };

    return api;
  }

  globalThis.BuilderComponentLibraryRuntime = Object.freeze({
    create,
  });
})();