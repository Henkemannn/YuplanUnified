/**
 * Builder Modal Controller — shared initialization, lifecycle, and public API
 * for the Dish (resolveModal) and Component (componentDetailEditorModal) editors.
 *
 * This controller owns:
 *   - The DOM root references (compositionRoot, componentRoot)
 *   - The duplicate-initialization guard
 *   - All modal-specific event listeners
 *   - The workspace callback contract
 *   - The public API used by Builder Workspace and future consumers
 *
 * Implementation functions (renderBuilderPanel, openComponentDetailEditor, etc.)
 * remain in builder.js as globals and are called through here. This is an
 * EXTRACTION, not a rewrite — no logic is duplicated.
 *
 * Globals from builder.js (must be loaded on same page, called via delegation):
 *   openBuilderModalForComposition, closeResolveModal, openComponentDetailEditor
 *   renderBuilderPanel, setDishBuilderTab, closeDishComponentOverflowMenus
 *   setPendingComponentCreateForCurrentComposition, clearPendingComponentCreateForComposition
 *   attachExistingComponentToCurrentComposition, saveDishOverviewMetadata
 *   saveActiveComponentDetailDraft, closeModalById, openSimpleModal, closeSimpleModal
 *   setComponentDetailTab, markComponentDetailDirty, cleanComponentInlineName
 *   addComponentDetailTagsFromInput, removeComponentDetailTag
 *   readRecipeIngredientRowsFromForm, defaultRecipeIngredientRow
 *   renderRecipeIngredientRows, syncCalculationRowsFromRecipeRows
 *   reopenPendingCompositionForReturn, updateComponentDetailReturnAction
 *   deleteComponentFromLibrary, renderComponentPalette, loadReusableComponents
 *   currentBuilderComposition (mutable global), pendingComponentCreateForCompositionId
 *   _activeComponentDetailId (mutable global), _componentDetailDirty (mutable global)
 *
 * Workspace adapter callbacks (passed in config):
 *   config.loadLibrary: async () => void
 *   config.updateComponentCategoryChipCounts: () => void
 *   config.filterLibraryComponents: (query: string) => void
 *   config.currentComponentSearchQuery: () => string
 *
 * @param {{
 *   compositionRoot: Element,
 *   componentRoot: Element,
 *   loadLibrary: function,
 *   updateComponentCategoryChipCounts: function,
 *   filterLibraryComponents: function,
 *   currentComponentSearchQuery: function
 * }} config
 * @returns {object} Public API
 */
function createBuilderModalController(config) {
  if (!config || !config.compositionRoot || !config.componentRoot) {
    throw new Error("createBuilderModalController: compositionRoot and componentRoot are required");
  }

  // ── Public dom roots ──────────────────────────────────────────────────
  const compositionRoot = config.compositionRoot;
  const componentRoot = config.componentRoot;

  // ── Workspace callbacks ───────────────────────────────────────────────
  const _callbacks = {
    loadLibrary: config.loadLibrary || null,
    updateComponentCategoryChipCounts: config.updateComponentCategoryChipCounts || null,
    filterLibraryComponents: config.filterLibraryComponents || null,
    currentComponentSearchQuery: config.currentComponentSearchQuery || null,
  };

  const _state = {
    currentBuilderComposition: null,
    currentBuilderDishTab: "overview",
    currentDishAllergenSummaryToken: 0,
    currentDishCalculationSummaryToken: 0,
    selectedComponentId: null,
    pendingComponentCreateForCompositionId: null,
    pendingComponentCreateForCompositionName: null,
    pendingComponentCreateReturnTab: "components",
    _activeComponentDetailId: "",
    _activeComponentDetailTab: "overview",
    _componentDetailDirty: false,
    _componentDetailTagsDraft: [],
  };

  if (config.initialState && typeof config.initialState === "object") {
    Object.assign(_state, config.initialState);
  }

  // ── Duplicate-initialization guard ────────────────────────────────────
  let _listenersAttached = false;

  // ── Component editor instance ─────────────────────────────────────────
  const _componentEditorFactory =
    typeof config.componentEditorFactory === "function"
      ? config.componentEditorFactory
      : (typeof createBuilderComponentEditor === "function" ? createBuilderComponentEditor : null);

  const _componentEditor = _componentEditorFactory
    ? _componentEditorFactory({
        callApi: config.callApi,
        state: {
          get: (key) => _state[key],
          set: (key, value) => { _state[key] = value; return value; },
        },
        getCachedComponents: config.getCachedComponents,
        getCachedCompositions: config.getCachedCompositions,
        loadLibrary: _callbacks.loadLibrary,
        filterLibraryComponents: _callbacks.filterLibraryComponents,
        updateComponentCategoryChipCounts: _callbacks.updateComponentCategoryChipCounts,
        currentComponentSearchQuery: _callbacks.currentComponentSearchQuery,
        showLoading: config.showLoading,
        showJson: config.showJson,
        closeModalById: config.closeModalById,
        openSimpleModal: config.openSimpleModal,
        reopenPendingCompositionForReturn: config.reopenPendingCompositionForReturn,
        attachExistingComponentToCurrentComposition: config.attachExistingComponentToCurrentComposition,
        clearPendingComponentCreateForComposition: config.clearPendingComponentCreateForComposition,
      })
    : null;

  // ════════════════════════════════════════════════════════════════════════
  // PRIVATE HELPERS
  // ════════════════════════════════════════════════════════════════════════

  function _closeComponentDetailEditorSafe() {
    if (!_state._componentDetailDirty) {
      closeModalById("componentDetailEditorModal");
      _state._activeComponentDetailId = "";
      return Promise.resolve();
    }
    const shouldSave = window.confirm("Save changes before leaving?");
    if (shouldSave) {
      const savePromise = _componentEditor
        ? _componentEditor.saveActiveComponentDetailDraft()
        : Promise.resolve();
      return savePromise.then(() => {
        closeModalById("componentDetailEditorModal");
        _state._activeComponentDetailId = "";
        _state._componentDetailDirty = false;
      });
    }
    const shouldDiscard = window.confirm("Discard changes and close?");
    if (!shouldDiscard) {
      return Promise.resolve();
    }
    closeModalById("componentDetailEditorModal");
    _state._activeComponentDetailId = "";
    _state._componentDetailDirty = false;
    return Promise.resolve();
  }

  // ════════════════════════════════════════════════════════════════════════
  // EVENT LISTENER REGISTRATION  (idempotent — runs once per controller)
  // ════════════════════════════════════════════════════════════════════════

  function _attachListeners() {
    if (_listenersAttached) {
      return;
    }
    _listenersAttached = true;

    // ── Component detail: tab navigation ──────────────────────────────
    const componentDetailTabsEl = componentRoot.querySelector("#componentDetailTabs");
    if (componentDetailTabsEl) {
      componentDetailTabsEl.addEventListener("click", (event) => {
        const target = event.target instanceof Element
          ? event.target.closest("[data-component-tab]")
          : null;
        if (!target) {
          return;
        }
        if (_componentEditor) _componentEditor.setComponentDetailTab(String(target.getAttribute("data-component-tab") || "overview"));
      });
    }

    // ── Component detail: save changes ────────────────────────────────
    const componentDetailSaveBtn = componentRoot.querySelector("#componentDetailSaveChanges");
    if (componentDetailSaveBtn) {
      componentDetailSaveBtn.addEventListener("click", async () => {
        if (_componentEditor) await _componentEditor.saveActiveComponentDetailDraft();
      });
    }

    // ── Component detail: close / back ────────────────────────────────
    const componentDetailCloseBtn = componentRoot.querySelector("#componentDetailEditorClose");
    if (componentDetailCloseBtn) {
      componentDetailCloseBtn.addEventListener("click", async () => {
        await _closeComponentDetailEditorSafe();
      });
    }

    // ── Component detail: return-to-dish ──────────────────────────────
    const componentDetailReturnBtn = componentRoot.querySelector("#componentDetailReturnToDishBtn");
    if (componentDetailReturnBtn) {
      componentDetailReturnBtn.addEventListener("click", async () => {
        const componentId = String(_state._activeComponentDetailId || "").trim();
        if (!componentId || !_state.pendingComponentCreateForCompositionId) {
          return;
        }
        if (_state._componentDetailDirty) {
          if (_componentEditor) await _componentEditor.saveActiveComponentDetailDraft();
        }
        if (_state._componentDetailDirty) {
          return;
        }
        const reopenedComposition = await reopenPendingCompositionForReturn();
        if (!reopenedComposition) {
          showJson("componentDetailOut", { status: 0, data: { ok: false, error: "pending composition not found" } });
          return;
        }
        const attachResult = await attachExistingComponentToCurrentComposition(componentId);
        if (attachResult && attachResult.data && attachResult.data.ok && attachResult.data.composition) {
          if (_callbacks.loadLibrary) {
            await _callbacks.loadLibrary();
          }
          clearPendingComponentCreateForComposition();
          closeModalById("componentDetailEditorModal");
          _state._activeComponentDetailId = "";
          _state._componentDetailDirty = false;
        }
      });
    }

    // ── Component detail: clean name ──────────────────────────────────
    const overviewCleanBtn = componentRoot.querySelector("#componentDetailOverviewClean");
    if (overviewCleanBtn) {
      overviewCleanBtn.addEventListener("click", () => {
        const nameInput = componentRoot.querySelector("#componentDetailOverviewName");
        if (!nameInput) {
          return;
        }
        nameInput.value = _componentEditor ? _componentEditor.cleanComponentInlineName(nameInput.value) : nameInput.value;
        if (_componentEditor) _componentEditor.markComponentDetailDirty();
      });
    }

    // ── Component detail: category change (dirty) ─────────────────────
    const overviewCategoryInput = componentRoot.querySelector("#componentDetailOverviewCategory");
    if (overviewCategoryInput) {
      overviewCategoryInput.addEventListener("change", () => {
        if (_componentEditor) _componentEditor.markComponentDetailDirty();
      });
    }

    // ── Component detail: delete component ────────────────────────────
    const overviewDeleteBtn = componentRoot.querySelector("#componentDetailOverviewDelete");
    if (overviewDeleteBtn) {
      overviewDeleteBtn.addEventListener("click", async () => {
        const idValue = String(_state._activeComponentDetailId || "").trim();
        if (!idValue) {
          return;
        }
        const nameInput = componentRoot.querySelector("#componentDetailOverviewName");
        const componentName = nameInput ? String(nameInput.value || "") : idValue;
        if (_componentEditor) await _componentEditor.deleteComponentFromLibrary(idValue, componentName);
      });
    }

    // ── Component detail: tags input ──────────────────────────────────
    const tagsInput = componentRoot.querySelector("#componentDetailTagsInput");
    if (tagsInput) {
      tagsInput.addEventListener("keydown", (event) => {
        if (event.key !== "Enter" && event.key !== ",") {
          return;
        }
        event.preventDefault();
        const didAdd = _componentEditor ? _componentEditor.addComponentDetailTagsFromInput(tagsInput.value) : false;
        tagsInput.value = "";
        if (didAdd) {
          if (_componentEditor) _componentEditor.markComponentDetailDirty();
        }
      });
      tagsInput.addEventListener("blur", () => {
        const didAdd = _componentEditor ? _componentEditor.addComponentDetailTagsFromInput(tagsInput.value) : false;
        tagsInput.value = "";
        if (didAdd) {
          if (_componentEditor) _componentEditor.markComponentDetailDirty();
        }
      });
    }

    // ── Component detail: tags chips remove ───────────────────────────
    const tagsChips = componentRoot.querySelector("#componentDetailTagsChips");
    if (tagsChips) {
      tagsChips.addEventListener("click", (event) => {
        const target = event.target instanceof Element ? event.target : null;
        if (!target) {
          return;
        }
        const removeBtn = target.closest("[data-remove-tag]");
        if (!removeBtn) {
          return;
        }
        const tagValue = String(removeBtn.getAttribute("data-remove-tag") || "");
        if (_componentEditor && _componentEditor.removeComponentDetailTag(tagValue)) {
          _componentEditor.markComponentDetailDirty();
        }
      });
    }

    // ── Component detail: add recipe ingredient row ───────────────────
    const recipeAddRowBtn = componentRoot.querySelector("#componentDetailRecipeAddRow");
    if (recipeAddRowBtn) {
      recipeAddRowBtn.addEventListener("click", () => {
        if (!_componentEditor) return;
        const existingRows = _componentEditor.readRecipeIngredientRowsFromForm();
        existingRows.push(_componentEditor.defaultRecipeIngredientRow());
        _componentEditor.renderRecipeIngredientRows(existingRows);
        _componentEditor.markComponentDetailDirty();
      });
    }

    // ── Component detail: sync calc rows from recipe ──────────────────
    const calcSyncRowsBtn = componentRoot.querySelector("#componentDetailCalcSyncRows");
    if (calcSyncRowsBtn) {
      calcSyncRowsBtn.addEventListener("click", () => {
        if (_componentEditor) _componentEditor.syncCalculationRowsFromRecipeRows();
        if (_componentEditor) _componentEditor.markComponentDetailDirty();
      });
    }

    // ── Component detail: dirty tracking on any input/change ──────────
    componentRoot.addEventListener("input", () => {
      if (_componentEditor) _componentEditor.markComponentDetailDirty();
    });
    componentRoot.addEventListener("change", () => {
      if (_componentEditor) _componentEditor.markComponentDetailDirty();
    });

    // ── Component detail: backdrop click to close ─────────────────────
    componentRoot.addEventListener("click", async (event) => {
      if (event.target === componentRoot) {
        await _closeComponentDetailEditorSafe();
      }
    });

    // ── Dish modal: close / done button ───────────────────────────────
    const resolveCancelBtn = compositionRoot.querySelector("#resolveCancel");
    if (resolveCancelBtn) {
      resolveCancelBtn.addEventListener("click", () => {
        closeModalById("resolveModal");
        closeResolveModal();
      });
    }

    // ── Dish modal: tab navigation ────────────────────────────────────
    const dishTabButtons = compositionRoot.querySelectorAll("[data-dish-tab]");
    dishTabButtons.forEach((button) => {
      button.addEventListener("click", () => {
        setDishBuilderTab(button.getAttribute("data-dish-tab") || "overview");
      });
    });

    // ── Dish modal: overview save ─────────────────────────────────────
    const dishOverviewSaveBtn = compositionRoot.querySelector("#btnDishOverviewSave");
    if (dishOverviewSaveBtn) {
      dishOverviewSaveBtn.addEventListener("click", async () => {
        await saveDishOverviewMetadata();
      });
    }

    // ── Dish modal: overview name clears status on input ─────────────
    const dishOverviewNameInput = compositionRoot.querySelector("#dishOverviewName");
    if (dishOverviewNameInput) {
      dishOverviewNameInput.addEventListener("input", () => {
        if (typeof setDishOverviewStatus === "function") {
          setDishOverviewStatus("");
        }
      });
    }

    // ── Dish modal: overview category clears status on change ─────────
    const dishOverviewCategorySelect = compositionRoot.querySelector("#dishOverviewCategorySelect");
    if (dishOverviewCategorySelect) {
      dishOverviewCategorySelect.addEventListener("change", () => {
        if (typeof setDishOverviewStatus === "function") {
          setDishOverviewStatus("");
        }
      });
    }

    // ── Dish modal: backdrop click to close ───────────────────────────
    compositionRoot.addEventListener("click", (event) => {
      if (event.target === compositionRoot) {
        closeModalById("resolveModal");
        closeResolveModal();
      }
    });

    // ── Dish modal: close overflow menus on outside click ─────────────
    document.addEventListener("click", (event) => {
      const panel = compositionRoot.querySelector("#dishComponentsPanel");
      if (!panel || panel.classList.contains("hidden") || panel.hasAttribute("hidden")) {
        return;
      }
      const target = event.target;
      if (!(target instanceof Element)) {
        closeDishComponentOverflowMenus();
        return;
      }
      if (target.closest("#dishComponentsPanel .component-overflow")) {
        return;
      }
      closeDishComponentOverflowMenus();
    });
  }

  // ════════════════════════════════════════════════════════════════════════
  // INITIALIZE
  // ════════════════════════════════════════════════════════════════════════

  _attachListeners();

  // ════════════════════════════════════════════════════════════════════════
  // PUBLIC API
  // ════════════════════════════════════════════════════════════════════════

  return {
    /**
     * Open the Dish (composition) modal.
     * @param {object} composition
     * @param {string} [initialTab]
     */
    openComposition(composition, initialTab) {
      openBuilderModalForComposition(composition, initialTab || "overview");
    },

    /**
     * Close the Dish (composition) modal.
     */
    closeComposition() {
      closeResolveModal();
    },

    /**
     * Open the Component detail editor.
     * @param {string} componentId
     * @param {string} [initialTab]
     */
    openComponentDetailEditor(componentId, initialTab) {
      if (_componentEditor) return _componentEditor.openComponentDetailEditor(componentId, initialTab);
      return Promise.resolve();
    },

    getComponentEditor() {
      return _componentEditor;
    },

    /**
     * Render the builder panel (component list) for a composition.
     * @param {object} composition
     */
    renderBuilderPanel(composition) {
      renderBuilderPanel(composition);
    },

    /**
     * Set the active dish tab.
     * @param {string} tabValue
     */
    setDishBuilderTab(tabValue) {
      setDishBuilderTab(tabValue);
    },

    /**
     * Set pending composition create context before creating a new component
     * from within a dish. Uses current composition if no args provided.
     */
    setPendingComponentCreate() {
      setPendingComponentCreateForCurrentComposition();
    },

    /**
     * Clear pending composition create context.
     */
    clearPendingComponentCreate() {
      clearPendingComponentCreateForComposition();
    },

    /**
     * Attach an existing component to the current composition.
     * @param {string} componentId
     */
    attachExistingComponentToCurrentComposition(componentId) {
      return attachExistingComponentToCurrentComposition(componentId);
    },

    /**
     * Re-render the component palette (addComponentModal).
     */
    renderComponentPalette() {
      renderComponentPalette();
    },

    /**
     * Close dish component overflow menus.
     * @param {Element} [exceptElement]
     */
    closeDishComponentOverflowMenus(exceptElement) {
      return closeDishComponentOverflowMenus(exceptElement);
    },

    /**
     * Get the current composition (read-only).
     * @returns {object|null}
     */
    getCurrentComposition() {
      return _state.currentBuilderComposition;
    },

    /**
     * Read a modal-owned state value.
     * @param {string} key
     * @returns {*}
     */
    getState(key) {
      return _state[key];
    },

    /**
     * Update a modal-owned state value.
     * @param {string} key
     * @param {*} value
     * @returns {*}
     */
    setState(key, value) {
      _state[key] = value;
      return value;
    },

    /**
     * Called after reusable components cache is refreshed by workspace.
     * Re-renders palette and composition list.
     */
    onReusableComponentsRefreshed() {
      renderComponentPalette();
      if (_state.currentBuilderComposition) {
        renderBuilderPanel(_state.currentBuilderComposition);
      }
    },

    /**
     * Get the workspace callbacks registered with this controller.
     * Used by builder.js adapter for callback wiring.
     */
    getCallbacks() {
      return _callbacks;
    },

    /**
     * Whether modal event listeners have been attached.
     * Prevents duplicate registration if called multiple times.
     */
    isInitialized() {
      return _listenersAttached;
    },
  };
}
