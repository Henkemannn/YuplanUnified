/**
 * Canonical Component editor implementation for Builder.
 * All Component-specific behavior lives here.
 */
function createBuilderComponentEditor(config) {
  if (!config || typeof config.callApi !== "function") {
    throw new Error("createBuilderComponentEditor: callApi is required");
  }

  const callApi = config.callApi;
  const _getState = (key) => config.state.get(key);
  const _setState = (key, value) => { config.state.set(key, value); return value; };

  function _getCachedComponents() {
    return typeof config.getCachedComponents === "function" ? config.getCachedComponents() : [];
  }
  function _getCachedCompositions() {
    return typeof config.getCachedCompositions === "function" ? config.getCachedCompositions() : [];
  }
  async function _resolveComponentById(componentId) {
    if (typeof config.resolveComponentById === "function") {
      return config.resolveComponentById(componentId);
    }
    return null;
  }
  function _loadLibrary() {
    return typeof config.loadLibrary === "function" ? config.loadLibrary() : Promise.resolve();
  }
  function _upsertCachedComponent(component) {
    if (typeof config.upsertCachedComponent === "function") {
      return config.upsertCachedComponent(component);
    }
    return null;
  }
  function _filterLibraryComponents(q) {
    if (typeof config.filterLibraryComponents === "function") {
      config.filterLibraryComponents(q);
    }
  }
  function _updateComponentCategoryChipCounts() {
    if (typeof config.updateComponentCategoryChipCounts === "function") {
      config.updateComponentCategoryChipCounts();
    }
  }
  function _currentComponentSearchQuery() {
    return typeof config.currentComponentSearchQuery === "function"
      ? config.currentComponentSearchQuery()
      : "";
  }
  function _closeModalById(id) {
    if (typeof config.closeModalById === "function") {
      config.closeModalById(id);
    }
  }
  function _openSimpleModal(id) {
    if (typeof config.openSimpleModal === "function") {
      config.openSimpleModal(id);
    }
  }
  function _showLoading(id) {
    if (typeof config.showLoading === "function") {
      config.showLoading(id);
    }
  }
  function _showJson(id, val) {
    if (typeof config.showJson === "function") {
      config.showJson(id, val);
    }
  }
  function _reopenPendingCompositionForReturn() {
    return typeof config.reopenPendingCompositionForReturn === "function"
      ? config.reopenPendingCompositionForReturn()
      : Promise.resolve(null);
  }
  function _refreshCurrentCompositionView() {
    return typeof config.refreshCurrentCompositionView === "function"
      ? config.refreshCurrentCompositionView()
      : Promise.resolve();
  }
  function _attachExistingComponentToCurrentComposition(id) {
    return typeof config.attachExistingComponentToCurrentComposition === "function"
      ? config.attachExistingComponentToCurrentComposition(id)
      : Promise.resolve(null);
  }
  function _clearPendingComponentCreateForComposition() {
    if (typeof config.clearPendingComponentCreateForComposition === "function") {
      config.clearPendingComponentCreateForComposition();
    }
  }

  // ─── A: Draft data model ─────────────────────────────────────────────────

  function defaultRecipeIngredientRow() {
    return { ingredient_name: "", amount_value: "", amount_unit: "g" };
  }

  function normalizeRecipeIngredientRows(value) {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((row) => {
        const s = row || {};
        return {
          ingredient_name: String(s.ingredient_name || ""),
          amount_value: String(s.amount_value || ""),
          amount_unit: String(s.amount_unit || "g"),
        };
      })
      .filter((row) =>
        Boolean(String(row.ingredient_name || "").trim()) ||
        Boolean(String(row.amount_value || "").trim()) ||
        Boolean(String(row.amount_unit || "").trim()),
      );
  }

  function parseLegacyRecipeIngredientText(value) {
    const text = String(value || "");
    if (!text.trim()) {
      return [];
    }
    return text
      .split(/\r?\n/)
      .map((line) => String(line || "").trim())
      .filter(Boolean)
      .map((line) => {
        const parts = line.split("|").map((p) => String(p || "").trim());
        if (parts.length >= 3) {
          return { ingredient_name: parts[0], amount_value: parts[1], amount_unit: parts[2] };
        }
        return { ingredient_name: line, amount_value: "", amount_unit: "g" };
      });
  }

  function recipeIngredientRowsToLegacyText(rows) {
    return normalizeRecipeIngredientRows(rows)
      .map((row) => {
        const ingredient = String(row.ingredient_name || "").trim();
        const amount = String(row.amount_value || "").trim();
        const unit = String(row.amount_unit || "").trim();
        if (ingredient && amount && unit) {
          return ingredient + " | " + amount + " | " + unit;
        }
        if (ingredient && amount) {
          return ingredient + " | " + amount;
        }
        return ingredient || "";
      })
      .filter(Boolean)
      .join("\n");
  }

  function defaultCalculationRow() {
    return {
      ingredient_name: "",
      amount_value: "",
      amount_unit: "g",
      price_value: "",
      price_unit: "kr/kg",
      calculated_cost: "",
    };
  }

  function parseFloatSafe(value) {
    const num = Number(String(value || "").replace(",", "."));
    return Number.isFinite(num) ? num : null;
  }

  function normalizeCalculationRows(value) {
    if (!Array.isArray(value)) {
      return [];
    }
    return value
      .map((row) => {
        const base = defaultCalculationRow();
        const s = row || {};
        return {
          ingredient_name: String(s.ingredient_name || base.ingredient_name),
          amount_value: String(s.amount_value || base.amount_value),
          amount_unit: String(s.amount_unit || base.amount_unit),
          price_value: String(s.price_value || base.price_value),
          price_unit: String(s.price_unit || base.price_unit),
          calculated_cost: String(s.calculated_cost || base.calculated_cost),
        };
      })
      .filter((row) =>
        Boolean(String(row.ingredient_name || "").trim()) ||
        Boolean(String(row.amount_value || "").trim()) ||
        Boolean(String(row.price_value || "").trim()),
      );
  }

  function calculateRowCost(row) {
    const amountValue = parseFloatSafe(row && row.amount_value);
    const priceValue = parseFloatSafe(row && row.price_value);
    const amountUnit = String((row && row.amount_unit) || "").trim().toLowerCase();
    const priceUnit = String((row && row.price_unit) || "").trim().toLowerCase();
    if (amountValue == null || priceValue == null) {
      return null;
    }
    if (priceUnit === "kr/kg") {
      if (amountUnit === "g") {
        return (amountValue / 1000) * priceValue;
      }
      if (amountUnit === "kg") {
        return amountValue * priceValue;
      }
    }
    if (priceUnit === "kr/l") {
      if (amountUnit === "ml") {
        return (amountValue / 1000) * priceValue;
      }
      if (amountUnit === "dl") {
        return (amountValue / 10) * priceValue;
      }
      if (amountUnit === "l") {
        return amountValue * priceValue;
      }
      if (amountUnit === "g") {
        return (amountValue / 1000) * priceValue;
      }
    }
    if (priceUnit === "kr/st") {
      return amountValue * priceValue;
    }
    return null;
  }

  function formatCostValue(value) {
    if (!Number.isFinite(value)) {
      return "";
    }
    return value.toFixed(2);
  }

  function defaultComponentDetailDraft() {
    return {
      tags: [],
      long_description: "",
      recipe_ingredient_rows: [],
      recipe_ingredients_text: "",
      method_text: "",
      method_notes: "",
      calculation_yield: "",
      calculation_cost: "",
      calculation_notes: "",
      calculation_rows: [],
      allergens: [],
      allergen_notes: "",
    };
  }

  function normalizeComponentDetailDraft(value) {
    const source = value || {};
    const base = defaultComponentDetailDraft();
    const recipeIngredientRows = normalizeRecipeIngredientRows(source.recipe_ingredient_rows);
    const normalizedRecipeRows = recipeIngredientRows.length > 0
      ? recipeIngredientRows
      : normalizeRecipeIngredientRows(parseLegacyRecipeIngredientText(source.recipe_ingredients_text));
    return {
      tags: Array.isArray(source.tags)
        ? Array.from(new Set(source.tags.map((item) => String(item || "").trim().toLowerCase()).filter(Boolean)))
        : [],
      long_description: String(source.long_description || base.long_description),
      recipe_ingredient_rows: normalizedRecipeRows,
      recipe_ingredients_text: String(source.recipe_ingredients_text || recipeIngredientRowsToLegacyText(normalizedRecipeRows) || base.recipe_ingredients_text),
      method_text: String(source.method_text || base.method_text),
      method_notes: String(source.method_notes || base.method_notes),
      calculation_yield: String(source.calculation_yield || base.calculation_yield),
      calculation_cost: String(source.calculation_cost || base.calculation_cost),
      calculation_notes: String(source.calculation_notes || base.calculation_notes),
      calculation_rows: normalizeCalculationRows(source.calculation_rows),
      allergens: Array.isArray(source.allergens)
        ? source.allergens.map((item) => String(item || "").trim().toLowerCase()).filter(Boolean)
        : [],
      allergen_notes: String(source.allergen_notes || base.allergen_notes),
    };
  }

  // ─── B: Component-specific API persistence ───────────────────────────────

  async function fetchComponentDetailDraft(componentId) {
    const idValue = String(componentId || "").trim();
    if (!idValue) {
      return defaultComponentDetailDraft();
    }
    const result = await callApi(
      "/api/builder/components/" + encodeURIComponent(idValue) + "/details",
      { method: "GET" },
    );
    if (!(result && result.status < 400 && result.data && result.data.ok)) {
      throw new Error("Could not load component details from backend.");
    }
    const details = result.data && result.data.details ? result.data.details : {};
    return normalizeComponentDetailDraft(details);
  }

  async function saveComponentDetailDraft(componentId, draft) {
    const idValue = String(componentId || "").trim();
    if (!idValue) {
      throw new Error("Component id is missing.");
    }
    const payload = normalizeComponentDetailDraft(draft);
    const result = await callApi(
      "/api/builder/components/" + encodeURIComponent(idValue) + "/details",
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: payload,
      },
    );
    if (!(result && result.status < 400 && result.data && result.data.ok)) {
      throw new Error("Could not save component details to backend.");
    }
    const details = result.data && result.data.details ? result.data.details : payload;
    return normalizeComponentDetailDraft(details);
  }

  async function saveComponentOverviewFromDetail(componentId) {
    const idValue = String(componentId || "").trim();
    if (!idValue) {
      throw new Error("Component id is missing.");
    }
    const nameInput = document.getElementById("componentDetailOverviewName");
    const categoryInput = document.getElementById("componentDetailOverviewCategory");
    const nextName = cleanComponentInlineName(nameInput ? nameInput.value : "");
    const nextCategory = String((categoryInput && categoryInput.value) || "").trim().toLowerCase();
    if (!nextName) {
      throw new Error("Component name is required.");
    }
    _showLoading("componentDetailOut");
    const result = await callApi(
      "/api/builder/components/" + encodeURIComponent(idValue),
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: { name: nextName, category: nextCategory || null },
      },
    );
    setComponentDetailFeedback(result);
    if (!(result && result.status < 400 && result.data && result.data.ok)) {
      throw new Error("Could not save component overview.");
    }
    const target = _getCachedComponents().find((entry) => String(entry.component_id || "") === idValue);
    if (target) {
      target.component_name = nextName;
      target.category = nextCategory || "";
    }
    if (nameInput) {
      nameInput.value = nextName;
    }
    if (result && result.data && result.data.component) {
      _upsertCachedComponent({
        ...result.data.component,
        component_id: idValue,
        component_name: nextName,
        category: nextCategory || "",
      });
    }
    const cachedAfter = _getCachedComponents().find((entry) => String(entry.component_id || "") === idValue) || null;
    _updateComponentCategoryChipCounts();
    _filterLibraryComponents(_currentComponentSearchQuery());
    return result;
  }

  // ─── C/K: Form feedback ──────────────────────────────────────────────────

  function setComponentDetailFeedback(payload) {
    const el = document.getElementById("componentDetailOut");
    if (!el) {
      return;
    }
    const data = (payload && payload.data) || {};
    const ok = Boolean(data && data.ok);
    if (ok) {
      el.textContent = String(data.message || "Saved.");
      return;
    }
      el.textContent = String(data.message || data.error || "Could not save changes.");
  }

    function clearComponentDetailFeedback() {
      const el = document.getElementById("componentDetailOut");
      if (!el) {
        return;
      }
      el.textContent = "";
    }

  // ─── H: Dirty/session tracking ───────────────────────────────────────────

  function markComponentDetailDirty() {
    _setState("_componentDetailDirty", true);
  }

  function resetComponentDetailDirty() {
    _setState("_componentDetailDirty", false);
  }

  // ─── G: Component tags ───────────────────────────────────────────────────

  function parseComponentTagsInput(value) {
    return Array.from(new Set(
      String(value || "")
        .split(",")
        .map((entry) => String(entry || "").trim().toLowerCase())
        .filter(Boolean),
    ));
  }

  function formatComponentTagsInput(tags) {
    if (!Array.isArray(tags)) {
      return "";
    }
    return tags
      .map((v) => String(v || "").trim().toLowerCase())
      .filter(Boolean)
      .join(", ");
  }

  function normalizeComponentDetailTagValue(value) {
    return String(value || "")
      .replace(/#/g, "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, " ");
  }

  function currentComponentDetailTags() {
    const draft = _getState("_componentDetailTagsDraft");
    return Array.isArray(draft) ? draft.slice() : [];
  }

  function _buildTagCatalog() {
    const unique = new Set();
    for (const item of _getCachedComponents()) {
      if (Array.isArray(item.tags)) {
        for (const tag of item.tags) {
          const t = String(tag || "").trim().toLowerCase();
          if (t) {
            unique.add(t);
          }
        }
      }
    }
    return Array.from(unique).sort((a, b) =>
      a.localeCompare(b, undefined, { sensitivity: "base" }),
    );
  }

  function renderComponentDetailTagSuggestions() {
    const suggestions = document.getElementById("componentDetailTagsSuggestions");
    if (!suggestions) {
      return;
    }
    const selected = new Set(currentComponentDetailTags());
    const catalog = _buildTagCatalog()
      .filter((tag) => !selected.has(tag))
      .slice(0, 40);
    suggestions.innerHTML = "";
    for (const tag of catalog) {
      const option = document.createElement("option");
      option.value = tag;
      suggestions.appendChild(option);
    }
  }

  function renderComponentDetailTagChips() {
    const host = document.getElementById("componentDetailTagsChips");
    const hiddenInput = document.getElementById("componentDetailOverviewTags");
    const tagsDraft = _getState("_componentDetailTagsDraft") || [];
    if (hiddenInput) {
      hiddenInput.value = formatComponentTagsInput(tagsDraft);
    }
    if (!host) {
      renderComponentDetailTagSuggestions();
      return;
    }
    host.innerHTML = "";
    if (!Array.isArray(tagsDraft) || tagsDraft.length === 0) {
      const empty = document.createElement("span");
      empty.className = "builder-component-tags-empty";
      empty.textContent = "Inga taggar ännu.";
      host.appendChild(empty);
      renderComponentDetailTagSuggestions();
      return;
    }
    for (const tag of tagsDraft) {
      const chip = document.createElement("span");
      chip.className = "builder-component-tag-chip";
      const text = document.createElement("span");
      text.textContent = "#" + tag;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "builder-component-tag-chip-remove";
      remove.setAttribute("aria-label", "Ta bort tagg " + tag);
      remove.setAttribute("data-remove-tag", tag);
      remove.textContent = "x";
      chip.appendChild(text);
      chip.appendChild(remove);
      host.appendChild(chip);
    }
    renderComponentDetailTagSuggestions();
  }

  function setComponentDetailTags(tags) {
    const source = Array.isArray(tags) ? tags : parseComponentTagsInput(tags);
    const normalized = Array.from(new Set(
      source.map((v) => normalizeComponentDetailTagValue(v)).filter(Boolean),
    ));
    _setState("_componentDetailTagsDraft", normalized);
    renderComponentDetailTagChips();
  }

  function addComponentDetailTagsFromInput(rawValue) {
    const parsed = parseComponentTagsInput(String(rawValue || "").replace(/#/g, ","));
    if (parsed.length === 0) {
      return false;
    }
    const next = new Set(currentComponentDetailTags());
    let changed = false;
    for (const tag of parsed) {
      const normalized = normalizeComponentDetailTagValue(tag);
      if (!normalized || next.has(normalized)) {
        continue;
      }
      next.add(normalized);
      changed = true;
    }
    if (!changed) {
      return false;
    }
    setComponentDetailTags(Array.from(next));
    return true;
  }

  function removeComponentDetailTag(tagValue) {
    const normalized = normalizeComponentDetailTagValue(tagValue);
    if (!normalized) {
      return false;
    }
    const current = currentComponentDetailTags();
    const next = current.filter((tag) => tag !== normalized);
    if (next.length === current.length) {
      return false;
    }
    setComponentDetailTags(next);
    return true;
  }

  // ─── H: Tab/display state ─────────────────────────────────────────────────

  function componentDetailTabValue(value) {
    const key = String(value || "").trim().toLowerCase();
    if (key === "recipe" || key === "calculation" || key === "allergens") {
      return key;
    }
    return "overview";
  }

  function setComponentDetailTab(tabValue) {
    const nextTab = componentDetailTabValue(tabValue);
    _setState("_activeComponentDetailTab", nextTab);
    const modal = document.getElementById("componentDetailEditorModal");
    const tabButtons = modal
      ? Array.from(modal.querySelectorAll("[data-component-tab]"))
      : Array.from(document.querySelectorAll("[data-component-tab]"));
    const tabPanels = modal
      ? Array.from(modal.querySelectorAll(".component-detail-panel[data-component-panel]"))
      : Array.from(document.querySelectorAll(".component-detail-panel[data-component-panel]"));
    tabButtons.forEach((button) => {
      const tab = String(button.getAttribute("data-component-tab") || "").trim().toLowerCase();
      const active = tab === nextTab;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-selected", active ? "true" : "false");
    });
    tabPanels.forEach((panel) => {
      const tab = String(panel.getAttribute("data-component-panel") || "").trim().toLowerCase();
      const active = tab === nextTab;
      panel.classList.toggle("hidden", !active);
      if (active) {
        panel.removeAttribute("hidden");
      } else {
        panel.setAttribute("hidden", "hidden");
      }
    });
    if (nextTab === "calculation") {
      const host = document.getElementById("componentDetailCalculationRows");
      const hasRows = host ? Boolean(host.querySelector("[data-calc-row]")) : false;
      if (!hasRows) {
        syncCalculationRowsFromRecipeRows();
      }
    }
  }

  // ─── D/E: Recipe & method editing ────────────────────────────────────────

  function readRecipeIngredientRowsFromForm() {
    const host = document.getElementById("componentDetailRecipeIngredientRows");
    if (!host) {
      return [];
    }
    const rows = Array.from(host.querySelectorAll("[data-recipe-row]"));
    return normalizeRecipeIngredientRows(
      rows.map((rowEl) => {
        const readField = (field) => {
          const input = rowEl.querySelector("[data-recipe-field='" + field + "']");
          return input ? String(input.value || "") : "";
        };
        return {
          ingredient_name: readField("ingredient_name"),
          amount_value: readField("amount_value"),
          amount_unit: readField("amount_unit"),
        };
      }),
    );
  }

  function renderRecipeIngredientRows(rows) {
    const host = document.getElementById("componentDetailRecipeIngredientRows");
    if (!host) {
      return;
    }
    const normalized = normalizeRecipeIngredientRows(rows);
    const sourceRows = normalized.length > 0 ? normalized : [defaultRecipeIngredientRow()];
    host.innerHTML = "";
    sourceRows.forEach((row) => {
      const rowWrap = document.createElement("div");
      rowWrap.className = "builder-component-recipe-row";
      rowWrap.setAttribute("data-recipe-row", "1");
      const ingredient = document.createElement("input");
      ingredient.type = "text";
      ingredient.placeholder = "Ingrediens";
      ingredient.value = String(row.ingredient_name || "");
      ingredient.setAttribute("data-recipe-field", "ingredient_name");
      const amountValue = document.createElement("input");
      amountValue.type = "number";
      amountValue.step = "0.01";
      amountValue.placeholder = "Mängd";
      amountValue.value = String(row.amount_value || "");
      amountValue.setAttribute("data-recipe-field", "amount_value");
      const amountUnit = document.createElement("input");
      amountUnit.type = "text";
      amountUnit.placeholder = "Enhet (g/ml/dl/kg/l/st)";
      amountUnit.value = String(row.amount_unit || "g");
      amountUnit.setAttribute("data-recipe-field", "amount_unit");
      const removeBtn = document.createElement("button");
      removeBtn.type = "button";
      removeBtn.className = "builder-row-remove-icon";
      removeBtn.textContent = "x";
      removeBtn.setAttribute("aria-label", "Ta bort ingrediensrad");
      removeBtn.addEventListener("click", () => {
        rowWrap.remove();
        if (!host.querySelector("[data-recipe-row]")) {
          renderRecipeIngredientRows([defaultRecipeIngredientRow()]);
        }
        markComponentDetailDirty();
      });
      [ingredient, amountValue, amountUnit].forEach((input) => {
        input.addEventListener("input", () => {
          markComponentDetailDirty();
        });
      });
      rowWrap.appendChild(ingredient);
      rowWrap.appendChild(amountValue);
      rowWrap.appendChild(amountUnit);
      rowWrap.appendChild(removeBtn);
      host.appendChild(rowWrap);
    });
  }

  // ─── F: Calculation synchronization ──────────────────────────────────────

  function buildCalculationRowsFromRecipeRows(recipeRows, existingCalculationRows) {
    const normalizedRecipeRows = normalizeRecipeIngredientRows(recipeRows);
    const normalizedExisting = normalizeCalculationRows(existingCalculationRows);
    const existingByKey = new Map();
    normalizedExisting.forEach((row) => {
      const key = String(row.ingredient_name || "").trim().toLowerCase();
      if (key && !existingByKey.has(key)) {
        existingByKey.set(key, row);
      }
    });
    return normalizedRecipeRows.map((recipeRow) => {
      const key = String(recipeRow.ingredient_name || "").trim().toLowerCase();
      const existing = key ? existingByKey.get(key) : null;
      return {
        ingredient_name: String(recipeRow.ingredient_name || ""),
        amount_value: String(recipeRow.amount_value || ""),
        amount_unit: String(recipeRow.amount_unit || "g"),
        price_value: existing ? String(existing.price_value || "") : "",
        price_unit: existing ? String(existing.price_unit || "kr/kg") : "kr/kg",
        calculated_cost: "",
      };
    });
  }

  function recalculateCalculationRowsCost() {
    const host = document.getElementById("componentDetailCalculationRows");
    const totalInput = document.getElementById("componentDetailCalcCost");
    if (!host) {
      return;
    }
    let total = 0;
    const rows = Array.from(host.querySelectorAll("[data-calc-row]"));
    rows.forEach((rowEl) => {
      const amountInput = rowEl.querySelector("[data-calc-field='amount_value']");
      const amountUnitInput = rowEl.querySelector("[data-calc-field='amount_unit']");
      const priceInput = rowEl.querySelector("[data-calc-field='price_value']");
      const priceUnitInput = rowEl.querySelector("[data-calc-field='price_unit']");
      const calcCostInput = rowEl.querySelector("[data-calc-field='calculated_cost']");
      const rowData = {
        amount_value: amountInput ? amountInput.value : "",
        amount_unit: amountUnitInput ? amountUnitInput.value : "",
        price_value: priceInput ? priceInput.value : "",
        price_unit: priceUnitInput ? priceUnitInput.value : "",
      };
      const cost = calculateRowCost(rowData);
      if (calcCostInput) {
        calcCostInput.value = cost == null ? "" : formatCostValue(cost) + " kr";
      }
      if (cost != null) {
        total += cost;
      }
    });
    if (totalInput) {
      totalInput.value = total > 0 ? formatCostValue(total) + " kr" : "";
    }
  }

  function renderCalculationRows(rows) {
    const host = document.getElementById("componentDetailCalculationRows");
    if (!host) {
      return;
    }
    const normalized = normalizeCalculationRows(rows);
    const sourceRows = normalized.length > 0 ? normalized : [defaultCalculationRow()];
    host.innerHTML = "";
    for (const row of sourceRows) {
      const rowWrap = document.createElement("div");
      rowWrap.className = "builder-component-calc-row";
      rowWrap.setAttribute("data-calc-row", "1");
      const ingredient = document.createElement("input");
      ingredient.type = "text";
      ingredient.placeholder = "Ingrediens";
      ingredient.value = String(row.ingredient_name || "");
      ingredient.setAttribute("data-calc-field", "ingredient_name");
      ingredient.readOnly = true;
      const amountValue = document.createElement("input");
      amountValue.type = "number";
      amountValue.placeholder = "Mängd";
      amountValue.step = "0.01";
      amountValue.value = String(row.amount_value || "");
      amountValue.setAttribute("data-calc-field", "amount_value");
      amountValue.readOnly = true;
      const amountUnit = document.createElement("input");
      amountUnit.type = "text";
      amountUnit.placeholder = "Enhet (g/ml/kg/l/st)";
      amountUnit.value = String(row.amount_unit || "g");
      amountUnit.setAttribute("data-calc-field", "amount_unit");
      amountUnit.readOnly = true;
      const priceValue = document.createElement("input");
      priceValue.type = "number";
      priceValue.placeholder = "Pris";
      priceValue.step = "0.01";
      priceValue.value = String(row.price_value || "");
      priceValue.setAttribute("data-calc-field", "price_value");
      const priceUnit = document.createElement("input");
      priceUnit.type = "text";
      priceUnit.placeholder = "Prisenhet (kr/kg, kr/l, kr/st)";
      priceUnit.value = String(row.price_unit || "kr/kg");
      priceUnit.setAttribute("data-calc-field", "price_unit");
      const calcCost = document.createElement("input");
      calcCost.type = "text";
      calcCost.placeholder = "Kostnad";
      calcCost.readOnly = true;
      calcCost.value = String(row.calculated_cost || "");
      calcCost.setAttribute("data-calc-field", "calculated_cost");
      [priceValue, priceUnit].forEach((input) => {
        input.addEventListener("input", () => {
          markComponentDetailDirty();
          recalculateCalculationRowsCost();
        });
      });
      rowWrap.appendChild(ingredient);
      rowWrap.appendChild(amountValue);
      rowWrap.appendChild(amountUnit);
      rowWrap.appendChild(priceValue);
      rowWrap.appendChild(priceUnit);
      rowWrap.appendChild(calcCost);
      host.appendChild(rowWrap);
    }
    recalculateCalculationRowsCost();
  }

  function syncCalculationRowsFromRecipeRows() {
    const recipeRows = readRecipeIngredientRowsFromForm();
    const host = document.getElementById("componentDetailCalculationRows");
    const existing = host
      ? Array.from(host.querySelectorAll("[data-calc-row]")).map((rowEl) => {
        const readField = (field) => {
          const input = rowEl.querySelector("[data-calc-field='" + field + "']");
          return input ? String(input.value || "") : "";
        };
        return {
          ingredient_name: readField("ingredient_name"),
          amount_value: readField("amount_value"),
          amount_unit: readField("amount_unit"),
          price_value: readField("price_value"),
          price_unit: readField("price_unit"),
          calculated_cost: readField("calculated_cost"),
        };
      })
      : [];
    renderCalculationRows(buildCalculationRowsFromRecipeRows(recipeRows, existing));
  }

  // ─── C: Form read/apply ───────────────────────────────────────────────────

  function readComponentDetailFormDraft() {
    const longDescriptionInput = document.getElementById("componentDetailOverviewLongDescription");
    const recipeIngredientsLegacy = document.getElementById("componentDetailRecipeIngredients");
    const methodText = document.getElementById("componentDetailMethodText");
    const methodNotes = document.getElementById("componentDetailMethodNotes");
    const calcCost = document.getElementById("componentDetailCalcCost");
    const calcNotes = document.getElementById("componentDetailCalcNotes");
    const allergenNotes = document.getElementById("componentDetailAllergenNotes");
    const checkboxes = Array.from(document.querySelectorAll(".component-detail-allergen-checkbox"));
    const allergens = checkboxes
      .filter((box) => Boolean(box.checked))
      .map((box) => String(box.value || "").trim().toLowerCase())
      .filter(Boolean);
    const recipeIngredientRows = readRecipeIngredientRowsFromForm();
    const calculationRowsHost = document.getElementById("componentDetailCalculationRows");
    const existingCalculationRows = calculationRowsHost
      ? Array.from(calculationRowsHost.querySelectorAll("[data-calc-row]")).map((rowEl) => {
        const readField = (field) => {
          const input = rowEl.querySelector("[data-calc-field='" + field + "']");
          return input ? String(input.value || "") : "";
        };
        return {
          ingredient_name: readField("ingredient_name"),
          amount_value: readField("amount_value"),
          amount_unit: readField("amount_unit"),
          price_value: readField("price_value"),
          price_unit: readField("price_unit"),
          calculated_cost: readField("calculated_cost"),
        };
      })
      : [];
    const calculationRows = buildCalculationRowsFromRecipeRows(recipeIngredientRows, existingCalculationRows);
    const recipeLegacyText = recipeIngredientRowsToLegacyText(recipeIngredientRows);
    if (recipeIngredientsLegacy) {
      recipeIngredientsLegacy.value = recipeLegacyText;
    }
    return {
      tags: currentComponentDetailTags(),
      long_description: longDescriptionInput ? String(longDescriptionInput.value || "") : "",
      recipe_ingredient_rows: recipeIngredientRows,
      recipe_ingredients_text: recipeLegacyText,
      method_text: methodText ? String(methodText.value || "") : "",
      method_notes: methodNotes ? String(methodNotes.value || "") : "",
      calculation_yield: "",
      calculation_cost: calcCost ? String(calcCost.value || "") : "",
      calculation_notes: calcNotes ? String(calcNotes.value || "") : "",
      calculation_rows: normalizeCalculationRows(calculationRows),
      allergens,
      allergen_notes: allergenNotes ? String(allergenNotes.value || "") : "",
    };
  }

  function applyComponentDetailDraftToForm(draft) {
    const payload = draft || defaultComponentDetailDraft();
    const longDescriptionInput = document.getElementById("componentDetailOverviewLongDescription");
    const recipeIngredientsLegacy = document.getElementById("componentDetailRecipeIngredients");
    const methodText = document.getElementById("componentDetailMethodText");
    const methodNotes = document.getElementById("componentDetailMethodNotes");
    const calcCost = document.getElementById("componentDetailCalcCost");
    const calcNotes = document.getElementById("componentDetailCalcNotes");
    const allergenNotes = document.getElementById("componentDetailAllergenNotes");
    const selected = new Set(
      Array.isArray(payload.allergens)
        ? payload.allergens.map((item) => String(item || "").trim().toLowerCase())
        : [],
    );
    const recipeRows = normalizeRecipeIngredientRows(payload.recipe_ingredient_rows).length > 0
      ? normalizeRecipeIngredientRows(payload.recipe_ingredient_rows)
      : normalizeRecipeIngredientRows(parseLegacyRecipeIngredientText(payload.recipe_ingredients_text));
    renderRecipeIngredientRows(recipeRows);
    if (recipeIngredientsLegacy) {
      recipeIngredientsLegacy.value = recipeIngredientRowsToLegacyText(recipeRows);
    }
    if (methodText) {
      methodText.value = String(payload.method_text || "");
    }
    if (methodNotes) {
      methodNotes.value = String(payload.method_notes || "");
    }
    if (calcCost) {
      calcCost.value = String(payload.calculation_cost || "");
    }
    if (calcNotes) {
      calcNotes.value = String(payload.calculation_notes || "");
    }
    if (allergenNotes) {
      allergenNotes.value = String(payload.allergen_notes || "");
    }
    setComponentDetailTags(payload.tags);
    if (longDescriptionInput) {
      longDescriptionInput.value = String(payload.long_description || "");
    }
    const syncedRows = buildCalculationRowsFromRecipeRows(recipeRows, payload.calculation_rows || []);
    renderCalculationRows(syncedRows);
    document.querySelectorAll(".component-detail-allergen-checkbox").forEach((checkbox) => {
      const value = String(checkbox.value || "").trim().toLowerCase();
      checkbox.checked = selected.has(value);
    });
  }

  // ─── Return-to-dish button label (reads pending context from state) ────────

  function updateComponentDetailReturnAction() {
    const button = document.getElementById("componentDetailReturnToDishBtn");
    if (!button) {
      return;
    }
    const compositionId = String(_getState("pendingComponentCreateForCompositionId") || "").trim();
    const compositionName = String(_getState("pendingComponentCreateForCompositionName") || "").trim();
    const pendingComponentId = String(_getState("pendingComponentCreateComponentId") || "").trim();
    const activeComponentId = String(_getState("_activeComponentDetailId") || "").trim();
    if (!compositionId || !compositionName || !pendingComponentId || !activeComponentId || activeComponentId !== pendingComponentId) {
      button.classList.add("hidden");
      button.setAttribute("hidden", "hidden");
      button.textContent = "";
      return;
    }
    button.textContent = "Lägg till i " + compositionName;
    button.classList.remove("hidden");
    button.removeAttribute("hidden");
  }

  // ─── L: Text helper ───────────────────────────────────────────────────────

  function cleanComponentInlineName(value) {
    let cleaned = String(value || "").trim();
    if (!cleaned) {
      return "";
    }
    cleaned = cleaned.replace(/^\s*(Lunch|Kväll|Kvall|Dessert|Middag|Frukost)\s*:\s*/i, "").trim();
    cleaned = cleaned.replace(/^\s*(Serveras(?:\s+med)?|Med)\s+/i, "").trim();
    cleaned = cleaned.replace(/\s+serveras(?:\b.*)?$/i, "").trim();
    return cleaned.replace(/\s+/g, " ").trim();
  }

  // Category key normalization (used in open orchestration only) ─────────────

  function _normalizeCategoryKey(value) {
    const folded = String(value || "")
      .trim()
      .toLowerCase()
      .replace(/[åä]/g, "a")
      .replace(/ö/g, "o");
    if (!folded) {
      return "ovrigt";
    }
    if (
      folded === "main" ||
      folded === "kott" ||
      folded === "protein" ||
      folded === "fish" ||
      folded === "fisk"
    ) {
      return "main";
    }
    if (folded === "side" || folded === "tillbehor") {
      return "side";
    }
    if (folded === "sauce" || folded === "sas") {
      return "sauce";
    }
    if (folded === "dessert") {
      return "dessert";
    }
    return "ovrigt";
  }

  // ─── I: Modal open/save/close orchestration ───────────────────────────────

  async function openComponentDetailEditor(componentId, initialTab) {
    const idValue = String(componentId || "").trim();
    if (!idValue) {
      return;
    }
    const pendingComponentId = String(_getState("pendingComponentCreateComponentId") || "").trim();
    if (pendingComponentId && pendingComponentId !== idValue) {
      _clearPendingComponentCreateForComposition();
    }
    const requestedTab = componentDetailTabValue(initialTab || "overview");
    let component = _getCachedComponents().find(
      (item) => String(item.component_id || "") === idValue,
    );
    if (!component) {
      const resolvedComponent = await _resolveComponentById(idValue);
      if (resolvedComponent) {
        component = resolvedComponent.component || resolvedComponent;
      }
    }
    if (!component) {
      return;
    }
    _setState("_activeComponentDetailId", idValue);
    const title = document.getElementById("componentDetailEditorTitle");
    const nameInput = document.getElementById("componentDetailOverviewName");
    const categoryInput = document.getElementById("componentDetailOverviewCategory");
    const meta = document.getElementById("componentDetailOverviewMeta");
    const nextCategory = String(component.category || "").trim().toLowerCase();
    if (title) {
      title.textContent =
        "Komponentredigerare: " +
        String(component.component_name || component.component_id || "");
    }
    if (nameInput) {
      nameInput.value = String(component.component_name || component.component_id || "");
    }
    if (categoryInput) {
      categoryInput.value = ["main", "side", "sauce", "dessert", "ovrigt"].includes(nextCategory)
        ? nextCategory
        : "ovrigt";
    }
    if (meta) {
      meta.textContent = "Komponent-ID: " + String(component.component_id || "");
    }
    _showLoading("componentDetailOut");
      clearComponentDetailFeedback();
    applyComponentDetailDraftToForm(defaultComponentDetailDraft());
    try {
      const draft = await fetchComponentDetailDraft(idValue);
      applyComponentDetailDraftToForm(draft);
      setComponentDetailFeedback({
        status: 200,
        data: { ok: true, message: "Komponentdetaljer laddade." },
      });
    } catch (_error) {
      applyComponentDetailDraftToForm(defaultComponentDetailDraft());
      setComponentDetailFeedback({
        status: 500,
        data: { ok: false, message: "Could not load details from backend. Try again." },
      });
    }
    setComponentDetailTab(requestedTab || "overview");
    resetComponentDetailDirty();
    _openSimpleModal("componentDetailEditorModal");
    updateComponentDetailReturnAction();
  }

  async function saveActiveComponentDetailDraft() {
    const idValue = String(_getState("_activeComponentDetailId") || "").trim();
    if (!idValue) {
      return;
    }
    const draft = readComponentDetailFormDraft();
    _showLoading("componentDetailOut");
    try {
      const target = _getCachedComponents().find(
        (entry) => String(entry.component_id || "") === idValue,
      );
      const overviewResult = await saveComponentOverviewFromDetail(idValue);
      const saved = await saveComponentDetailDraft(idValue, draft);
      applyComponentDetailDraftToForm(saved);
      if (target) {
        target.tags = Array.isArray(saved.tags) ? saved.tags.slice() : [];
      }
      if (overviewResult && overviewResult.data && overviewResult.data.component) {
        _upsertCachedComponent({
          ...overviewResult.data.component,
          component_id: idValue,
          tags: Array.isArray(saved.tags) ? saved.tags.slice() : [],
        });
      }
      resetComponentDetailDirty();
      const canonicalAfter = _getCachedComponents().find((entry) => String(entry.component_id || "") === idValue) || null;
      const compositionLink = _getCachedCompositions().find(
        (composition) => Array.isArray(composition.components) && composition.components.some((item) => String(item.component_id || "") === idValue),
      ) || null;
      setComponentDetailFeedback({
        status: 200,
        data: { ok: true, message: "Komponentdetaljer sparade." },
      });
      try {
        await _refreshCurrentCompositionView();
      } catch (refreshError) {
        console.warn("Component saved, but current composition refresh failed:", refreshError);
      }
    } catch (_error) {
      setComponentDetailFeedback({
        status: 500,
        data: { ok: false, message: "Save failed: backend persistence is unavailable." },
      });
    }
  }

  async function closeComponentDetailEditor() {
    _closeModalById("componentDetailEditorModal");
    _setState("_activeComponentDetailId", "");
    _setState("_componentDetailDirty", false);
      clearComponentDetailFeedback();
    _clearPendingComponentCreateForComposition();
  }

  // ─── J: Component delete ──────────────────────────────────────────────────

  async function deleteComponentFromLibrary(componentId, componentName) {
    const idValue = String(componentId || "").trim();
    if (!idValue) {
      return;
    }
    const name = String(componentName || componentId || "component");
    if (!window.confirm('Ta bort komponent "' + name + '"?')) {
      return;
    }
    _showLoading("libraryOut");
    const result = await callApi(
      "/api/builder/components/" + encodeURIComponent(idValue),
      { method: "DELETE" },
    );
    _showJson("libraryOut", result);
    if (result && result.status === 409) {
      const payload = (result && result.data) || {};
      const refs = payload.references || {};
      const compositionIds = Array.isArray(refs.composition_ids)
        ? Array.from(
          new Set(refs.composition_ids.map((v) => String(v || "")).filter(Boolean)),
        )
        : [];
      const referencedNames = Array.isArray(refs.composition_names)
        ? refs.composition_names.map((v) => String(v || "")).filter(Boolean)
        : [];
      const dishNames =
        referencedNames.length > 0
          ? referencedNames
          : compositionIds.map((id) => {
            const match = _getCachedCompositions().find(
              (entry) => String(entry.composition_id || "") === id,
            );
            return String((match && match.composition_name) || id);
          });
      const uniqueDishNames = Array.from(new Set(dishNames));
      const usedCount =
        uniqueDishNames.length > 0
          ? uniqueDishNames.length
          : compositionIds.length > 0
            ? compositionIds.length
            : Number(refs.composition_count || 0);
      const recipeCount = Number(refs.recipe_count || 0);
      let msg =
        "Den här komponenten används i " +
        String(usedCount) +
        (usedCount === 1 ? " rätt" : " rätter") +
        " och kan inte tas bort direkt.";
      if (uniqueDishNames.length > 0) {
        const preview = uniqueDishNames.slice(0, 10).join("\n- ");
        const extra =
          uniqueDishNames.length > 10
            ? "\n- +" + String(uniqueDishNames.length - 10) + " fler"
            : "";
        msg += "\n\nAnvänds i:\n- " + preview + extra;
      }
      if (recipeCount > 0) {
        msg +=
          "\n\nKopplad till " +
          String(recipeCount) +
          (recipeCount === 1 ? " recept." : " recept.");
      }
      msg +=
        "\n\nNästa steg: öppna berörd rätt för att ta bort eller ersätta komponenten, eller byt namn på komponenten.";
      const fallback = String(payload.message || "Komponenten används redan.");
      window.alert(msg || fallback);
      return;
    }
    if (result && result.status < 400 && result.data && result.data.ok) {
      await _loadLibrary();
      const search = document.getElementById("libraryComponentsSearch");
      const query = search ? String(search.value || "") : "";
      _filterLibraryComponents(query);
      if (String(_getState("_activeComponentDetailId") || "") === idValue) {
        _closeModalById("componentDetailEditorModal");
        _setState("_activeComponentDetailId", "");
        resetComponentDetailDirty();
      }
    }
  }

  return {
    openComponentDetailEditor,
    closeComponentDetailEditor,
    saveActiveComponentDetailDraft,
    setComponentDetailTab,
    markComponentDetailDirty,
    resetComponentDetailDirty,
    cleanComponentInlineName,
    addComponentDetailTagsFromInput,
    removeComponentDetailTag,
    readRecipeIngredientRowsFromForm,
    defaultRecipeIngredientRow,
    renderRecipeIngredientRows,
    syncCalculationRowsFromRecipeRows,
    updateComponentDetailReturnAction,
    deleteComponentFromLibrary,
    componentDetailTabValue,
    fetchComponentDetailDraft,
    defaultComponentDetailDraft,
  };
}
