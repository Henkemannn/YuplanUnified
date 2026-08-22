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
 * Workspace adapter callbacks (passed in config):
 *   config.loadLibrary: async () => void
 *   config.updateComponentCategoryChipCounts: () => void
 *   config.filterLibraryComponents: (query: string) => void
 *   config.currentComponentSearchQuery: () => string
 *   config.resolveComponentById: (componentId: string) => object | null | Promise<object | null>
 *   config.prepareLinkedComponentForEdit: (componentId: string) => object | null | Promise<object | null>
 *   config.resolveComponentCategoryThemeKey: (component: object) => string
 *   config.showLoading: (targetId: string) => void
 *   config.showJson: (targetId: string, value: any) => void
 *   config.openSimpleModal: (modalId: string) => void
 *   config.closeModalById: (modalId: string) => void
 *   config.renderComponentPalette: () => void
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
    resolveComponentById: config.resolveComponentById || null,
    prepareLinkedComponentForEdit: config.prepareLinkedComponentForEdit || null,
    resolveComponentCategoryThemeKey: config.resolveComponentCategoryThemeKey || null,
    attachExistingComponentToCurrentComposition: config.attachExistingComponentToCurrentComposition || null,
    showLoading: config.showLoading || null,
    showJson: config.showJson || null,
    openSimpleModal: config.openSimpleModal || null,
    closeModalById: config.closeModalById || null,
    renderComponentPalette: config.renderComponentPalette || null,
    notifyHostClose: config.notifyHostClose || null,
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

  const _dishEditorFactory =
    typeof config.dishEditorFactory === "function"
      ? config.dishEditorFactory
      : (typeof createBuilderDishEditor === "function" ? createBuilderDishEditor : null);

  const _sharedStateAccessors = {
    get: (key) => _state[key],
    set: (key, value) => { _state[key] = value; return value; },
  };

  function _openSimpleModal(modalId) {
    if (typeof _callbacks.openSimpleModal === "function") {
      _callbacks.openSimpleModal(modalId);
      return;
    }
    const modal = document.getElementById(String(modalId || ""));
    if (!modal) {
      return;
    }
    modal.classList.remove("hidden");
    modal.removeAttribute("hidden");
    modal.style.display = "";
    modal.removeAttribute("aria-hidden");
    modal.inert = false;
  }

  function _closeModalById(modalId) {
    if (typeof _callbacks.closeModalById === "function") {
      _callbacks.closeModalById(modalId);
      return;
    }
    const modal = document.getElementById(String(modalId || ""));
    if (!modal) {
      return;
    }
    modal.classList.add("hidden");
    modal.removeAttribute("aria-hidden");
    modal.inert = false;
  }

  function _showLoading(targetId) {
    if (typeof _callbacks.showLoading === "function") {
      _callbacks.showLoading(targetId);
    }
  }

  function _showJson(targetId, value) {
    if (typeof _callbacks.showJson === "function") {
      _callbacks.showJson(targetId, value);
    }
  }

  function _notifyHostClose(detail) {
    if (typeof _callbacks.notifyHostClose === "function") {
      _callbacks.notifyHostClose(detail);
    }
  }

  function _clearPendingComponentCreateForComposition() {
    if (typeof config.clearPendingComponentCreateForComposition === "function") {
      config.clearPendingComponentCreateForComposition();
    }
  }

  function _resolveComponentTheme(component) {
    if (typeof _callbacks.resolveComponentCategoryThemeKey === "function") {
      return String(_callbacks.resolveComponentCategoryThemeKey(component) || "neutral");
    }
    return "neutral";
  }

  async function _resolveComponentById(componentId) {
    if (typeof _callbacks.resolveComponentById === "function") {
      return _callbacks.resolveComponentById(componentId);
    }
    return null;
  }

  async function _openLinkedComponentEditor(componentId) {
    const componentIdValue = String(componentId || "").trim();
    if (!componentIdValue || !_componentEditor) {
      return Promise.resolve();
    }

    let targetComponentId = componentIdValue;
    if (typeof _callbacks.prepareLinkedComponentForEdit === "function") {
      const prepared = await _callbacks.prepareLinkedComponentForEdit(componentIdValue);
      if (prepared && prepared.composition) {
        renderCurrentComposition(prepared.composition);
      }
      if (prepared && prepared.component && String(prepared.component.component_id || "").trim()) {
        targetComponentId = String(prepared.component.component_id || "").trim();
      }
    }

    return _componentEditor.openComponentDetailEditor(targetComponentId, "overview");
  }

  function _resolveCanonicalComponent(component) {
    const componentId = String(component && component.component_id || "").trim();
    if (!componentId) {
      return component;
    }

    const resolved = typeof _callbacks.resolveComponentById === "function"
      ? _callbacks.resolveComponentById(componentId)
      : null;
    if (!resolved || typeof resolved.then === "function") {
      return component;
    }

    const canonical = resolved.component || resolved;
    const componentName = String(canonical.component_name || component.component_name || component.component_id || "").trim();
    return {
      ...component,
      ...canonical,
      component_id: componentId,
      component_name: componentName,
    };
  }

  function _compositionHasLinkedComponent(composition, componentId) {
    const compositionId = String(composition && composition.composition_id || "").trim();
    const linkedComponentId = String(componentId || "").trim();
    if (!compositionId || !linkedComponentId) {
      return false;
    }
    if (String((composition && composition.composition_id) || "").trim() !== compositionId) {
      return false;
    }
    return Array.isArray(composition && composition.components)
      ? composition.components.some((item) => String(item && item.component_id || "").trim() === linkedComponentId)
      : false;
  }

  function _normalizeCompositionForRender(composition) {
    if (!composition || !composition.composition_id) {
      return composition;
    }

    return {
      ...composition,
      components: Array.isArray(composition.components)
        ? composition.components.map((component) => _resolveCanonicalComponent(component))
        : [],
    };
  }

  const _componentEditor = _componentEditorFactory
    ? _componentEditorFactory({
        callApi: config.callApi,
        state: _sharedStateAccessors,
        getCachedComponents: config.getCachedComponents,
        getCachedCompositions: config.getCachedCompositions,
        loadLibrary: _callbacks.loadLibrary,
        upsertCachedComponent: config.upsertCachedComponent,
        filterLibraryComponents: _callbacks.filterLibraryComponents,
        updateComponentCategoryChipCounts: _callbacks.updateComponentCategoryChipCounts,
        currentComponentSearchQuery: _callbacks.currentComponentSearchQuery,
        showLoading: config.showLoading,
        showJson: config.showJson,
        closeModalById: config.closeModalById,
        openSimpleModal: config.openSimpleModal,
        resolveComponentById: config.resolveComponentById,
        reopenPendingCompositionForReturn: config.reopenPendingCompositionForReturn,
        attachExistingComponentToCurrentComposition: config.attachExistingComponentToCurrentComposition,
        clearPendingComponentCreateForComposition: config.clearPendingComponentCreateForComposition,
        refreshCurrentCompositionView: config.refreshCurrentCompositionView,
      })
    : null;

  const _dishEditor = _dishEditorFactory
    ? _dishEditorFactory({
        callApi: config.callApi,
        state: _sharedStateAccessors,
        fetchComponentDetailDraft: _componentEditor && typeof _componentEditor.fetchComponentDetailDraft === "function"
          ? _componentEditor.fetchComponentDetailDraft
          : config.fetchComponentDetailDraft,
        dishAllergenLabel: config.dishAllergenLabel,
        showLoading: config.showLoading,
        showJson: config.showJson,
        loadLibrary: _callbacks.loadLibrary,
      })
    : null;

  // ════════════════════════════════════════════════════════════════════════
  // PRIVATE HELPERS
  // ════════════════════════════════════════════════════════════════════════

  function _closeComponentDetailEditorSafe() {
    const activeComponentId = String(_state._activeComponentDetailId || "").trim();
    if (!_state._componentDetailDirty) {
      _closeModalById("componentDetailEditorModal");
      _state._activeComponentDetailId = "";
      _notifyHostClose({ kind: "component", component_id: activeComponentId });
      return Promise.resolve();
    }
    const shouldSave = window.confirm("Save changes before leaving?");
    if (shouldSave) {
      const savePromise = _componentEditor
        ? _componentEditor.saveActiveComponentDetailDraft()
        : Promise.resolve();
      return savePromise.then(() => {
        _closeModalById("componentDetailEditorModal");
        _state._activeComponentDetailId = "";
        _state._componentDetailDirty = false;
        _notifyHostClose({ kind: "component", component_id: activeComponentId });
      });
    }
    const shouldDiscard = window.confirm("Discard changes and close?");
    if (!shouldDiscard) {
      return Promise.resolve();
    }
    _closeModalById("componentDetailEditorModal");
    _state._activeComponentDetailId = "";
    _state._componentDetailDirty = false;
    _notifyHostClose({ kind: "component", component_id: activeComponentId });
    return Promise.resolve();
  }

  function componentsInDisplayOrder(composition) {
    const components = Array.isArray(composition && composition.components) ? composition.components : [];
    return [...components].sort((left, right) => {
      const leftOrder = Number(left.sort_order || 0);
      const rightOrder = Number(right.sort_order || 0);
      if (leftOrder !== rightOrder) {
        return leftOrder - rightOrder;
      }
      const leftName = String(left.component_name || left.component_id || "").toLowerCase();
      const rightName = String(right.component_name || right.component_id || "").toLowerCase();
      const nameCompare = leftName.localeCompare(rightName, undefined, { sensitivity: "base" });
      if (nameCompare !== 0) {
        return nameCompare;
      }
      return String(left.component_id || "").localeCompare(String(right.component_id || ""));
    });
  }

  function renderDishOverviewKlossPreview(composition) {
    const previewList = compositionRoot.querySelector("#dishOverviewKlossPreview");
    if (!previewList) {
      return;
    }

    previewList.innerHTML = "";
    const components = componentsInDisplayOrder(_normalizeCompositionForRender(composition));

    if (components.length === 0) {
      const li = document.createElement("li");
      li.className = "component-build-surface-empty";
      li.textContent = "Inga komponenter ännu.";
      previewList.appendChild(li);
      return;
    }

    for (const component of components) {
      const componentIdValue = String(component.component_id || "");
      const canonicalComponent = _resolveCanonicalComponent(component);
      const displayedName = String((canonicalComponent && canonicalComponent.component_name) || component.component_name || component.component_id || "");
      const themeKey = _resolveComponentTheme(canonicalComponent || component);
      const li = document.createElement("li");
      li.className = "component-list-item";

      const card = document.createElement("article");
      card.className = "builder-component-card builder-component-card-compact dish-linked-component-card";
      card.classList.add("builder-component-card-theme-" + themeKey);

      const surface = document.createElement("div");
      surface.className = "builder-component-card-surface";

      const name = document.createElement("div");
      name.className = "component-library-card-name";
      name.textContent = displayedName;

      surface.appendChild(name);
      card.appendChild(surface);
      card.addEventListener("click", async () => {
        await _openLinkedComponentEditor(componentIdValue);
      });
      li.appendChild(card);
      previewList.appendChild(li);
    }
  }

  function renderDishComponentsPanel(composition) {
    const list = compositionRoot.querySelector("#builderComponentsList");
    if (!list) {
      return;
    }

    list.innerHTML = "";
    const components = componentsInDisplayOrder(_normalizeCompositionForRender(composition));
    if (components.length === 0) {
      const li = document.createElement("li");
      li.className = "component-build-surface-empty";
      li.textContent = "Inga komponenter ännu. Använd Lägg till komponent för att börja bygga rätten.";
      list.appendChild(li);
      return;
    }

    for (const component of components) {
      const componentIdValue = String(component.component_id || "");
      const canonicalComponent = typeof _callbacks.resolveComponentById === "function"
        ? _callbacks.resolveComponentById(componentIdValue)
        : null;
      const canonicalResolved = canonicalComponent && typeof canonicalComponent.then !== "function"
        ? (canonicalComponent.component || canonicalComponent)
        : null;
      const displayedName = String((canonicalResolved && canonicalResolved.component_name) || component.component_name || component.component_id || "");
      const displayedCategory = String((canonicalResolved && canonicalResolved.category) || component.category || "");
      const themeKey = _resolveComponentTheme(canonicalResolved || component);
      const li = document.createElement("li");
      li.className = "component-list-item";
      if (!String(component.role || "").trim()) {
        li.classList.add("component-list-item-missing-role");
      }

      const card = document.createElement("article");
      card.className = "builder-component-card builder-component-card-compact dish-linked-component-card";
      card.dataset.componentId = componentIdValue;
      card.classList.add("builder-component-card-theme-" + themeKey);

      const surface = document.createElement("button");
      surface.type = "button";
      surface.className = "builder-component-card-surface";

      const name = document.createElement("div");
      name.className = "component-library-card-name";
      name.textContent = displayedName;

      const right = document.createElement("div");
      right.className = "component-row-right";

      const overflow = document.createElement("details");
      overflow.className = "component-overflow";
      const overflowSummary = document.createElement("summary");
      overflowSummary.textContent = "...";
      overflowSummary.addEventListener("click", (event) => {
        event.stopPropagation();
      });
      const menu = document.createElement("div");
      menu.className = "component-overflow-menu";
      const openComponentBtn = document.createElement("button");
      openComponentBtn.type = "button";
      openComponentBtn.textContent = "Öppna komponent";
      openComponentBtn.addEventListener("click", async () => {
        overflow.removeAttribute("open");
        await _openLinkedComponentEditor(componentIdValue);
      });
      menu.appendChild(openComponentBtn);
      overflow.appendChild(overflowSummary);
      overflow.appendChild(menu);
      right.appendChild(overflow);

      surface.appendChild(name);
      surface.appendChild(right);
      surface.addEventListener("click", async () => {
        await _openLinkedComponentEditor(componentIdValue);
      });

      card.appendChild(surface);
      li.appendChild(card);
      list.appendChild(li);
    }
  }

  function renderCurrentComposition(composition) {
    if (!composition || !composition.composition_id) {
      return;
    }
    const normalizedComposition = _normalizeCompositionForRender(composition);
    _state.currentBuilderComposition = normalizedComposition;
    _state.currentBuilderDishTab = _state.currentBuilderDishTab || "overview";
    if (_dishEditor) {
      _dishEditor.syncDishModalHeader(normalizedComposition);
      _dishEditor.syncDishOverviewInputs(normalizedComposition);
      _dishEditor.syncDishMenuNameVisibility();
    }
    renderDishOverviewKlossPreview(normalizedComposition);
    renderDishComponentsPanel(normalizedComposition);
    if (_dishEditor) {
      _dishEditor.setDishOverviewStatus("");
    }
    setDishBuilderTab(_state.currentBuilderDishTab);
  }

  function openCompositionModal() {
    const builderOut = compositionRoot.querySelector("#builderOut");
    if (builderOut) {
      builderOut.textContent = "";
    }
    _openSimpleModal("resolveModal");
    const modal = compositionRoot;
    modal.classList.remove("hidden");
    modal.removeAttribute("hidden");
    modal.style.display = "";
    modal.removeAttribute("aria-hidden");
    modal.inert = false;
  }

  function closeCompositionModal() {
    _state.currentDishAllergenSummaryToken += 1;
    _state.currentDishCalculationSummaryToken += 1;
    closeDishComponentOverflowMenus();
    const activeCompositionId = String(_state.currentBuilderComposition?.composition_id || "").trim();
    _closeModalById("componentDetailEditorModal");
    _closeModalById("resolveModal");
    _state.currentBuilderComposition = null;
    _state.currentBuilderDishTab = "overview";
    _notifyHostClose({ kind: "composition", composition_id: activeCompositionId });
  }

  async function _returnComponentDetailToDish() {
    const componentId = String(_state._activeComponentDetailId || "").trim();
    const compositionId = String(_state.pendingComponentCreateForCompositionId || "").trim();
    const pendingComponentId = String(_state.pendingComponentCreateComponentId || "").trim();
    const currentCompositionId = String(_state.currentBuilderComposition?.composition_id || "").trim();
    const isNewFromDish = Boolean(compositionId && pendingComponentId && componentId && componentId === pendingComponentId);
    if (!componentId || (!compositionId && !currentCompositionId)) {
      return;
    }

    if (_state._componentDetailDirty) {
      if (_componentEditor) {
        await _componentEditor.saveActiveComponentDetailDraft();
      }
    }
    if (_state._componentDetailDirty) {
      return;
    }

    const shouldAttachToDish = Boolean(isNewFromDish);
    if (!shouldAttachToDish) {
      _state._activeComponentDetailId = "";
      _closeModalById("componentDetailEditorModal");
      if (_state.currentBuilderComposition) {
        renderCurrentComposition(_state.currentBuilderComposition);
      }
      return;
    }

    const pendingReturnTab = String(_state.pendingComponentCreateReturnTab || "components").trim() || "components";

    const currentComposition = _state.currentBuilderComposition;
    const alreadyLinked = _compositionHasLinkedComponent(currentComposition, componentId) && String((currentComposition && currentComposition.composition_id) || "").trim() === compositionId;
    if (alreadyLinked) {
      const returnedComposition = currentComposition;
      _state.currentBuilderComposition = returnedComposition;
      _state._activeComponentDetailId = "";
      _state._componentDetailDirty = false;
      _closeModalById("componentDetailEditorModal");
      openCompositionModal();
      renderCurrentComposition(returnedComposition);
      setDishBuilderTab(pendingReturnTab);
      _clearPendingComponentCreateForComposition();
      return;
    }

    const attachComponent = typeof _callbacks.attachExistingComponentToCurrentComposition === "function"
      ? _callbacks.attachExistingComponentToCurrentComposition
      : null;
    const attachResult = attachComponent
      ? await attachComponent(componentId, compositionId)
      : null;

    if (!(attachResult && attachResult.data && attachResult.data.ok && attachResult.data.composition)) {
      _showJson("componentDetailOut", attachResult || { status: 0, data: { ok: false, error: "attach_failed" } });
      return;
    }

    const returnedComposition = attachResult.data.composition;
    _state.currentBuilderComposition = returnedComposition;
    _state._activeComponentDetailId = "";
    _state._componentDetailDirty = false;
    _closeModalById("componentDetailEditorModal");
    openCompositionModal();
    renderCurrentComposition(returnedComposition);
    setDishBuilderTab(pendingReturnTab);
    _clearPendingComponentCreateForComposition();
  }

  function closeDishComponentOverflowMenus(exceptElement = null) {
    const panel = compositionRoot.querySelector("#dishComponentsPanel");
    if (!panel) {
      return false;
    }

    const keepOpen = exceptElement instanceof Element
      ? exceptElement.closest(".component-overflow")
      : null;

    let didCloseAny = false;
    const menus = panel.querySelectorAll(".component-overflow");
    for (const menu of menus) {
      if (!(menu instanceof HTMLElement)) {
        continue;
      }
      if (keepOpen && menu === keepOpen) {
        continue;
      }
      if (menu.hasAttribute("open")) {
        menu.removeAttribute("open");
        didCloseAny = true;
      }
    }

    return didCloseAny;
  }

  function setDishBuilderTab(tabValue) {
    const key = String(tabValue || "").trim().toLowerCase();
    const nextTab = key === "components" || key === "allergens" || key === "calculation" || key === "overview"
      ? key
      : "overview";
    _state.currentBuilderDishTab = nextTab;
    if (nextTab !== "components") {
      closeDishComponentOverflowMenus();
    }

    const tabButtons = Array.from(compositionRoot.querySelectorAll("[data-dish-tab]"));
    const tabPanels = Array.from(compositionRoot.querySelectorAll("[data-dish-panel]"));
    tabButtons.forEach((button) => {
      const tab = String(button.getAttribute("data-dish-tab") || "").trim().toLowerCase();
      const active = tab === nextTab;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    tabPanels.forEach((panel) => {
      const tab = String(panel.getAttribute("data-dish-panel") || "").trim().toLowerCase();
      const active = tab === nextTab;
      panel.hidden = !active;
      panel.classList.toggle("hidden", !active);
      panel.setAttribute("aria-hidden", active ? "false" : "true");
      if (active) {
        panel.removeAttribute("hidden");
      } else {
        panel.setAttribute("hidden", "hidden");
      }
    });

    if (nextTab === "calculation" && _dishEditor) {
      _dishEditor.loadDishCalculationSummaryForCurrentComposition().catch(() => {
        _dishEditor.renderDishCalculationSummaryFailure();
      });
    }

    if (nextTab === "allergens" && _dishEditor) {
      _dishEditor.loadDishAllergenSummaryForCurrentComposition().catch(() => {
        _dishEditor.renderDishAllergenSummaryFailure();
      });
    }
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
        await _returnComponentDetailToDish();
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
        closeCompositionModal();
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
        if (_dishEditor) {
          await _dishEditor.saveDishOverviewMetadata();
        }
      });
    }

    // ── Dish modal: overview name clears status on input ─────────────
    const dishOverviewNameInput = compositionRoot.querySelector("#dishOverviewName");
    if (dishOverviewNameInput) {
      dishOverviewNameInput.addEventListener("input", () => {
        if (typeof setDishOverviewStatus === "function") {
          setDishOverviewStatus("");
        }
        if (_dishEditor) {
          _dishEditor.setDishOverviewStatus("");
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
        if (_dishEditor) {
          _dishEditor.setDishOverviewStatus("");
        }
      });
    }

    const dishOverviewUseCustomMenuNameInput = compositionRoot.querySelector("#dishOverviewUseCustomMenuName");
    if (dishOverviewUseCustomMenuNameInput) {
      dishOverviewUseCustomMenuNameInput.addEventListener("change", () => {
        if (_dishEditor && typeof _dishEditor.syncDishMenuNameVisibility === "function") {
          _dishEditor.syncDishMenuNameVisibility();
        }
        if (_dishEditor) {
          _dishEditor.setDishOverviewStatus("");
        }
      });
    }

    const dishOverviewMenuNameInput = compositionRoot.querySelector("#dishOverviewMenuName");
    if (dishOverviewMenuNameInput) {
      dishOverviewMenuNameInput.addEventListener("input", () => {
        if (_dishEditor) {
          _dishEditor.setDishOverviewStatus("");
        }
      });
    }

    // ── Dish modal: backdrop click to close ───────────────────────────
    compositionRoot.addEventListener("click", (event) => {
      if (event.target === compositionRoot) {
        closeCompositionModal();
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
      renderCurrentComposition(composition);
      setDishBuilderTab(initialTab || "overview");
      openCompositionModal();
    },

    /**
     * Close the Dish (composition) modal.
     */
    closeComposition() {
      closeCompositionModal();
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

    getDishEditor() {
      return _dishEditor;
    },

    /**
     * Render the builder panel (component list) for a composition.
     * @param {object} composition
     */
    renderBuilderPanel(composition) {
      renderCurrentComposition(composition);
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
      _state.pendingComponentCreateForCompositionId = _state.currentBuilderComposition && _state.currentBuilderComposition.composition_id
        ? String(_state.currentBuilderComposition.composition_id || "").trim() || null
        : null;
      _state.pendingComponentCreateForCompositionName = _state.currentBuilderComposition && _state.currentBuilderComposition.composition_name
        ? String(_state.currentBuilderComposition.composition_name || "").trim() || null
        : null;
      _state.pendingComponentCreateReturnTab = "components";
    },

    /**
     * Clear pending composition create context.
     */
    clearPendingComponentCreate() {
      _state.pendingComponentCreateForCompositionId = null;
      _state.pendingComponentCreateForCompositionName = null;
      _state.pendingComponentCreateReturnTab = "components";
    },

    /**
     * Attach an existing component to the current composition.
     * @param {string} componentId
     */
    attachExistingComponentToCurrentComposition(componentId) {
      if (typeof _callbacks.attachExistingComponentToCurrentComposition === "function") {
        return _callbacks.attachExistingComponentToCurrentComposition(componentId);
      }
      return Promise.resolve({ status: 0, data: { ok: false, error: "attach callback unavailable" } });
    },

    /**
     * Re-render the component palette (addComponentModal).
     */
    renderComponentPalette() {
      if (typeof _callbacks.renderComponentPalette === "function") {
        _callbacks.renderComponentPalette();
      }
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
      if (typeof _callbacks.renderComponentPalette === "function") {
        _callbacks.renderComponentPalette();
      }
    },

    /**
     * Re-render the current composition from the canonical cache.
     * This is only used after an explicit component save or attach action.
     */
    refreshCurrentComposition() {
      if (_state.currentBuilderComposition) {
        renderCurrentComposition(_state.currentBuilderComposition);
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
