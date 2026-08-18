function createBuilderDishEditor(config) {
  if (!config || !config.state || typeof config.state.get !== "function" || typeof config.state.set !== "function") {
    throw new Error("createBuilderDishEditor: state.get and state.set are required");
  }
  if (typeof config.callApi !== "function") {
    throw new Error("createBuilderDishEditor: callApi is required");
  }

  const _state = config.state;
  const _callApi = config.callApi;
  const _showLoading = typeof config.showLoading === "function" ? config.showLoading : null;
  const _showJson = typeof config.showJson === "function" ? config.showJson : null;
  const _loadLibrary = typeof config.loadLibrary === "function" ? config.loadLibrary : null;
  const _loadCompositionTextPreviewForCurrentComposition =
    typeof config.loadCompositionTextPreviewForCurrentComposition === "function"
      ? config.loadCompositionTextPreviewForCurrentComposition
      : null;
  const _fetchComponentDetailDraft = typeof config.fetchComponentDetailDraft === "function"
    ? config.fetchComponentDetailDraft
    : null;
  const _dishAllergenLabel = typeof config.dishAllergenLabel === "function"
    ? config.dishAllergenLabel
    : (value) => String(value || "");

  if (!_fetchComponentDetailDraft) {
    throw new Error("createBuilderDishEditor: fetchComponentDetailDraft is required");
  }

  function _getState(key) {
    return _state.get(key);
  }

  function _setState(key, value) {
    return _state.set(key, value);
  }

  function normalizeDishCategoryKey(value) {
    return String(value || "")
      .trim()
      .toLowerCase()
      .replace(/\s+/g, "_");
  }

  function normalizeDishLibraryGroupValue(value) {
    const key = normalizeDishCategoryKey(value);
    if (key === "fisk" || key === "kott" || key === "dessert" || key === "ovrigt") {
      return key;
    }
    return "";
  }

  function setCompositionTextPreview(previewId, message) {
    const preview = document.getElementById(String(previewId || ""));
    if (!preview) {
      return;
    }
    preview.textContent = String(message || "");
  }

  function renderDishAllergenSummaryMessage(message) {
    const host = document.getElementById("dishAllergensSummary");
    if (!host) {
      return;
    }
    host.innerHTML = "";
    const text = document.createElement("p");
    text.className = "builder-dish-allergen-summary-empty";
    text.textContent = String(message || "");
    host.appendChild(text);
  }

  function renderDishAllergenSummaryFailure() {
    renderDishAllergenSummaryMessage("Kunde inte läsa komponenterna just nu.");
  }

  function renderDishAllergenSummaryEmpty() {
    renderDishAllergenSummaryMessage("Inga allergener eller kostmarkörer registrerade på komponenterna.");
  }

  function renderDishAllergenSummaryLoading() {
    renderDishAllergenSummaryMessage("Samlar information från komponenterna...");
  }

  function renderDishAllergenSummary(composition, componentDetails) {
    const host = document.getElementById("dishAllergensSummary");
    if (!host) {
      return;
    }

    host.innerHTML = "";
    const detailsList = Array.isArray(componentDetails) ? componentDetails : [];
    const allergenMap = new Map();
    const markerMap = new Map();

    for (const entry of detailsList) {
      const component = entry && entry.component ? entry.component : null;
      const details = entry && entry.details ? entry.details : null;
      const componentName = String((component && component.component_name) || (component && component.component_id) || "").trim();
      const allergenNotes = String((details && details.allergen_notes) || "").trim();
      const allergens = Array.isArray(details && details.allergens) ? details.allergens : [];
      const tags = Array.isArray(details && details.tags) ? details.tags : [];

      for (const allergen of allergens) {
        const allergenKey = String(allergen || "").trim().toLowerCase();
        if (!allergenKey) {
          continue;
        }
        if (!allergenMap.has(allergenKey)) {
          allergenMap.set(allergenKey, { components: [], notes: [] });
        }
        const bucket = allergenMap.get(allergenKey);
        if (componentName && !bucket.components.includes(componentName)) {
          bucket.components.push(componentName);
        }
        if (allergenNotes && !bucket.notes.includes(allergenNotes)) {
          bucket.notes.push(allergenNotes);
        }
      }

      for (const tag of tags) {
        const tagKey = String(tag || "").trim().toLowerCase();
        if (!tagKey) {
          continue;
        }
        if (!markerMap.has(tagKey)) {
          markerMap.set(tagKey, []);
        }
        const list = markerMap.get(tagKey);
        if (componentName && !list.includes(componentName)) {
          list.push(componentName);
        }
      }
    }

    if (allergenMap.size === 0 && markerMap.size === 0) {
      renderDishAllergenSummaryEmpty();
      return;
    }

    const allergenSection = document.createElement("section");
    allergenSection.className = "builder-dish-allergen-summary-section";

    const allergenTitle = document.createElement("h4");
    allergenTitle.textContent = "Allergener";
    allergenSection.appendChild(allergenTitle);

    if (allergenMap.size === 0) {
      const empty = document.createElement("p");
      empty.className = "builder-dish-allergen-summary-empty";
      empty.textContent = "Inga allergener registrerade på komponenterna.";
      allergenSection.appendChild(empty);
    } else {
      const list = document.createElement("div");
      list.className = "builder-dish-allergen-grid";
      for (const [allergenKey, value] of allergenMap.entries()) {
        const card = document.createElement("article");
        card.className = "builder-dish-allergen-card";

        const chip = document.createElement("div");
        chip.className = "builder-dish-allergen-chip";
        chip.textContent = _dishAllergenLabel(allergenKey);
        card.appendChild(chip);

        const source = document.createElement("p");
        source.className = "builder-dish-allergen-source";
        source.textContent = value.components.length > 0
          ? "Från: " + value.components.join(", ")
          : "Från komponenterna";
        card.appendChild(source);

        if (value.notes.length > 0) {
          const note = document.createElement("p");
          note.className = "builder-dish-allergen-note";
          note.textContent = value.notes.join(" | ");
          card.appendChild(note);
        }

        list.appendChild(card);
      }
      allergenSection.appendChild(list);
    }

    const markerSection = document.createElement("section");
    markerSection.className = "builder-dish-allergen-summary-section";

    const markerTitle = document.createElement("h4");
    markerTitle.textContent = "Kostmarkörer";
    markerSection.appendChild(markerTitle);

    if (markerMap.size === 0) {
      const empty = document.createElement("p");
      empty.className = "builder-dish-allergen-summary-empty";
      empty.textContent = "Inga kostmarkörer registrerade på komponenterna.";
      markerSection.appendChild(empty);
    } else {
      const markerList = document.createElement("div");
      markerList.className = "builder-dish-allergen-marker-grid";
      for (const [tagKey, sources] of markerMap.entries()) {
        const chip = document.createElement("article");
        chip.className = "builder-dish-allergen-marker";

        const label = document.createElement("div");
        label.className = "builder-dish-allergen-marker-label";
        label.textContent = _dishAllergenLabel(tagKey);
        chip.appendChild(label);

        const source = document.createElement("p");
        source.className = "builder-dish-allergen-marker-source";
        source.textContent = sources.length > 0 ? "Från: " + sources.join(", ") : "Från komponenterna";
        chip.appendChild(source);

        markerList.appendChild(chip);
      }
      markerSection.appendChild(markerList);
    }

    host.appendChild(allergenSection);
    host.appendChild(markerSection);
  }

  function renderDishCalculationSummaryMessage(message) {
    const host = document.getElementById("dishCalculationSummary");
    if (!host) {
      return;
    }
    host.innerHTML = "";
    const text = document.createElement("p");
    text.className = "builder-dish-calculation-summary-empty";
    text.textContent = String(message || "");
    host.appendChild(text);
  }

  function renderDishCalculationSummaryFailure() {
    renderDishCalculationSummaryMessage("Kunde inte läsa komponenterna just nu.");
  }

  function renderDishCalculationSummaryEmpty() {
    renderDishCalculationSummaryMessage("Ingen kalkyl registrerad på komponenterna.");
  }

  function renderDishCalculationSummaryLoading() {
    renderDishCalculationSummaryMessage("Samlar kalkyldata från komponenterna...");
  }

  function parseDishStrictNumericValue(value) {
    const text = String(value || "").trim();
    if (!text) {
      return null;
    }
    if (!/^[-+]?(?:\d+|\d*[\.,]\d+)$/.test(text)) {
      return null;
    }
    return Number(text.replace(",", "."));
  }

  function parseDishCurrencyValue(value) {
    const text = String(value || "").trim();
    if (!text) {
      return null;
    }
    const match = text.match(/[-+]?(?:\d+[\.,]?\d*|\d*[\.,]\d+)/);
    if (!match) {
      return null;
    }
    const parsed = Number(String(match[0]).replace(",", "."));
    return Number.isFinite(parsed) ? parsed : null;
  }

  function formatDishCostValue(value) {
    if (!Number.isFinite(value)) {
      return "";
    }
    return value.toFixed(2);
  }

  function formatDishCalculationValue(value) {
    if (value == null) {
      return "–";
    }
    const parsed = parseDishCurrencyValue(value);
    if (parsed == null) {
      const text = String(value || "").trim();
      return text ? text : "–";
    }
    return formatDishCostValue(parsed) + " kr";
  }

  function formatDishCalculationCell(value, fallback = "–") {
    const text = String(value || "").trim();
    return text ? text : fallback;
  }

  function formatDishCalculationAmount(value, unit) {
    const amountText = String(value || "").trim();
    const unitText = String(unit || "").trim();
    if (!amountText && !unitText) {
      return "–";
    }
    if (!amountText) {
      return "–" + (unitText ? " " + unitText : "");
    }
    if (!unitText) {
      return amountText + " –";
    }
    return amountText + " " + unitText;
  }

  function formatDishCalculationRowCost(value) {
    const parsed = parseDishCurrencyValue(value);
    return parsed == null ? "–" : formatDishCostValue(parsed) + " kr";
  }

  function renderDishCalculationRow(row) {
    const rowCard = document.createElement("article");
    rowCard.className = "builder-dish-calculation-row";

    const ingredient = document.createElement("div");
    ingredient.className = "builder-dish-calculation-row-value";
    ingredient.textContent = formatDishCalculationCell(row && row.ingredient_name);
    rowCard.appendChild(ingredient);

    const amount = document.createElement("div");
    amount.className = "builder-dish-calculation-row-value";
    amount.textContent = formatDishCalculationAmount(row && row.amount_value, row && row.amount_unit);
    rowCard.appendChild(amount);

    const price = document.createElement("div");
    price.className = "builder-dish-calculation-row-value";
    price.textContent = formatDishCalculationValue((row && row.price_value) || "");
    rowCard.appendChild(price);

    const cost = document.createElement("div");
    cost.className = "builder-dish-calculation-row-value builder-dish-calculation-row-value-cost";
    cost.textContent = formatDishCalculationRowCost((row && row.calculated_cost) || "");
    rowCard.appendChild(cost);

    return rowCard;
  }

  function componentsInDisplayOrder(composition) {
    const components = Array.isArray(composition.components) ? composition.components : [];
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

  async function fetchDishLinkedComponentDetailsForCurrentComposition() {
    const composition = _getState("currentBuilderComposition");
    if (!composition || !composition.composition_id) {
      return {
        composition: null,
        compositionId: "",
        linkedComponents: [],
        componentDetails: [],
      };
    }

    const compositionId = String(composition.composition_id || "").trim();
    const linkedComponents = componentsInDisplayOrder(composition);
    const linkedComponentIds = Array.from(new Set(
      linkedComponents
        .map((item) => String(item.component_id || "").trim())
        .filter(Boolean),
    ));

    if (linkedComponentIds.length === 0) {
      return {
        composition,
        compositionId,
        linkedComponents,
        componentDetails: [],
      };
    }

    const componentDetails = await Promise.all(linkedComponents.map(async (linkedComponent) => {
      const componentIdValue = String(linkedComponent.component_id || "").trim();
      if (!componentIdValue) {
        return null;
      }
      try {
        const details = await _fetchComponentDetailDraft(componentIdValue);
        return {
          component: linkedComponent,
          details,
        };
      } catch (error) {
        return {
          component: linkedComponent,
          details: { tags: [], long_description: "", recipe_ingredient_rows: [], recipe_ingredients_text: "", method_text: "", method_notes: "", calculation_yield: "", calculation_cost: "", calculation_notes: "", calculation_rows: [], allergens: [], allergen_notes: "" },
          error: String(error && error.message ? error.message : error || ""),
        };
      }
    }));

    return {
      composition,
      compositionId,
      linkedComponents,
      componentDetails,
    };
  }

  async function loadDishAllergenSummaryForCurrentComposition() {
    const host = document.getElementById("dishAllergensSummary");
    if (!host) {
      return;
    }
    const summaryToken = _setState("currentDishAllergenSummaryToken", Number(_getState("currentDishAllergenSummaryToken") || 0) + 1);
    renderDishAllergenSummaryLoading();

    const payload = await fetchDishLinkedComponentDetailsForCurrentComposition();
    const composition = payload.composition;
    const compositionId = String(payload.compositionId || "").trim();
    const componentDetails = Array.isArray(payload.componentDetails) ? payload.componentDetails : [];

    if (summaryToken !== _getState("currentDishAllergenSummaryToken")) {
      return;
    }
    if (!_getState("currentBuilderComposition") || String(_getState("currentBuilderComposition").composition_id || "").trim() !== compositionId) {
      return;
    }
    if (_getState("currentBuilderDishTab") !== "allergens") {
      return;
    }

    const anyFailure = componentDetails.some((item) => item && item.error);
    if (anyFailure && componentDetails.every((item) => !item || !item.details)) {
      renderDishAllergenSummaryFailure();
      return;
    }

    renderDishAllergenSummary(composition, componentDetails.filter(Boolean));
  }

  async function loadDishCalculationSummaryForCurrentComposition() {
    const host = document.getElementById("dishCalculationSummary");
    if (!host) {
      return;
    }

    const summaryToken = _setState("currentDishCalculationSummaryToken", Number(_getState("currentDishCalculationSummaryToken") || 0) + 1);
    renderDishCalculationSummaryLoading();

    const payload = await fetchDishLinkedComponentDetailsForCurrentComposition();
    const composition = payload.composition;
    const compositionId = String(payload.compositionId || "").trim();
    const componentDetails = Array.isArray(payload.componentDetails) ? payload.componentDetails : [];

    if (summaryToken !== _getState("currentDishCalculationSummaryToken")) {
      return;
    }
    if (!_getState("currentBuilderComposition") || String(_getState("currentBuilderComposition").composition_id || "").trim() !== compositionId) {
      return;
    }
    if (_getState("currentBuilderDishTab") !== "calculation") {
      return;
    }

    if (!composition || !composition.composition_id) {
      renderDishCalculationSummaryEmpty();
      return;
    }

    const anyFailure = componentDetails.some((item) => item && item.error);
    if (anyFailure && componentDetails.every((item) => !item || !item.details)) {
      renderDishCalculationSummaryFailure();
      return;
    }

    renderDishCalculationSummary(composition, componentDetails.filter(Boolean));
  }

  function renderDishCalculationSummary(composition, componentDetails) {
    const host = document.getElementById("dishCalculationSummary");
    if (!host) {
      return;
    }

    host.innerHTML = "";
    const detailsList = Array.isArray(componentDetails) ? componentDetails : [];
    const orderedComponents = componentsInDisplayOrder(composition);
    const detailsByComponentId = new Map();

    detailsList.forEach((entry) => {
      const componentId = String((entry && entry.component && entry.component.component_id) || "").trim();
      if (componentId) {
        detailsByComponentId.set(componentId, entry);
      }
    });

    let totalCost = 0;
    let knownCostCount = 0;
    let anyCalculationData = false;
    let missingCalculationDataCount = 0;

    for (const component of orderedComponents) {
      const componentId = String(component.component_id || "").trim();
      const entry = componentId ? detailsByComponentId.get(componentId) : null;
      const details = entry && entry.details ? entry.details : null;
      const componentName = String(component.component_name || component.component_id || "").trim();
      const calculationCostText = String((details && details.calculation_cost) || "").trim();
      const calculationNotesText = String((details && details.calculation_notes) || "").trim();
      const calculationRows = Array.isArray(details && details.calculation_rows) ? details.calculation_rows : [];
      const hasCalculationData = Boolean(calculationCostText || calculationNotesText || calculationRows.length > 0);
      const hasNumericCost = parseDishCurrencyValue(calculationCostText) != null;

      if (hasCalculationData && !hasNumericCost) {
        missingCalculationDataCount += 1;
      }

      const parsedCost = parseDishCurrencyValue(calculationCostText);
      if (parsedCost != null) {
        totalCost += parsedCost;
        knownCostCount += 1;
      }

      const card = document.createElement("article");
      card.className = "builder-dish-calculation-card";

      const title = document.createElement("div");
      title.className = "builder-dish-calculation-card-title";
      title.textContent = componentName || "Komponent";
      card.appendChild(title);

      if (!hasCalculationData) {
        const missing = document.createElement("p");
        missing.className = "builder-dish-calculation-summary-empty builder-dish-calculation-summary-missing";
        missing.textContent = "Saknar kalkyldata";
        card.appendChild(missing);
        host.appendChild(card);
        continue;
      }

      anyCalculationData = true;

      const metaGrid = document.createElement("div");
      metaGrid.className = "builder-dish-calculation-meta";

      const totalField = document.createElement("div");
      totalField.className = "builder-dish-calculation-meta-item";
      const totalLabel = document.createElement("span");
      totalLabel.className = "builder-dish-calculation-meta-label";
      totalLabel.textContent = "Komponentkostnad";
      const totalValue = document.createElement("span");
      totalValue.className = "builder-dish-calculation-meta-value";
      totalValue.textContent = formatDishCalculationValue(calculationCostText);
      totalField.appendChild(totalLabel);
      totalField.appendChild(totalValue);
      metaGrid.appendChild(totalField);

      if (calculationNotesText) {
        const notesField = document.createElement("div");
        notesField.className = "builder-dish-calculation-meta-item";
        const notesLabel = document.createElement("span");
        notesLabel.className = "builder-dish-calculation-meta-label";
        notesLabel.textContent = "Anteckning";
        const notesValue = document.createElement("span");
        notesValue.className = "builder-dish-calculation-meta-value";
        notesValue.textContent = calculationNotesText;
        notesField.appendChild(notesLabel);
        notesField.appendChild(notesValue);
        metaGrid.appendChild(notesField);
      }

      card.appendChild(metaGrid);

      if (calculationRows.length > 0) {
        const rowsWrap = document.createElement("div");
        rowsWrap.className = "builder-dish-calculation-rows";

        const header = document.createElement("div");
        header.className = "builder-dish-calculation-row builder-dish-calculation-row-head";
        ["Ingrediens", "Mängd", "Pris", "Kostnad"].forEach((labelText) => {
          const label = document.createElement("div");
          label.className = "builder-dish-calculation-row-value";
          label.textContent = labelText;
          header.appendChild(label);
        });
        rowsWrap.appendChild(header);

        calculationRows.forEach((row) => {
          rowsWrap.appendChild(renderDishCalculationRow(row));
        });

        card.appendChild(rowsWrap);
      }

      host.appendChild(card);
    }

    if (!anyCalculationData) {
      renderDishCalculationSummaryEmpty();
      return;
    }

    if (knownCostCount > 0) {
      const totalCard = document.createElement("article");
      totalCard.className = "builder-dish-calculation-total";

      const label = document.createElement("div");
      label.className = "builder-dish-calculation-total-label";
      label.textContent = "Total kalkyl för rätt";
      totalCard.appendChild(label);

      const value = document.createElement("div");
      value.className = "builder-dish-calculation-total-value";
      value.textContent = formatDishCostValue(totalCost) + " kr";
      totalCard.appendChild(value);

      if (missingCalculationDataCount > 0) {
        const warning = document.createElement("p");
        warning.className = "builder-dish-calculation-summary-warning";
        warning.textContent = "Vissa komponenter saknar kalkyldata.";
        totalCard.appendChild(warning);
      }

      host.insertBefore(totalCard, host.firstChild);
    }
  }

  function setDishOverviewStatus(message, isError = false) {
    const statusLine = document.getElementById("resolveStatusLine");
    if (!statusLine) {
      return;
    }
    const value = String(message || "").trim();
    statusLine.textContent = value;
    statusLine.classList.toggle("hidden", !value);
    statusLine.dataset.state = value ? (isError ? "error" : "success") : "idle";
  }

  function syncDishModalHeader(composition) {
    const modalTitle = document.getElementById("resolveModalTitle");
    if (!modalTitle) {
      return;
    }
    modalTitle.textContent = String((composition && composition.composition_name) || "").trim() || "Redigera rätt";
  }

  function syncDishOverviewInputs(composition) {
    const nameInput = document.getElementById("dishOverviewName");
    const categorySelect = document.getElementById("dishOverviewCategorySelect");
    if (nameInput) {
      nameInput.value = String((composition && composition.composition_name) || "");
    }
    if (categorySelect) {
      categorySelect.value = normalizeDishLibraryGroupValue((composition && composition.library_group) || "ovrigt") || "ovrigt";
    }
  }

  function dishOverviewCategoryLabel(composition) {
    const rawValue = String((composition && composition.library_group) || "").trim();
    const key = normalizeDishCategoryKey(rawValue);
    if (key === "fisk") return "Fisk";
    if (key === "kott") return "Kött";
    if (key === "dessert") return "Dessert";
    if (key === "ovrigt") return "Övrigt";
    return rawValue || "Ej kategoriserad";
  }

  async function saveDishOverviewMetadata() {
    const currentBuilderComposition = _getState("currentBuilderComposition");
    if (!currentBuilderComposition || !currentBuilderComposition.composition_id) {
      setDishOverviewStatus("Ingen rätt vald.", true);
      return;
    }

    const nameInput = document.getElementById("dishOverviewName");
    const categorySelect = document.getElementById("dishOverviewCategorySelect");
    const composition_name = String((nameInput && nameInput.value) || "").trim();
    const library_group = normalizeDishLibraryGroupValue((categorySelect && categorySelect.value) || "");

    if (!composition_name) {
      setDishOverviewStatus("Rättnamn måste fyllas i.", true);
      return;
    }
    if (!library_group) {
      setDishOverviewStatus("Välj en giltig kategori.", true);
      return;
    }

    if (_showLoading) {
      _showLoading("builderOut");
    }
    try {
      const result = await _callApi(
        "/api/builder/compositions/" +
          encodeURIComponent(String(currentBuilderComposition.composition_id || "")),
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: {
            composition_name,
            library_group,
          },
        },
      );

      if (_showJson) {
        _showJson("builderOut", result);
      }
      if (!(result && result.status < 400 && result.data && result.data.ok && result.data.composition)) {
        const message = String((result && result.data && (result.data.message || result.data.error)) || "Unable to save dish metadata");
        setDishOverviewStatus(message, true);
        return;
      }

      const savedComposition = result.data.composition;
      _setState("currentBuilderComposition", savedComposition);
      syncDishModalHeader(savedComposition);
      syncDishOverviewInputs(savedComposition);
      setDishOverviewStatus("Ändringarna sparades.");

      if (_loadCompositionTextPreviewForCurrentComposition) {
        await _loadCompositionTextPreviewForCurrentComposition(
          "dishTextPreview",
          "Ingen rätt vald",
          "Läser textvy...",
          "Textvy saknas.",
        ).catch(() => {
          setCompositionTextPreview("dishTextPreview", "Textvy saknas.");
        });
      }

      if (_loadLibrary) {
        await _loadLibrary();
      }
    } catch (error) {
      setDishOverviewStatus(String(error.message || error), true);
    }
  }

  return {
    saveDishOverviewMetadata,
    syncDishModalHeader,
    syncDishOverviewInputs,
    setDishOverviewStatus,
    dishOverviewCategoryLabel,
    renderDishAllergenSummary,
    renderDishAllergenSummaryMessage,
    renderDishAllergenSummaryFailure,
    renderDishAllergenSummaryEmpty,
    renderDishAllergenSummaryLoading,
    renderDishCalculationSummaryMessage,
    renderDishCalculationSummaryFailure,
    renderDishCalculationSummaryEmpty,
    renderDishCalculationSummaryLoading,
    renderDishCalculationRow,
    renderDishCalculationSummary,
    fetchDishLinkedComponentDetailsForCurrentComposition,
    loadDishAllergenSummaryForCurrentComposition,
    loadDishCalculationSummaryForCurrentComposition,
    componentsInDisplayOrder,
  };
}