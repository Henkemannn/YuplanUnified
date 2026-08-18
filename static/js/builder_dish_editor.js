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
  const _dishAllergenLabel = typeof config.dishAllergenLabel === "function"
    ? config.dishAllergenLabel
    : (value) => String(value || "");

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
  };
}