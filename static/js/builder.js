function showJson(targetId, value) {
  const el = document.getElementById(targetId);
  if (!el) {
    return;
  }
  el.textContent = JSON.stringify(value, null, 2);
}

function showLoading(targetId) {
  const el = document.getElementById(targetId);
  if (!el) {
    return;
  }
  el.textContent = "Loading...";
}

async function callApi(url, options) {
  const headers = Object.assign({}, options.headers || {});
  let body = undefined;

  if (options.formData) {
    body = options.formData;
    if (headers["Content-Type"]) {
      delete headers["Content-Type"];
    }
  } else if (Object.prototype.hasOwnProperty.call(options, "body")) {
    body = JSON.stringify(options.body);
    if (!headers["Content-Type"]) {
      headers["Content-Type"] = "application/json";
    }
  }

  const response = await fetch(url, {
    method: options.method || "GET",
    headers,
    body,
  });
  const data = await response
    .json()
    .catch(() => ({ ok: false, error: "invalid_json_response", message: "Response was not valid JSON" }));
  return { status: response.status, data };
}

function parseLibraryLines(text) {
  return String(text || "")
    .split(/\r?\n/)
    .map((v) => v.trim())
    .filter(Boolean);
}

function renderImportSummary(result) {
  const host = document.getElementById("importSummaryView");
  if (!host) {
    return;
  }

  host.innerHTML = "";

  const data = (result && result.data) || {};
  const summary = data.summary;
  if (!summary || typeof summary !== "object") {
    const msg = document.createElement("div");
    msg.className = "import-warning-block";
    msg.textContent = String(data.message || data.error || "Import failed");
    host.appendChild(msg);
    return;
  }

  const counts = document.createElement("div");
  counts.className = "import-counts";
  counts.textContent =
    "Imported lines: " +
    String(summary.imported_count || 0) +
    " | Created compositions: " +
    String(summary.created_composition_count || summary.created_count || 0) +
    " | Reused compositions: " +
    String(summary.reused_composition_count || summary.reused_count || 0) +
    " | Created components: " +
    String(summary.created_component_count || 0) +
    " | Reused components: " +
    String(summary.reused_component_count || 0) +
    " | Ignored noise: " +
    String(summary.ignored_noise_count || 0);
  host.appendChild(counts);

  const summaryWarnings = Array.isArray(summary.warnings) ? summary.warnings : [];
  if (summaryWarnings.length > 0) {
    const warningBlock = document.createElement("div");
    warningBlock.className = "import-warning-block";
    warningBlock.textContent = "Warnings: " + summaryWarnings.join(" | ");
    host.appendChild(warningBlock);
  }

  const rows = Array.isArray(summary.row_results) ? summary.row_results : [];
  for (const row of rows) {
    const item = document.createElement("div");
    item.className = "import-row-result";

    const badge = document.createElement("span");
    badge.className = "status-resolved";
    const via = String(row.matched_via || "").toLowerCase();
    badge.textContent = via === "created" ? "Created composition" : "Reused composition";

    const primary = document.createElement("span");
    primary.className = "import-row-primary";
    primary.textContent = String(row.raw_text || "");

    item.appendChild(badge);
    item.appendChild(primary);

    if (row.composition_id) {
      const secondary = document.createElement("div");
      secondary.className = "import-row-secondary";
      secondary.textContent =
        "composition_id: " +
        String(row.composition_id) +
        " | composition_name: " +
        String(row.composition_name || "");
      item.appendChild(secondary);
    }

    const rowWarnings = Array.isArray(row.warnings) ? row.warnings : [];
    for (const warning of rowWarnings) {
      const w = document.createElement("div");
      w.className = "import-row-warning";
      w.textContent = String(warning || "");
      item.appendChild(w);
    }

    host.appendChild(item);
  }
}

const IMPORT_PREVIEW_INITIAL_CHUNK = 40;
const IMPORT_PREVIEW_CHUNK_SIZE = 40;

let pendingFileImportItems = [];
let pendingFileIgnoredItems = [];
let importPreviewVisibleCount = 0;
let importIgnoredExpanded = false;

function selectedFileImportLines() {
  const selected = [];
  for (const item of pendingFileImportItems) {
    if (item && item.selected) {
      selected.push(String(item.line || ""));
    }
  }
  return selected;
}

function updateFileImportControls() {
  const confirmBtn = document.getElementById("btnImportFileConfirm");
  const selectSummary = document.getElementById("importFileSelectionSummary");
  const ignoredSummary = document.getElementById("importFileIgnoredSummary");
  const showMoreBtn = document.getElementById("btnImportPreviewShowMore");
  const toggleIgnoredBtn = document.getElementById("btnImportPreviewToggleIgnored");

  const total = pendingFileImportItems.length;
  const selectedCount = selectedFileImportLines().length;
  const visibleCount = Math.min(importPreviewVisibleCount, total);
  const ignoredCount = pendingFileIgnoredItems.length;

  if (confirmBtn) {
    confirmBtn.disabled = selectedCount === 0;
  }

  if (selectSummary) {
    selectSummary.textContent =
      "Selected " +
      String(selectedCount) +
      " of " +
      String(total) +
      " importable lines (showing " +
      String(visibleCount) +
      ")";
  }

  if (ignoredSummary) {
    ignoredSummary.textContent = "Ignored noise: " + String(ignoredCount);
  }

  if (showMoreBtn) {
    showMoreBtn.disabled = visibleCount >= total;
    showMoreBtn.textContent =
      visibleCount >= total
        ? "All importable lines visible"
        : "Show more importable lines";
  }

  if (toggleIgnoredBtn) {
    toggleIgnoredBtn.disabled = ignoredCount === 0;
    toggleIgnoredBtn.textContent = importIgnoredExpanded ? "Hide ignored lines" : "Show ignored lines";
  }
}

function renderImportablePreviewList() {
  const list = document.getElementById("importFilePreviewList");
  if (!list) {
    return;
  }

  list.innerHTML = "";
  const visibleCount = Math.min(importPreviewVisibleCount, pendingFileImportItems.length);
  for (let index = 0; index < visibleCount; index += 1) {
    const itemData = pendingFileImportItems[index] || {};
    const item = document.createElement("li");
    item.className = "import-preview-item";

    const label = document.createElement("label");
    label.className = "import-preview-line";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = Boolean(itemData.selected);
    checkbox.dataset.previewId = String(itemData.previewId || index);

    const text = document.createElement("span");
    text.textContent = String(itemData.line || "");

    label.appendChild(checkbox);
    label.appendChild(text);
    item.appendChild(label);
    list.appendChild(item);
  }
}

function renderIgnoredPreviewList() {
  const ignoredList = document.getElementById("importFileIgnoredList");
  if (!ignoredList) {
    return;
  }

  ignoredList.innerHTML = "";
  if (!importIgnoredExpanded) {
    ignoredList.classList.add("hidden");
    return;
  }

  ignoredList.classList.remove("hidden");
  for (const itemData of pendingFileIgnoredItems) {
    const item = document.createElement("li");
    const text = String(itemData.normalized_text || itemData.raw_text || "");
    const reason = String(itemData.reason || "ignored_noise");
    item.textContent = text + " (" + reason + ")";
    ignoredList.appendChild(item);
  }
}

function refreshFilePreviewLists() {
  renderImportablePreviewList();
  renderIgnoredPreviewList();
  updateFileImportControls();
}

function toggleAllImportableLines(selected) {
  for (const item of pendingFileImportItems) {
    item.selected = Boolean(selected);
  }
  refreshFilePreviewLists();
}

function setFileImportStatus(message, isError) {
  const status = document.getElementById("importFileStatus");
  if (!status) {
    return;
  }
  status.textContent = String(message || "");
  status.className = isError ? "import-warning-block" : "";
}

function renderFileImportPreview(result) {
  pendingFileImportItems = [];
  pendingFileIgnoredItems = [];
  importPreviewVisibleCount = 0;
  importIgnoredExpanded = false;
  refreshFilePreviewLists();

  const data = (result && result.data) || {};
  const preview = data.preview || {};
  const lines = Array.isArray(preview.importable_lines)
    ? preview.importable_lines
    : (Array.isArray(preview.lines) ? preview.lines : []);
  const importableItems = Array.isArray(preview.importable_items)
    ? preview.importable_items
    : lines.map((line, index) => ({ preview_index: index, line }));
  const ignored = Array.isArray(preview.ignored_lines) ? preview.ignored_lines : [];
  if (!result || result.status >= 400 || importableItems.length === 0) {
    setFileImportStatus(String(data.message || data.error || "Unable to preview file"), true);
    return;
  }

  pendingFileImportItems = importableItems.map((item, index) => ({
    previewId: Number.isInteger(item.preview_index) ? item.preview_index : index,
    line: String(item.line || lines[index] || ""),
    selected: true,
  }));
  pendingFileIgnoredItems = ignored;
  importPreviewVisibleCount = Math.min(IMPORT_PREVIEW_INITIAL_CHUNK, pendingFileImportItems.length);

  if (pendingFileImportItems.length > 0 && importPreviewVisibleCount === 0) {
    importPreviewVisibleCount = pendingFileImportItems.length;
  }
  refreshFilePreviewLists();

  setFileImportStatus(
    "Preview ready: " +
      String(preview.line_count || pendingFileImportItems.length) +
      " importable lines, " +
      String(pendingFileIgnoredItems.length) +
      " ignored from " +
      String(preview.file_type || "file"),
    false,
  );
}

async function loadAllCompositions() {
  return callApi("/api/builder/compositions", { method: "GET" });
}

function renderLibrary(result) {
  const componentsGrid = document.getElementById("libraryComponentsGrid");
  const compositionsGrid = document.getElementById("libraryCompositionsGrid");
  if (!componentsGrid || !compositionsGrid) {
    return;
  }

  componentsGrid.innerHTML = "";
  compositionsGrid.innerHTML = "";

  const data = (result && result.data) || {};
  const components = Array.isArray(data.components) ? data.components : [];
  const compositions = Array.isArray(data.compositions) ? data.compositions : [];

  if (components.length === 0) {
    const empty = document.createElement("div");
    empty.className = "library-empty";
    empty.textContent = "No components yet";
    componentsGrid.appendChild(empty);
  } else {
    for (const item of components) {
      const componentId = String(item.component_id || "");
      const componentName = String(item.component_name || item.component_id || "");
      const hasPrimaryRecipe = Boolean(String(item.primary_recipe_id || "").trim());

      const card = document.createElement("article");
      card.className = "component-library-card";

      const openSurface = document.createElement("button");
      openSurface.type = "button";
      openSurface.className = "component-library-card-surface";
      openSurface.addEventListener("click", () => {
        openRecipeModalForComponent(componentId, componentName);
      });

      const name = document.createElement("div");
      name.className = "component-library-card-name";
      name.textContent = componentName;

      const status = document.createElement("div");
      status.className = "component-library-card-status";
      status.textContent = hasPrimaryRecipe ? "Primary recipe linked" : "No primary recipe yet";
      status.classList.add(
        hasPrimaryRecipe
          ? "component-library-card-status-has-data"
          : "component-library-card-status-no-data",
      );

      openSurface.appendChild(name);
      openSurface.appendChild(status);

      const openBtn = document.createElement("button");
      openBtn.type = "button";
      openBtn.className = "library-component-open-btn";
      openBtn.textContent = "Open component detail";
      openBtn.addEventListener("click", () => {
        openRecipeModalForComponent(componentId, componentName);
      });

      card.appendChild(openSurface);
      card.appendChild(openBtn);
      componentsGrid.appendChild(card);
    }
  }

  if (compositions.length === 0) {
    const empty = document.createElement("div");
    empty.className = "library-empty";
    empty.textContent = "No dishes yet";
    compositionsGrid.appendChild(empty);
  } else {
    for (const item of compositions) {
      const compositionId = String(item.composition_id || "");
      const compositionName = String(item.composition_name || item.composition_id || "");

      const card = document.createElement("article");
      card.className = "composition-library-card";

      const openSurface = document.createElement("button");
      openSurface.type = "button";
      openSurface.className = "composition-library-card-surface";
      openSurface.addEventListener("click", async () => {
        await openCompositionFromLibrary(compositionId);
      });

      const name = document.createElement("div");
      name.className = "composition-library-card-name";
      name.textContent = compositionName;

      const status = document.createElement("div");
      status.className = "composition-library-card-status";
      status.textContent = "Reusable composition";

      openSurface.appendChild(name);
      openSurface.appendChild(status);

      const open = document.createElement("button");
      open.className = "library-composition-open-btn";
      open.type = "button";
      open.textContent = "Open dish editor";
      open.addEventListener("click", async () => {
        await openCompositionFromLibrary(compositionId);
      });

      card.appendChild(openSurface);
      card.appendChild(open);
      compositionsGrid.appendChild(card);
    }
  }
}

async function openCompositionFromLibrary(compositionId) {
  const compositionIdValue = String(compositionId || "");
  if (!compositionIdValue) {
    return;
  }

  const all = await loadAllCompositions();
  const list = (all.data && all.data.compositions) || [];
  const full = list.find(
    (candidate) =>
      String(candidate.composition_id || "") === compositionIdValue,
  );
  if (full) {
    openBuilderModalForComposition(full);
  }
}

async function loadLibrary() {
  const result = await callApi("/api/builder/library", { method: "GET" });
  renderLibrary(result);
}

let currentBuilderComposition = null;
let reusableComponentsCache = [];
let selectedComponentId = null;
let draggedComponentEntryKey = null;

function componentEntryKey(component) {
  return String(component.component_id || "") + "::" + String(component.sort_order || 0);
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

async function persistComponentOrder(compositionId, orderedComponents) {
  const orderedEntries = orderedComponents.map((item) => ({
    component_id: String(item.component_id || ""),
    sort_order: Number(item.sort_order || 0),
  }));

  const result = await callApi(
    "/api/builder/compositions/" + encodeURIComponent(String(compositionId || "")) + "/components/reorder",
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: { ordered_entries: orderedEntries },
    },
  );
  showJson("builderOut", result);
  if (result && result.data && result.data.ok && result.data.composition) {
    renderBuilderPanel(result.data.composition);
  }
}

async function reorderCompositionBlocksByEntryKey(fromEntryKey, toEntryKey) {
  if (!currentBuilderComposition || !currentBuilderComposition.composition_id) {
    return;
  }
  const fromKey = String(fromEntryKey || "");
  const toKey = String(toEntryKey || "");
  if (!fromKey || !toKey || fromKey === toKey) {
    return;
  }

  const ordered = componentsInDisplayOrder(currentBuilderComposition);
  const fromIndex = ordered.findIndex((item) => componentEntryKey(item) === fromKey);
  const toIndex = ordered.findIndex((item) => componentEntryKey(item) === toKey);
  if (fromIndex < 0 || toIndex < 0 || fromIndex === toIndex) {
    return;
  }

  const moved = ordered.splice(fromIndex, 1)[0];
  ordered.splice(toIndex, 0, moved);
  await persistComponentOrder(currentBuilderComposition.composition_id, ordered);
}
let currentRecipeComponent = null;
let currentRecipeList = [];
let currentSelectedRecipeId = null;
let currentSelectedRecipe = null;
let currentSelectedRecipeLines = [];

function setComponentDetailTextPreview(message) {
  const preview = document.getElementById("componentDetailTextPreview");
  if (!preview) {
    return;
  }
  preview.textContent = String(message || "");
}

async function loadCompositionTextPreviewForCurrentComposition() {
  if (!currentBuilderComposition || !currentBuilderComposition.composition_id) {
    setComponentDetailTextPreview("No composition selected");
    return;
  }

  setComponentDetailTextPreview("Loading composition text preview...");
  const result = await callApi(
    "/api/builder/compositions/" +
      encodeURIComponent(String(currentBuilderComposition.composition_id || "")) +
      "/render/text",
    { method: "GET" },
  );
  if (!result || result.status >= 400 || !result.data || !result.data.ok) {
    setComponentDetailTextPreview("Composition text preview unavailable");
    return;
  }

  const rendered = result.data.rendered || {};
  setComponentDetailTextPreview(String(rendered.text || ""));
}

function findCachedComponentById(componentId) {
  const idValue = String(componentId || "").trim();
  if (!idValue) {
    return null;
  }
  for (const item of reusableComponentsCache) {
    if (String(item.component_id || "") === idValue) {
      return item;
    }
  }
  return null;
}

function selectComponentBlock(componentId) {
  selectedComponentId = String(componentId || "").trim() || null;
  if (currentBuilderComposition) {
    renderBuilderPanel(currentBuilderComposition);
  }
}

async function setComponentRoleWithPrompt(component) {
  const nextRole = window.prompt(
    "Role (optional, leave empty to clear)",
    String(component.role || ""),
  );
  if (nextRole === null) {
    return;
  }
  await updateComponentRoleInCurrentComposition(
    String(component.component_id || ""),
    String(nextRole || "").trim(),
  );
}

function setRecipeEditControlsDisabled(disabled) {
  const editName = document.getElementById("recipeEditName");
  const editYield = document.getElementById("recipeEditYieldPortions");
  const editVisibility = document.getElementById("recipeEditVisibility");
  const editNotes = document.getElementById("recipeEditNotes");
  const saveMetadataBtn = document.getElementById("btnRecipeSaveMetadata");
  const deleteRecipeBtn = document.getElementById("btnRecipeDelete");
  const setPrimaryBtn = document.getElementById("btnRecipeSetPrimary");
  const addIngredientBtn = document.getElementById("btnRecipeIngredientAdd");

  if (editName) {
    editName.disabled = disabled;
  }
  if (editYield) {
    editYield.disabled = disabled;
  }
  if (editVisibility) {
    editVisibility.disabled = disabled;
  }
  if (editNotes) {
    editNotes.disabled = disabled;
  }
  if (saveMetadataBtn) {
    saveMetadataBtn.disabled = disabled;
  }
  if (deleteRecipeBtn) {
    deleteRecipeBtn.disabled = disabled;
  }
  if (setPrimaryBtn) {
    setPrimaryBtn.disabled = disabled;
  }
  if (addIngredientBtn) {
    addIngredientBtn.disabled = disabled;
  }
}

function resetRecipePanel(message) {
  currentRecipeComponent = null;
  currentRecipeList = [];
  currentSelectedRecipeId = null;
  currentSelectedRecipe = null;
  currentSelectedRecipeLines = [];

  const componentTitle = document.getElementById("componentDetailComponentTitle");
  const primaryStatus = document.getElementById("recipePrimaryStatus");
  const recipeList = document.getElementById("recipeList");
  const selectedSummary = document.getElementById("recipeSelectedSummary");
  const ingredientList = document.getElementById("recipeIngredientsList");
  const setPrimaryBtn = document.getElementById("btnRecipeSetPrimary");
  const addIngredientBtn = document.getElementById("btnRecipeIngredientAdd");
  const editName = document.getElementById("recipeEditName");
  const editYield = document.getElementById("recipeEditYieldPortions");
  const editVisibility = document.getElementById("recipeEditVisibility");
  const editNotes = document.getElementById("recipeEditNotes");

  if (componentTitle) {
    componentTitle.textContent = String(message || "Component: not selected");
  }
  if (primaryStatus) {
    primaryStatus.textContent = "";
  }
  if (recipeList) {
    recipeList.innerHTML = "";
  }
  if (selectedSummary) {
    selectedSummary.textContent = "No recipe selected";
  }
  if (ingredientList) {
    ingredientList.innerHTML = "";
  }
  if (editName) {
    editName.value = "";
  }
  if (editYield) {
    editYield.value = "";
  }
  if (editVisibility) {
    editVisibility.value = "";
  }
  if (editNotes) {
    editNotes.value = "";
  }
  if (setPrimaryBtn) {
    setPrimaryBtn.disabled = true;
  }
  if (addIngredientBtn) {
    addIngredientBtn.disabled = true;
  }
  setRecipeEditControlsDisabled(true);
  setComponentDetailTextPreview("No composition selected");
}

function renderRecipeList() {
  const recipeList = document.getElementById("recipeList");
  const primaryStatus = document.getElementById("recipePrimaryStatus");
  if (!recipeList) {
    return;
  }

  recipeList.innerHTML = "";
  const recipes = Array.isArray(currentRecipeList) ? currentRecipeList : [];
  if (recipes.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No recipes yet";
    recipeList.appendChild(li);
  } else {
    for (const recipe of recipes) {
      const li = document.createElement("li");
      li.className = "recipe-item";

      const left = document.createElement("span");
      const isPrimary = Boolean(recipe.is_primary);
      left.textContent =
        String(recipe.recipe_name || recipe.recipe_id || "") +
        " (yield " +
        String(recipe.yield_portions || "?") +
        ")";
      if (isPrimary) {
        const badge = document.createElement("span");
        badge.className = "recipe-primary-badge";
        badge.textContent = " [primary]";
        left.appendChild(badge);
      }

      const open = document.createElement("button");
      open.type = "button";
      open.textContent = "Open";
      open.addEventListener("click", () => {
        loadRecipeDetail(String(recipe.recipe_id || ""));
      });

      li.appendChild(left);
      li.appendChild(open);
      recipeList.appendChild(li);
    }
  }

  const primary = recipes.find((item) => Boolean(item.is_primary));
  if (primaryStatus) {
    primaryStatus.textContent = primary
      ? "Primary recipe: " + String(primary.recipe_name || primary.recipe_id || "")
      : "Primary recipe: none selected";
  }
}

function renderRecipeIngredientLines(lines) {
  const ingredientList = document.getElementById("recipeIngredientsList");
  if (!ingredientList) {
    return;
  }

  ingredientList.innerHTML = "";
  if (!Array.isArray(lines) || lines.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No ingredients yet";
    ingredientList.appendChild(li);
    return;
  }

  for (const line of lines) {
    const li = document.createElement("li");
    li.className = "recipe-item";

    const left = document.createElement("span");
    left.textContent =
      String(line.ingredient_name || "") +
      ": " +
      String(line.amount_value || "") +
      " " +
      String(line.amount_unit || "") +
      (line.note ? " (" + String(line.note) + ")" : "") +
      " | sort " +
      String(line.sort_order || 0);

    const right = document.createElement("span");

    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.textContent = "Edit";
    editBtn.addEventListener("click", async () => {
      const ingredientName = String(
        window.prompt("Ingredient name", String(line.ingredient_name || "")) || "",
      ).trim();
      if (!ingredientName) {
        return;
      }
      const amountValueRaw = String(
        window.prompt("Amount value", String(line.amount_value || "")) || "",
      ).trim();
      const amountUnit = String(
        window.prompt("Amount unit", String(line.amount_unit || "")) || "",
      ).trim();
      const note = String(
        window.prompt("Note (optional)", String(line.note || "")) || "",
      ).trim();
      const sortRaw = String(
        window.prompt("Sort order", String(line.sort_order || 0)) || "",
      ).trim();
      if (!amountValueRaw || !amountUnit) {
        return;
      }

      showLoading("recipeOut");
      try {
        const result = await callApi(
          "/api/builder/components/" +
            encodeURIComponent(String(currentRecipeComponent.component_id)) +
            "/recipes/" +
            encodeURIComponent(String(currentSelectedRecipeId)) +
            "/ingredients/" +
            encodeURIComponent(String(line.recipe_ingredient_line_id || "")),
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: {
              ingredient_name: ingredientName,
              amount_value: Number(amountValueRaw),
              amount_unit: amountUnit,
              note,
              sort_order: Number(sortRaw || 0),
            },
          },
        );
        showJson("recipeOut", result);
        if (result && result.data && result.data.ok) {
          await loadRecipeDetail(String(currentSelectedRecipeId || ""));
        }
      } catch (error) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });

    const deleteBtn = document.createElement("button");
    deleteBtn.type = "button";
    deleteBtn.textContent = "Delete";
    deleteBtn.addEventListener("click", async () => {
      const confirmed = window.confirm("Delete this ingredient row?");
      if (!confirmed) {
        return;
      }
      showLoading("recipeOut");
      try {
        const result = await callApi(
          "/api/builder/components/" +
            encodeURIComponent(String(currentRecipeComponent.component_id)) +
            "/recipes/" +
            encodeURIComponent(String(currentSelectedRecipeId)) +
            "/ingredients/" +
            encodeURIComponent(String(line.recipe_ingredient_line_id || "")),
          { method: "DELETE" },
        );
        showJson("recipeOut", result);
        if (result && result.data && result.data.ok) {
          await loadRecipeDetail(String(currentSelectedRecipeId || ""));
        }
      } catch (error) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });

    right.appendChild(editBtn);
    right.appendChild(deleteBtn);
    li.appendChild(left);
    li.appendChild(right);
    ingredientList.appendChild(li);
  }
}

async function loadRecipesForComponent(componentId, componentName) {
  const componentIdValue = String(componentId || "").trim();
  if (!componentIdValue) {
    resetRecipePanel("Invalid component id");
    return;
  }

  showLoading("recipeOut");
  const result = await callApi(
    "/api/builder/components/" + encodeURIComponent(componentIdValue) + "/recipes",
    { method: "GET" },
  );
  showJson("recipeOut", result);
  if (!result || result.status >= 400 || !result.data || !result.data.ok) {
    resetRecipePanel("Failed to load recipes for component");
    return;
  }

  currentRecipeComponent = result.data.component || {
    component_id: componentIdValue,
    component_name: componentName,
  };
  currentRecipeList = Array.isArray(result.data.recipes) ? result.data.recipes : [];
  currentSelectedRecipeId = null;

  const componentTitle = document.getElementById("componentDetailComponentTitle");
  const modalTitle = document.getElementById("componentDetailModalTitle");
  const resolvedName = String(
    currentRecipeComponent.component_name || componentName || componentIdValue,
  );
  if (modalTitle) {
    modalTitle.textContent = "Component detail: " + resolvedName;
  }
  if (componentTitle) {
    componentTitle.textContent = "Component: " + resolvedName;
  }

  const selectedSummary = document.getElementById("recipeSelectedSummary");
  if (selectedSummary) {
    selectedSummary.textContent = "No recipe selected";
  }
  const ingredientList = document.getElementById("recipeIngredientsList");
  if (ingredientList) {
    ingredientList.innerHTML = "";
  }
  const setPrimaryBtn = document.getElementById("btnRecipeSetPrimary");
  const addIngredientBtn = document.getElementById("btnRecipeIngredientAdd");
  if (setPrimaryBtn) {
    setPrimaryBtn.disabled = true;
  }
  if (addIngredientBtn) {
    addIngredientBtn.disabled = true;
  }

  renderRecipeList();
}

function openRecipeModalForComponent(componentId, componentName) {
  const componentDetailModal = document.getElementById("componentDetailModal");
  if (!componentDetailModal) {
    return;
  }
  componentDetailModal.classList.remove("hidden");
  Promise.all([
    loadRecipesForComponent(componentId, componentName),
    loadCompositionTextPreviewForCurrentComposition(),
  ]).catch((error) => {
    showJson("recipeOut", {
      status: 0,
      data: { ok: false, error: String(error.message || error) },
    });
  });
}

function closeRecipeModal() {
  const componentDetailModal = document.getElementById("componentDetailModal");
  if (componentDetailModal) {
    componentDetailModal.classList.add("hidden");
  }
  resetRecipePanel("Component: not selected");
}

async function loadRecipeDetail(recipeId) {
  if (!currentRecipeComponent || !currentRecipeComponent.component_id) {
    return;
  }
  const recipeIdValue = String(recipeId || "").trim();
  if (!recipeIdValue) {
    return;
  }

  showLoading("recipeOut");
  const result = await callApi(
    "/api/builder/components/" +
      encodeURIComponent(String(currentRecipeComponent.component_id)) +
      "/recipes/" +
      encodeURIComponent(recipeIdValue),
    { method: "GET" },
  );
  showJson("recipeOut", result);
  if (!result || result.status >= 400 || !result.data || !result.data.ok) {
    return;
  }

  currentSelectedRecipeId = recipeIdValue;
  const recipe = result.data.recipe || {};
  const lines = Array.isArray(result.data.ingredient_lines) ? result.data.ingredient_lines : [];
  currentSelectedRecipe = recipe;
  currentSelectedRecipeLines = lines;

  const selectedSummary = document.getElementById("recipeSelectedSummary");
  if (selectedSummary) {
    selectedSummary.textContent =
      "Selected: " +
      String(recipe.recipe_name || recipe.recipe_id || "") +
      " | Yield " +
      String(recipe.yield_portions || "?");
  }

  renderRecipeIngredientLines(lines);

  const editName = document.getElementById("recipeEditName");
  const editYield = document.getElementById("recipeEditYieldPortions");
  const editVisibility = document.getElementById("recipeEditVisibility");
  const editNotes = document.getElementById("recipeEditNotes");
  if (editName) {
    editName.value = String(recipe.recipe_name || "");
  }
  if (editYield) {
    editYield.value = String(recipe.yield_portions || "");
  }
  if (editVisibility) {
    editVisibility.value = String(recipe.visibility || "");
  }
  if (editNotes) {
    editNotes.value = String(recipe.notes || "");
  }

  setRecipeEditControlsDisabled(false);
}

function renderExistingComponentSuggestions(components) {
  const optionsHost = document.getElementById("componentNameSuggestions");
  if (!optionsHost) {
    return;
  }

  optionsHost.innerHTML = "";
  const items = Array.isArray(components) ? components : [];
  for (const item of items) {
    const option = document.createElement("option");
    option.value = String(item.component_name || item.component_id || "");
    optionsHost.appendChild(option);
  }
}

function renderComponentPalette() {
  const palette = document.getElementById("builderComponentPalette");
  const searchInput = document.getElementById("builderPaletteSearch");
  if (!palette) {
    return;
  }

  palette.innerHTML = "";
  const composition = currentBuilderComposition;
  const components = Array.isArray(reusableComponentsCache) ? reusableComponentsCache : [];

  if (!composition || components.length === 0) {
    const empty = document.createElement("div");
    empty.className = "component-palette-empty";
    empty.textContent = "No reusable components yet";
    palette.appendChild(empty);
    return;
  }

  const searchValue = searchInput ? String(searchInput.value || "").trim().toLowerCase() : "";
  const existingIds = new Set(
    (Array.isArray(composition.components) ? composition.components : []).map((item) =>
      String(item.component_id || ""),
    ),
  );

  let renderedCount = 0;

  for (const component of components) {
    const componentId = String(component.component_id || "");
    const componentName = String(component.component_name || componentId || "");
    if (searchValue && !componentName.toLowerCase().includes(searchValue)) {
      continue;
    }
    const isAlreadyIncluded = existingIds.has(componentId);
    const hasPrimaryRecipe = Boolean(String(component.primary_recipe_id || "").trim());

    const pill = document.createElement("button");
    pill.type = "button";
    pill.className = "component-palette-pill";
    pill.textContent = componentName;
    pill.title = isAlreadyIncluded ? "Already included in this dish" : "Add component to dish";
    if (hasPrimaryRecipe) {
      pill.classList.add("component-palette-pill-has-data");
    }
    if (isAlreadyIncluded) {
      pill.classList.add("component-palette-pill-included");
      pill.disabled = true;
    } else {
      pill.addEventListener("click", async () => {
        await attachExistingComponentToCurrentComposition(componentId);
      });
    }

    palette.appendChild(pill);
    renderedCount += 1;
  }

  if (renderedCount === 0) {
    const empty = document.createElement("div");
    empty.className = "component-palette-empty";
    empty.textContent = searchValue ? "No components match search" : "No reusable components yet";
    palette.appendChild(empty);
  }
}

async function loadReusableComponents(query) {
  const queryValue = String(query || "").trim();
  let url = "/api/builder/components";
  if (queryValue) {
    url += "?q=" + encodeURIComponent(queryValue);
  }

  const result = await callApi(url, { method: "GET" });
  const items = (result && result.data && result.data.components) || [];
  reusableComponentsCache = Array.isArray(items) ? items : [];
  renderExistingComponentSuggestions(reusableComponentsCache);
  renderComponentPalette();
  if (currentBuilderComposition) {
    renderBuilderPanel(currentBuilderComposition);
  }
}

function renderBuilderPanel(composition) {
  const title = document.getElementById("builderCompositionTitle");
  const list = document.getElementById("builderComponentsList");
  const roleSummary = document.getElementById("builderRoleSummary");

  if (!title || !list || !composition) {
    return;
  }

  currentBuilderComposition = composition;
  resetRecipePanel("Component: not selected");
  title.textContent = "Dish: " + String(composition.composition_name || "");
  list.innerHTML = "";

  const components = Array.isArray(composition.components) ? composition.components : [];
  const missingRoleCount = components.filter((item) => !String(item.role || "").trim()).length;
  if (roleSummary) {
    roleSummary.textContent =
      "Missing role: " +
      String(missingRoleCount) +
      " | With role: " +
      String(Math.max(0, components.length - missingRoleCount));
    roleSummary.className =
      missingRoleCount > 0 ? "builder-role-summary builder-role-summary-missing" : "builder-role-summary";
  }

  if (components.length === 0) {
    selectedComponentId = null;
    const li = document.createElement("li");
    li.textContent = "No parts added yet";
    list.appendChild(li);
    renderComponentPalette();
    return;
  }

  const componentIds = new Set(components.map((item) => String(item.component_id || "")));
  if (!selectedComponentId || !componentIds.has(selectedComponentId)) {
    selectedComponentId = String(components[0].component_id || "");
  }

  const visibleComponents = componentsInDisplayOrder(composition);

  for (const component of visibleComponents) {
    const componentIdValue = String(component.component_id || "");
    const cached = findCachedComponentById(componentIdValue);
    const hasRecipeData = Boolean(cached && String(cached.primary_recipe_id || "").trim());

    const li = document.createElement("li");
    li.className = "component-list-item";
    if (!String(component.role || "").trim()) {
      li.classList.add("component-list-item-missing-role");
    }
    const block = document.createElement("div");
    block.className = "component-block";
      block.draggable = true;
      const entryKey = componentEntryKey(component);
      block.dataset.entryKey = entryKey;
    if (selectedComponentId === componentIdValue) {
      block.classList.add("component-block-selected");
        block.addEventListener("dragstart", (event) => {
          draggedComponentEntryKey = entryKey;
          block.classList.add("component-block-dragging");
          if (event && event.dataTransfer) {
            event.dataTransfer.effectAllowed = "move";
            event.dataTransfer.setData("text/plain", entryKey);
          }
        });
        block.addEventListener("dragend", () => {
          draggedComponentEntryKey = null;
          block.classList.remove("component-block-dragging");
          const allBlocks = list.querySelectorAll(".component-block-drop-target");
          for (const element of allBlocks) {
            element.classList.remove("component-block-drop-target");
          }
        });
        block.addEventListener("dragover", (event) => {
          if (!draggedComponentEntryKey || draggedComponentEntryKey === entryKey) {
            return;
          }
          event.preventDefault();
          if (event && event.dataTransfer) {
            event.dataTransfer.dropEffect = "move";
          }
          block.classList.add("component-block-drop-target");
        });
        block.addEventListener("dragleave", () => {
          block.classList.remove("component-block-drop-target");
        });
        block.addEventListener("drop", async (event) => {
          event.preventDefault();
          block.classList.remove("component-block-drop-target");
          const fromKey = draggedComponentEntryKey || "";
          draggedComponentEntryKey = null;
          if (!fromKey || fromKey === entryKey) {
            return;
          }
          showLoading("builderOut");
          try {
            await reorderCompositionBlocksByEntryKey(fromKey, entryKey);
          } catch (error) {
            showJson("builderOut", {
              status: 0,
              data: { ok: false, error: String(error.message || error) },
            });
          }
        });
    }

    const surface = document.createElement("button");
    surface.type = "button";
    surface.className = "component-block-surface";
    surface.addEventListener("click", () => {
      selectComponentBlock(componentIdValue);
    });

    const left = document.createElement("div");
    left.className = "component-row-left";

    const name = document.createElement("span");
    name.className = "component-name";
    name.textContent = String(component.component_name || component.component_id || "");

    const roleTag = document.createElement("span");
    roleTag.className = "component-role-tag";
    const roleValue = String(component.role || "").trim();
    if (roleValue) {
      roleTag.textContent = "role: " + roleValue;
    } else {
      roleTag.textContent = "missing role";
      roleTag.classList.add("component-role-tag-missing");
    }
    left.appendChild(name);
    left.appendChild(roleTag);
    surface.appendChild(left);

    const dataIcon = document.createElement("button");
    dataIcon.className = "component-data-icon";
    dataIcon.type = "button";
    dataIcon.textContent = "R";
    dataIcon.title = hasRecipeData
      ? "Open component details for this component (recipe data exists)"
      : "Open component details for this component";
    dataIcon.classList.add(hasRecipeData ? "component-data-icon-has-data" : "component-data-icon-no-data");
    dataIcon.addEventListener("click", () => {
      selectComponentBlock(componentIdValue);
      openRecipeModalForComponent(
        componentIdValue,
        String(component.component_name || component.component_id || ""),
      );
    });

    const overflow = document.createElement("details");
    overflow.className = "component-overflow";

    const overflowSummary = document.createElement("summary");
    overflowSummary.textContent = "...";

    const menu = document.createElement("div");
    menu.className = "component-overflow-menu";

    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.textContent = "Rename";
    renameBtn.addEventListener("click", () => {
      overflow.removeAttribute("open");
      renameComponentInCurrentComposition(
        componentIdValue,
        String(component.component_name || component.component_id || ""),
      );
    });

    const roleBtn = document.createElement("button");
    roleBtn.type = "button";
    roleBtn.textContent = "Set role";
    roleBtn.addEventListener("click", async () => {
      overflow.removeAttribute("open");
      await setComponentRoleWithPrompt(component);
    });

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "Remove";
    removeBtn.addEventListener("click", () => {
      overflow.removeAttribute("open");
      removeComponentFromCurrentComposition(componentIdValue);
    });

    menu.appendChild(renameBtn);
    menu.appendChild(roleBtn);
    menu.appendChild(removeBtn);
    overflow.appendChild(overflowSummary);
    overflow.appendChild(menu);

    const right = document.createElement("div");
    right.className = "component-row-right";
    right.appendChild(dataIcon);
    right.appendChild(overflow);

    block.appendChild(surface);
    block.appendChild(right);
    li.appendChild(block);
    list.appendChild(li);
  }

  renderComponentPalette();
}

async function updateComponentRoleInCurrentComposition(componentId, roleValue) {
  if (!currentBuilderComposition || !currentBuilderComposition.composition_id) {
    showJson("builderOut", {
      status: 0,
      data: { ok: false, error: "no_composition_selected" },
    });
    return;
  }

  const compositionId = String(currentBuilderComposition.composition_id);
  const url =
    "/api/builder/compositions/" +
    encodeURIComponent(compositionId) +
    "/components/" +
    encodeURIComponent(String(componentId || ""));

  showLoading("builderOut");
  try {
    const result = await callApi(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: { role: String(roleValue || "").trim() },
    });
    showJson("builderOut", result);
    if (result && result.data && result.data.ok && result.data.composition) {
      renderBuilderPanel(result.data.composition);
    }
  } catch (error) {
    showJson("builderOut", {
      status: 0,
      data: { ok: false, error: String(error.message || error) },
    });
  }
}

function openBuilderModalForComposition(composition) {
  const modal = document.getElementById("resolveModal");
  const modalTitle = document.getElementById("resolveModalTitle");
  const statusLine = document.getElementById("resolveStatusLine");
  if (!modal || !composition) {
    return;
  }
  if (modalTitle) {
    modalTitle.textContent = "Edit dish: " + String(composition.composition_name || "");
  }
  if (statusLine) {
    statusLine.textContent = "Adjust what should be included in this dish.";
    statusLine.classList.remove("hidden");
  }
  closeRecipeModal();
  renderBuilderPanel(composition);
  modal.classList.remove("hidden");
  loadReusableComponents("").catch((error) => {
    showJson("builderOut", {
      status: 0,
      data: { ok: false, error: String(error.message || error) },
    });
  });
}

function closeResolveModal() {
  const modal = document.getElementById("resolveModal");
  if (modal) {
    modal.classList.add("hidden");
  }
  currentBuilderComposition = null;
  closeRecipeModal();
}

async function removeComponentFromCurrentComposition(componentId) {
  if (!currentBuilderComposition || !currentBuilderComposition.composition_id) {
    showJson("builderOut", {
      status: 0,
      data: { ok: false, error: "no_composition_selected" },
    });
    return;
  }

  const compositionId = String(currentBuilderComposition.composition_id);
  const url =
    "/api/builder/compositions/" +
    encodeURIComponent(compositionId) +
    "/components/" +
    encodeURIComponent(String(componentId || ""));

  showLoading("builderOut");
  try {
    const result = await callApi(url, { method: "DELETE" });
    showJson("builderOut", result);
    if (result && result.data && result.data.ok && result.data.composition) {
      renderBuilderPanel(result.data.composition);
    }
  } catch (error) {
    showJson("builderOut", {
      status: 0,
      data: { ok: false, error: String(error.message || error) },
    });
  }
}

async function attachExistingComponentToCurrentComposition(componentId) {
  if (!currentBuilderComposition || !currentBuilderComposition.composition_id) {
    showJson("builderOut", {
      status: 0,
      data: { ok: false, error: "no_composition_selected" },
    });
    return;
  }

  const compositionId = String(currentBuilderComposition.composition_id);
  const roleInput = document.getElementById("newComponentRole");
  const role = roleInput ? String(roleInput.value || "").trim() : "";

  showLoading("builderOut");
  try {
    const result = await callApi(
      "/api/builder/compositions/" +
        encodeURIComponent(compositionId) +
        "/components/attach",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: {
          component_id: String(componentId || ""),
          role,
        },
      },
    );
    showJson("builderOut", result);
    if (result && result.data && result.data.ok && result.data.composition) {
      renderBuilderPanel(result.data.composition);
    }
  } catch (error) {
    showJson("builderOut", {
      status: 0,
      data: { ok: false, error: String(error.message || error) },
    });
  }
}

async function renameComponentInCurrentComposition(componentId, currentName) {
  if (!currentBuilderComposition || !currentBuilderComposition.composition_id) {
    showJson("builderOut", {
      status: 0,
      data: { ok: false, error: "no_composition_selected" },
    });
    return;
  }

  const newName = String(window.prompt("New component name", String(currentName || "")) || "").trim();
  if (!newName) {
    showJson("builderOut", {
      status: 0,
      data: { ok: false, error: "component_name is required" },
    });
    return;
  }

  const compositionId = String(currentBuilderComposition.composition_id);
  const url =
    "/api/builder/compositions/" +
    encodeURIComponent(compositionId) +
    "/components/" +
    encodeURIComponent(String(componentId || ""));

  showLoading("builderOut");
  try {
    const result = await callApi(url, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: { component_name: newName },
    });
    showJson("builderOut", result);
    if (result && result.data && result.data.ok && result.data.composition) {
      renderBuilderPanel(result.data.composition);
    }
  } catch (error) {
    showJson("builderOut", {
      status: 0,
      data: { ok: false, error: String(error.message || error) },
    });
  }
}

function bindBuilderHandlers() {
  const createDishBtn = document.getElementById("btnCreateDish");
  const createComponentBtn = document.getElementById("btnCreateComponent");
  const importLibraryBtn = document.getElementById("btnImportLibrary");
  const resolveCancelBtn = document.getElementById("resolveCancel");
  const addComponentBtn = document.getElementById("btnAddComponent");
  const paletteSearchInput = document.getElementById("builderPaletteSearch");
  const newComponentInput = document.getElementById("newComponentName");
  const importFilePreviewBtn = document.getElementById("btnImportFilePreview");
  const importFileConfirmBtn = document.getElementById("btnImportFileConfirm");
  const newComponentRoleInput = document.getElementById("newComponentRole");
  const importFileSelectAllBtn = document.getElementById("btnImportPreviewSelectAll");
  const importFileSelectNoneBtn = document.getElementById("btnImportPreviewSelectNone");
  const importFileShowMoreBtn = document.getElementById("btnImportPreviewShowMore");
  const importFileToggleIgnoredBtn = document.getElementById("btnImportPreviewToggleIgnored");
  const importFilePreviewList = document.getElementById("importFilePreviewList");
  const recipeModalCloseBtn = document.getElementById("componentDetailModalClose");
  const recipeCreateBtn = document.getElementById("btnRecipeCreate");
  const recipeSetPrimaryBtn = document.getElementById("btnRecipeSetPrimary");
  const recipeAddIngredientBtn = document.getElementById("btnRecipeIngredientAdd");
  const recipeSaveMetadataBtn = document.getElementById("btnRecipeSaveMetadata");
  const recipeDeleteBtn = document.getElementById("btnRecipeDelete");

  if (createDishBtn) {
    createDishBtn.addEventListener("click", async () => {
      const freeDishNameEl = document.getElementById("freeDishName");
      const composition_name = freeDishNameEl ? String(freeDishNameEl.value || "").trim() : "";
      if (!composition_name) {
        showJson("createDishOut", { status: 0, data: { ok: false, error: "dish name is required" } });
        return;
      }

      showLoading("createDishOut");
      try {
        const result = await callApi("/api/builder/compositions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: { composition_name },
        });
        showJson("createDishOut", result);
        if (result && result.data && result.data.ok && result.data.composition) {
          openBuilderModalForComposition(result.data.composition);
          if (freeDishNameEl) {
            freeDishNameEl.value = "";
          }
          await loadLibrary();
        }
      } catch (error) {
        showJson("createDishOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });
  }

  if (createComponentBtn) {
    createComponentBtn.addEventListener("click", async () => {
      const freeComponentNameEl = document.getElementById("freeComponentName");
      const component_name = freeComponentNameEl ? String(freeComponentNameEl.value || "").trim() : "";
      if (!component_name) {
        showJson("createComponentOut", { status: 0, data: { ok: false, error: "component name is required" } });
        return;
      }

      showLoading("createComponentOut");
      try {
        const result = await callApi("/api/builder/components", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: { component_name },
        });
        showJson("createComponentOut", result);
        if (result && result.data && result.data.ok) {
          if (freeComponentNameEl) {
            freeComponentNameEl.value = "";
          }
          await loadLibrary();
        }
      } catch (error) {
        showJson("createComponentOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });
  }

  if (importLibraryBtn) {
    importLibraryBtn.addEventListener("click", async () => {
      const importLinesEl = document.getElementById("importLibraryLines");
      const importSummaryView = document.getElementById("importSummaryView");
      showLoading("importOut");
      if (importSummaryView) {
        importSummaryView.textContent = "Loading import summary...";
      }

      try {
        const linesInput = importLinesEl ? String(importLinesEl.value || "") : "";
        const result = await callApi("/api/builder/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: { lines: parseLibraryLines(linesInput) },
        });
        renderImportSummary(result);
        showJson("importOut", result);
        await loadLibrary();
      } catch (error) {
        const failResult = { status: 0, data: { ok: false, error: String(error.message || error) } };
        renderImportSummary(failResult);
        showJson("importOut", failResult);
      }
    });
  }

  if (importFilePreviewBtn) {
    importFilePreviewBtn.addEventListener("click", async () => {
      const fileInput = document.getElementById("importLibraryFile");
      const csvColumnInput = document.getElementById("importCsvColumn");
      const file = fileInput && fileInput.files && fileInput.files[0] ? fileInput.files[0] : null;
      if (!file) {
        setFileImportStatus("Choose a .txt, .csv, or .xlsx file first", true);
        return;
      }

      setFileImportStatus("Loading file preview...", false);
      showLoading("importOut");

      const formData = new FormData();
      formData.append("file", file);
      const csvColumn = csvColumnInput ? String(csvColumnInput.value || "").trim() : "";
      if (csvColumn) {
        formData.append("csv_column", csvColumn);
      }

      try {
        const result = await callApi("/api/builder/import/file/preview", {
          method: "POST",
          formData,
        });
        renderFileImportPreview(result);
        showJson("importOut", result);
      } catch (error) {
        const fail = { status: 0, data: { ok: false, error: String(error.message || error) } };
        renderFileImportPreview(fail);
        showJson("importOut", fail);
      }
    });
  }

  if (importFileConfirmBtn) {
    importFileConfirmBtn.addEventListener("click", async () => {
      const selectedLines = selectedFileImportLines();
      if (selectedLines.length === 0) {
        setFileImportStatus("No preview lines available. Run preview first.", true);
        return;
      }

      showLoading("importOut");
      setFileImportStatus("Importing previewed lines...", false);
      try {
        const result = await callApi("/api/builder/import/file/confirm", {
          method: "POST",
          body: {
            lines: selectedLines,
            ignored_noise_count: pendingFileIgnoredItems.length,
          },
        });
        renderImportSummary(result);
        showJson("importOut", result);
        if (result && result.status < 400) {
          pendingFileImportItems = [];
          pendingFileIgnoredItems = [];
          importPreviewVisibleCount = 0;
          importIgnoredExpanded = false;
          refreshFilePreviewLists();
          importFileConfirmBtn.disabled = true;
          setFileImportStatus("File import completed.", false);
        } else {
          setFileImportStatus("File import failed", true);
        }
        await loadLibrary();
      } catch (error) {
        const failResult = { status: 0, data: { ok: false, error: String(error.message || error) } };
        renderImportSummary(failResult);
        showJson("importOut", failResult);
        setFileImportStatus("File import failed", true);
      }
    });
  }

  if (importFilePreviewList) {
    importFilePreviewList.addEventListener("change", (event) => {
      const target = event && event.target;
      if (!target || target.tagName !== "INPUT") {
        return;
      }
      const previewId = String(target.dataset.previewId || "");
      const checked = Boolean(target.checked);
      for (const item of pendingFileImportItems) {
        if (String(item.previewId) === previewId) {
          item.selected = checked;
          break;
        }
      }
      updateFileImportControls();
    });
  }

  if (importFileSelectAllBtn) {
    importFileSelectAllBtn.addEventListener("click", () => {
      toggleAllImportableLines(true);
    });
  }

  if (importFileSelectNoneBtn) {
    importFileSelectNoneBtn.addEventListener("click", () => {
      toggleAllImportableLines(false);
    });
  }

  if (importFileShowMoreBtn) {
    importFileShowMoreBtn.addEventListener("click", () => {
      const total = pendingFileImportItems.length;
      importPreviewVisibleCount = Math.min(total, importPreviewVisibleCount + IMPORT_PREVIEW_CHUNK_SIZE);
      refreshFilePreviewLists();
    });
  }

  if (importFileToggleIgnoredBtn) {
    importFileToggleIgnoredBtn.addEventListener("click", () => {
      importIgnoredExpanded = !importIgnoredExpanded;
      refreshFilePreviewLists();
    });
  }

  if (resolveCancelBtn) {
    resolveCancelBtn.addEventListener("click", () => {
      closeResolveModal();
    });
  }

  if (recipeModalCloseBtn) {
    recipeModalCloseBtn.addEventListener("click", () => {
      closeRecipeModal();
    });
  }

  if (newComponentInput) {
    newComponentInput.addEventListener("input", async () => {
      try {
        await loadReusableComponents(String(newComponentInput.value || "").trim());
      } catch (error) {
        showJson("builderOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });
  }

  if (paletteSearchInput) {
    paletteSearchInput.addEventListener("input", () => {
      renderComponentPalette();
    });
  }

  if (addComponentBtn) {
    addComponentBtn.addEventListener("click", async () => {
      if (!currentBuilderComposition || !currentBuilderComposition.composition_id) {
        showJson("builderOut", { status: 0, data: { ok: false, error: "no_composition_selected" } });
        return;
      }

      const newComponentNameEl = document.getElementById("newComponentName");
      const component_name = newComponentNameEl ? String(newComponentNameEl.value || "").trim() : "";
      const role = newComponentRoleInput ? String(newComponentRoleInput.value || "").trim() : "";
      if (!component_name) {
        showJson("builderOut", { status: 0, data: { ok: false, error: "component_name is required" } });
        return;
      }

      showLoading("builderOut");
      try {
        const result = await callApi(
          "/api/builder/compositions/" + encodeURIComponent(String(currentBuilderComposition.composition_id)) + "/components",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: { component_name, role },
          },
        );
        showJson("builderOut", result);
        if (result && result.data && result.data.ok && result.data.composition) {
          renderBuilderPanel(result.data.composition);
          if (newComponentNameEl) {
            newComponentNameEl.value = "";
          }
          if (newComponentRoleInput) {
            newComponentRoleInput.value = "";
          }
        }
      } catch (error) {
        showJson("builderOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });
  }

  if (recipeCreateBtn) {
    recipeCreateBtn.addEventListener("click", async () => {
      if (!currentRecipeComponent || !currentRecipeComponent.component_id) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: "no_component_selected" } });
        return;
      }

      const recipeNameEl = document.getElementById("recipeCreateName");
      const yieldEl = document.getElementById("recipeCreateYieldPortions");
      const visibilityEl = document.getElementById("recipeCreateVisibility");
      const notesEl = document.getElementById("recipeCreateNotes");
      const recipeName = recipeNameEl ? String(recipeNameEl.value || "").trim() : "";
      const yieldPortions = yieldEl ? String(yieldEl.value || "").trim() : "";
      const visibility = visibilityEl ? String(visibilityEl.value || "").trim() : "private";
      const notes = notesEl ? String(notesEl.value || "").trim() : "";

      if (!recipeName) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: "recipe_name is required" } });
        return;
      }
      if (!yieldPortions) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: "yield_portions is required" } });
        return;
      }

      showLoading("recipeOut");
      try {
        const result = await callApi(
          "/api/builder/components/" + encodeURIComponent(String(currentRecipeComponent.component_id)) + "/recipes",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: {
              recipe_name: recipeName,
              yield_portions: Number(yieldPortions),
              visibility,
              notes,
            },
          },
        );
        showJson("recipeOut", result);
        if (result && result.data && result.data.ok) {
          await loadRecipesForComponent(
            String(currentRecipeComponent.component_id),
            String(currentRecipeComponent.component_name || ""),
          );
          const createdRecipeId = (result.data.recipe || {}).recipe_id;
          if (createdRecipeId) {
            await loadRecipeDetail(String(createdRecipeId));
          }
          if (recipeNameEl) {
            recipeNameEl.value = "";
          }
          if (yieldEl) {
            yieldEl.value = "";
          }
          if (notesEl) {
            notesEl.value = "";
          }
        }
      } catch (error) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });
  }

  if (recipeSetPrimaryBtn) {
    recipeSetPrimaryBtn.addEventListener("click", async () => {
      if (!currentRecipeComponent || !currentRecipeComponent.component_id || !currentSelectedRecipeId) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: "no_recipe_selected" } });
        return;
      }

      showLoading("recipeOut");
      try {
        const result = await callApi(
          "/api/builder/components/" + encodeURIComponent(String(currentRecipeComponent.component_id)) + "/recipes/primary",
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: { recipe_id: String(currentSelectedRecipeId) },
          },
        );
        showJson("recipeOut", result);
        if (result && result.data && result.data.ok) {
          await loadRecipesForComponent(
            String(currentRecipeComponent.component_id),
            String(currentRecipeComponent.component_name || ""),
          );
          await loadRecipeDetail(String(currentSelectedRecipeId));
        }
      } catch (error) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });
  }

  if (recipeSaveMetadataBtn) {
    recipeSaveMetadataBtn.addEventListener("click", async () => {
      if (!currentRecipeComponent || !currentRecipeComponent.component_id || !currentSelectedRecipeId) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: "no_recipe_selected" } });
        return;
      }

      const editName = document.getElementById("recipeEditName");
      const editYield = document.getElementById("recipeEditYieldPortions");
      const editVisibility = document.getElementById("recipeEditVisibility");
      const editNotes = document.getElementById("recipeEditNotes");
      const recipeName = editName ? String(editName.value || "").trim() : "";
      const yieldRaw = editYield ? String(editYield.value || "").trim() : "";
      const visibility = editVisibility ? String(editVisibility.value || "").trim() : "";
      const notes = editNotes ? String(editNotes.value || "").trim() : "";

      if (!recipeName || !yieldRaw) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: "recipe_name and yield_portions are required" } });
        return;
      }

      showLoading("recipeOut");
      try {
        const result = await callApi(
          "/api/builder/components/" +
            encodeURIComponent(String(currentRecipeComponent.component_id)) +
            "/recipes/" +
            encodeURIComponent(String(currentSelectedRecipeId)),
          {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: {
              recipe_name: recipeName,
              yield_portions: Number(yieldRaw),
              visibility,
              notes,
            },
          },
        );
        showJson("recipeOut", result);
        if (result && result.data && result.data.ok) {
          await loadRecipesForComponent(
            String(currentRecipeComponent.component_id),
            String(currentRecipeComponent.component_name || ""),
          );
          await loadRecipeDetail(String(currentSelectedRecipeId));
        }
      } catch (error) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });
  }

  if (recipeDeleteBtn) {
    recipeDeleteBtn.addEventListener("click", async () => {
      if (!currentRecipeComponent || !currentRecipeComponent.component_id || !currentSelectedRecipeId) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: "no_recipe_selected" } });
        return;
      }
      const confirmed = window.confirm("Delete selected recipe?");
      if (!confirmed) {
        return;
      }

      showLoading("recipeOut");
      try {
        const result = await callApi(
          "/api/builder/components/" +
            encodeURIComponent(String(currentRecipeComponent.component_id)) +
            "/recipes/" +
            encodeURIComponent(String(currentSelectedRecipeId)),
          { method: "DELETE" },
        );
        showJson("recipeOut", result);
        if (result && result.data && result.data.ok) {
          currentSelectedRecipeId = null;
          await loadRecipesForComponent(
            String(currentRecipeComponent.component_id),
            String(currentRecipeComponent.component_name || ""),
          );
        }
      } catch (error) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });
  }

  if (recipeAddIngredientBtn) {
    recipeAddIngredientBtn.addEventListener("click", async () => {
      if (!currentRecipeComponent || !currentRecipeComponent.component_id || !currentSelectedRecipeId) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: "no_recipe_selected" } });
        return;
      }

      const nameEl = document.getElementById("recipeIngredientName");
      const amountValueEl = document.getElementById("recipeIngredientAmountValue");
      const amountUnitEl = document.getElementById("recipeIngredientAmountUnit");
      const noteEl = document.getElementById("recipeIngredientNote");

      const ingredientName = nameEl ? String(nameEl.value || "").trim() : "";
      const amountValue = amountValueEl ? String(amountValueEl.value || "").trim() : "";
      const amountUnit = amountUnitEl ? String(amountUnitEl.value || "").trim() : "";
      const note = noteEl ? String(noteEl.value || "").trim() : "";

      if (!ingredientName || !amountValue || !amountUnit) {
        showJson("recipeOut", {
          status: 0,
          data: {
            ok: false,
            error: "ingredient_name, amount_value and amount_unit are required",
          },
        });
        return;
      }

      showLoading("recipeOut");
      try {
        const result = await callApi(
          "/api/builder/components/" +
            encodeURIComponent(String(currentRecipeComponent.component_id)) +
            "/recipes/" +
            encodeURIComponent(String(currentSelectedRecipeId)) +
            "/ingredients",
          {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: {
              ingredient_name: ingredientName,
              amount_value: Number(amountValue),
              amount_unit: amountUnit,
              note,
            },
          },
        );
        showJson("recipeOut", result);
        if (result && result.data && result.data.ok) {
          await loadRecipeDetail(String(currentSelectedRecipeId));
          if (nameEl) {
            nameEl.value = "";
          }
          if (amountValueEl) {
            amountValueEl.value = "";
          }
          if (amountUnitEl) {
            amountUnitEl.value = "";
          }
          if (noteEl) {
            noteEl.value = "";
          }
        }
      } catch (error) {
        showJson("recipeOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
      }
    });
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  bindBuilderHandlers();
  try {
    await loadLibrary();
  } catch (error) {
    showJson("libraryOut", {
      status: 0,
      data: { ok: false, error: String(error.message || error) },
    });
  }
});
