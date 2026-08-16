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
  };
}