function showJson(targetId, value) {
  const el = document.getElementById(targetId);
  if (!el) {
    return;
  }
  if (isBuilderWorkspaceV1()) {
    el.textContent = formatWorkspaceMessage(targetId, value);
    return;
  }
  el.textContent = JSON.stringify(value, null, 2);
}

function showLoading(targetId) {
  const el = document.getElementById(targetId);
  if (!el) {
    return;
  }
  if (isBuilderWorkspaceV1()) {
    el.textContent = loadingMessageForTarget(targetId);
    return;
  }
  el.textContent = "Loading...";
}

function isBuilderWorkspaceV1() {
  const body = document.body;
  return Boolean(body && body.classList.contains("builder-workspace-v1"));
}

function loadingMessageForTarget(targetId) {
  const id = String(targetId || "");
  if (id === "createDishOut" || id === "createComponentOut") {
    return "Saving...";
  }
  if (id === "builderOut" || id === "recipeOut") {
    return "Saving changes...";
  }
  return "Loading...";
}

function formatWorkspaceMessage(targetId, value) {
  const id = String(targetId || "");
  const payload = (value && value.data) || {};
  const ok = Boolean(payload && payload.ok);

  if (id === "createDishOut") {
    return ok ? "Dish created." : "Could not create dish.";
  }
  if (id === "createComponentOut") {
    return ok ? "Component created." : "Could not create component.";
  }
  if (id === "builderOut") {
    return ok ? "Saved." : "Could not save changes.";
  }
  if (id === "recipeOut") {
    return ok ? "Saved." : "Could not save changes.";
  }
  if (id === "libraryOut") {
    return ok ? "Updated." : "Could not refresh library.";
  }
  return ok ? "Saved." : "Could not save changes.";
}

async function callApi(url, options) {
  const method = String(options.method || "GET").toUpperCase();
  let requestUrl = String(url || "");
  if (method === "GET") {
    const cacheBust = "_ts=" + String(Date.now());
    requestUrl += requestUrl.includes("?") ? "&" + cacheBust : "?" + cacheBust;
  }

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

  const response = await fetch(requestUrl, {
    method,
    headers,
    body,
    cache: method === "GET" ? "no-store" : "default",
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

const IMPORT_TYPE_MENU = "menu";
const IMPORT_TYPE_DISH_LIST = "dish_list";
const IMPORT_TYPE_COMPONENT_LIST = "component_list";
const IMPORT_TYPE_RECIPE_TEXT = "recipe_text";
const IMPORT_RESULT_ROW_LIMIT = 60;
const COMPONENT_RENDER_LIMIT = 80;

let _lastImportSession = null;
let _cachedLibraryComponents = [];
let _cachedLibraryCompositions = [];
let _recentComponentIds = [];

function selectedImportType() {
  const el = document.getElementById("importContextType");
  const value = el ? String(el.value || "") : "";
  return value || IMPORT_TYPE_MENU;
}

function normalizeImportText(value) {
  return String(value || "").trim().toLowerCase();
}

function isWeekHeader(text) {
  const value = normalizeImportText(text);
  return /^week\s*\d+/.test(value) || /^vecka\s*\d+/.test(value) || /^v\s*\d+/.test(value);
}

function isDayHeader(text) {
  const value = normalizeImportText(text);
  return /^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b/.test(value)
    || /^(monday|tuesday|wednesday|thursday|friday)\s+.+/.test(value)
    || /^(mon|tue|wed|thu|fri|sat|sun)\b/.test(value)
    || /^(man|mon|tis|tisdag|ons|onsdag|tors|torsdag|fre|fredag|lor|lordag|son|sondag)\b/.test(value)
    || /^(day)\s*\d+/.test(value);
}

function parseMenuImportStructure(lines) {
  const source = Array.isArray(lines) ? lines : [];
  const grouped = [];
  let currentWeek = "Week 1";
  let currentSection = "Day 1";
  let seenAnySection = false;
  let weekCounter = 1;

  function ensureGroup(weekLabel) {
    const label = String(weekLabel || "").trim() || "Week " + String(weekCounter);
    let group = grouped.find((item) => normalizeImportText(item.week_label) === normalizeImportText(label));
    if (!group) {
      group = { week_label: label, items: [] };
      grouped.push(group);
    }
    return group;
  }

  for (const raw of source) {
    const line = String(raw || "").trim();
    if (!line) {
      continue;
    }

    if (isWeekHeader(line)) {
      currentWeek = line;
      weekCounter += 1;
      currentSection = "Day 1";
      seenAnySection = false;
      ensureGroup(currentWeek);
      continue;
    }

    if (isDayHeader(line)) {
      currentSection = line;
      seenAnySection = true;
      ensureGroup(currentWeek);
      continue;
    }

    const group = ensureGroup(currentWeek);
    if (!seenAnySection && group.items.length === 0) {
      currentSection = "Day 1";
    }
    group.items.push({
      raw_text: line,
      section_label: currentSection,
    });
  }

  return grouped.filter((group) => Array.isArray(group.items) && group.items.length > 0);
}

function buildDishLinesFromGroupedMenu(groupedMenu) {
  const lines = [];
  for (const group of groupedMenu || []) {
    for (const item of group.items || []) {
      const rawText = String(item.raw_text || "").trim();
      if (rawText) {
        lines.push(rawText);
      }
    }
  }
  return lines;
}

function normalizeRecentImportGroups(groups) {
  const normalized = [];
  for (const group of groups || []) {
    const label = String(group.week_label || group.group_label || "Imported items").trim() || "Imported items";
    const items = Array.isArray(group.items) ? group.items : [];
    normalized.push({ week_label: label, items });
  }
  return normalized;
}

function renderRecentImportGroups() {
  const host = document.getElementById("recentImportGroups");
  if (!host) {
    return;
  }
  host.innerHTML = "";

  const session = _lastImportSession;
  if (!session || !Array.isArray(session.groups) || session.groups.length === 0) {
    return;
  }

  const title = document.createElement("div");
  title.className = "import-grouped-block";
  const titleText = document.createElement("p");
  titleText.className = "import-grouped-block-title";
  titleText.textContent = "Recent import: " + String(session.import_type_label || "Import");
  title.appendChild(titleText);
  if (session.note) {
    const note = document.createElement("p");
    note.className = "import-grouped-block-meta";
    note.textContent = String(session.note);
    title.appendChild(note);
  }
  host.appendChild(title);

  for (const group of session.groups) {
    const card = document.createElement("div");
    card.className = "import-grouped-block";

    const heading = document.createElement("p");
    heading.className = "import-grouped-block-title";
    heading.textContent = String(group.week_label || "Group");
    card.appendChild(heading);

    const meta = document.createElement("p");
    meta.className = "import-grouped-block-meta";
    meta.textContent = String((group.items || []).length) + " items";
    card.appendChild(meta);

    const sample = (group.items || []).slice(0, 4);
    if (sample.length > 0) {
      const list = document.createElement("ul");
      list.className = "import-grouped-list";
      for (const item of sample) {
        const li = document.createElement("li");
        li.textContent = String(item.raw_text || item.label || "");
        list.appendChild(li);
      }
      if ((group.items || []).length > sample.length) {
        const li = document.createElement("li");
        li.textContent = "...";
        list.appendChild(li);
      }
      card.appendChild(list);
    }

    host.appendChild(card);
  }
}

function renderImportSummary(result) {
  const host = document.getElementById("importSummaryView");
  const reviewNotice = document.getElementById("importReviewNotice");
  if (!host) {
    return;
  }

  host.innerHTML = "";
  renderRecentImportGroups();
  if (reviewNotice) {
    reviewNotice.classList.add("hidden");
    reviewNotice.textContent = "";
  }

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

  const reviewItems = Array.isArray(summary.component_review_items) ? summary.component_review_items : [];
  if (reviewItems.length > 0) {
    if (reviewNotice) {
      reviewNotice.textContent =
        String(reviewItems.length) +
        (reviewItems.length === 1
          ? " possible component match needs review."
          : " possible component matches need review.");
      reviewNotice.classList.remove("hidden");
    }

    const reviewBlock = document.createElement("div");
    reviewBlock.className = "import-review-block";

    const reviewTitle = document.createElement("p");
    reviewTitle.className = "import-review-title";
    reviewTitle.textContent = "Review-needed component matches";
    reviewBlock.appendChild(reviewTitle);

    const reviewList = document.createElement("div");
    reviewList.className = "import-review-list";

    for (const item of reviewItems) {
      const row = document.createElement("div");
      row.className = "import-review-item";

      const suggestedName = String(item.suggested_component_name || item.raw_text || "");
      const status = String(item.status || "possible_match");
      const statusLabel = document.createElement("span");
      statusLabel.className = "import-review-status";
      statusLabel.textContent = status.replace(/_/g, " ");

      const primary = document.createElement("p");
      primary.className = "import-review-primary";
      primary.textContent = "Imported component: " + suggestedName;

      const possibleMatches = Array.isArray(item.possible_matches) ? item.possible_matches : [];
      const candidate = possibleMatches.length > 0 ? possibleMatches[0] : null;
      const existingName = candidate ? String(candidate.component_name || "") : "No candidate";
      const scoreValue = candidate && typeof candidate.score === "number"
        ? candidate.score.toFixed(2)
        : "-";

      const secondary = document.createElement("p");
      secondary.className = "import-review-secondary";
      secondary.textContent =
        "Possible existing match: " + existingName +
        " | Score: " + scoreValue +
        " | Status: " + status.replace(/_/g, " ");

      row.appendChild(statusLabel);
      row.appendChild(primary);
      row.appendChild(secondary);
      reviewList.appendChild(row);
    }

    reviewBlock.appendChild(reviewList);
    host.appendChild(reviewBlock);
  }

  const rows = Array.isArray(summary.row_results) ? summary.row_results : [];
  const visibleRows = rows.slice(0, IMPORT_RESULT_ROW_LIMIT);
  if (rows.length > visibleRows.length) {
    const clipped = document.createElement("div");
    clipped.className = "workspace-library-hint";
    clipped.textContent =
      "Showing first " + String(visibleRows.length) + " of " + String(rows.length) + " imported rows.";
    host.appendChild(clipped);
  }

  for (const row of visibleRows) {
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
let pendingImportSource = "";

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
  status.className = isError ? "workspace-import-status import-warning-block" : "workspace-import-status";
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

async function previewPastedImportLines() {
  const importLinesEl = document.getElementById("importLibraryLines");
  const linesInput = importLinesEl ? String(importLinesEl.value || "") : "";
  const lines = parseLibraryLines(linesInput);
  if (lines.length === 0) {
    setFileImportStatus("Paste lines before preview.", true);
    return;
  }

  setFileImportStatus("Building pasted import preview...", false);
  showLoading("importOut");
  try {
    const result = await callApi("/api/builder/import/preview-lines", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: { lines },
    });
    pendingImportSource = "pasted";
    renderFileImportPreview(result);
    showJson("importOut", result);
  } catch (error) {
    pendingImportSource = "";
    const fail = { status: 0, data: { ok: false, error: String(error.message || error) } };
    renderFileImportPreview(fail);
    showJson("importOut", fail);
  }
}

async function loadAllCompositions() {
  return callApi("/api/builder/compositions", { method: "GET" });
}

function currentComponentScope() {
  const scopeEl = document.getElementById("libraryComponentsScope");
  const value = scopeEl ? String(scopeEl.value || "") : "";
  return value === "all" ? "all" : "recent";
}

function applyComponentLibraryFilter(query) {
  const grid = document.getElementById("libraryComponentsGrid");
  const componentsMeta = document.getElementById("workspaceComponentsMeta");
  if (!grid) {
    return;
  }

  const q = String(query || "").trim().toLowerCase();
  const scope = currentComponentScope();
  let scopedItems = _cachedLibraryComponents;
  if (scope === "recent" && _recentComponentIds.length > 0) {
    const idSet = new Set(_recentComponentIds.map((value) => String(value || "")));
    scopedItems = _cachedLibraryComponents.filter((item) => idSet.has(String(item.component_id || "")));
  }

  const filtered = q
    ? scopedItems.filter((item) =>
        String(item.component_name || item.component_id || "").toLowerCase().includes(q),
      )
    : scopedItems;

  grid.innerHTML = "";

  if (filtered.length === 0 && _cachedLibraryComponents.length > 0) {
    const noMatch = document.createElement("p");
    noMatch.className = "workspace-library-hint";
    noMatch.textContent = q
      ? 'No components match "' + q + '"'
      : (scope === "recent"
        ? "No recent components yet. Switch filter to All."
        : "No components to show.");
    grid.appendChild(noMatch);
    if (componentsMeta) {
      componentsMeta.textContent = "No components in current filter.";
    }
    return;
  }

  const visible = filtered.slice(0, COMPONENT_RENDER_LIMIT);
  renderComponentLibraryCards(visible, grid);

  if (filtered.length > visible.length) {
    const clipped = document.createElement("p");
    clipped.className = "workspace-library-hint";
    clipped.textContent =
      "Showing " + String(visible.length) + " of " + String(filtered.length) +
      " components in this view. Use search to narrow further.";
    grid.appendChild(clipped);
  }

  if (componentsMeta) {
    componentsMeta.textContent =
      String(visible.length) + " shown" +
      (filtered.length > visible.length ? " of " + String(filtered.length) : "") +
      " components (" + (scope === "recent" ? "recent" : "all") + " filter).";
  }
}

function renderComponentLibraryCards(items, targetGrid) {
  if (!targetGrid) {
    return;
  }

  for (const item of items) {
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

    const kicker = document.createElement("span");
    kicker.className = "component-library-card-kicker";
    kicker.textContent = "Component";

    const topRow = document.createElement("div");
    topRow.className = "component-library-card-row";

    const name = document.createElement("div");
    name.className = "component-library-card-name";
    name.textContent = componentName;

    const chip = document.createElement("span");
    chip.className = "component-library-card-status component-library-card-status-chip";
    chip.textContent = hasPrimaryRecipe ? "Recipe ready" : "Needs recipe";
    chip.classList.add(
      hasPrimaryRecipe
        ? "component-library-card-status-has-data"
        : "component-library-card-status-no-data",
    );

    topRow.appendChild(name);
    topRow.appendChild(chip);

    const footer = document.createElement("p");
    footer.className = "component-library-card-footer";
    footer.textContent = "Open details to edit recipes, ingredients, scaling, and declarations.";

    openSurface.appendChild(kicker);
    openSurface.appendChild(topRow);
    openSurface.appendChild(footer);

    card.appendChild(openSurface);
    targetGrid.appendChild(card);
  }
}

function buildLibraryStartEmptyState(targetGrid) {
  const start = document.createElement("section");
  start.className = "workspace-library-start";

  const title = document.createElement("h3");
  title.className = "workspace-library-start-title";
  title.textContent = "Start building your kitchen library";

  const copy = document.createElement("p");
  copy.className = "workspace-library-start-copy";
  copy.textContent = "Create reusable components first. Then combine them into dishes when you are ready.";

  const actions = document.createElement("div");
  actions.className = "workspace-library-start-actions";

  const createAction = document.createElement("button");
  createAction.type = "button";
  createAction.className = "workspace-library-start-action";
  createAction.innerHTML = "<strong>Create component</strong><span>Add your first reusable building block</span>";
  createAction.addEventListener("click", () => {
    openSimpleModal("componentCreateModal");
    const input = document.getElementById("freeComponentName");
    if (input) {
      input.focus();
    }
  });

  const importAction = document.createElement("button");
  importAction.type = "button";
  importAction.className = "workspace-library-start-action";
  importAction.innerHTML = "<strong>Import menu/recipes</strong><span>Bring in existing names to get started quickly</span>";
  importAction.addEventListener("click", () => {
    openSimpleModal("importLibraryModal");
    const importInput = document.getElementById("importLibraryLines");
    if (importInput) {
      importInput.focus();
    }
  });

  const dishesAction = document.createElement("button");
  dishesAction.type = "button";
  dishesAction.className = "workspace-library-start-action";
  dishesAction.innerHTML = "<strong>Open dishes</strong><span>See dishes and start combining components</span>";
  dishesAction.addEventListener("click", () => {
    openSimpleModal("dishesLibraryModal");
  });

  actions.appendChild(createAction);
  actions.appendChild(importAction);
  actions.appendChild(dishesAction);
  start.appendChild(title);
  start.appendChild(copy);
  start.appendChild(actions);
  targetGrid.appendChild(start);
}

function renderLibrary(result) {
  const componentsGrid = document.getElementById("libraryComponentsGrid");
  const compositionsGrid = document.getElementById("libraryCompositionsGrid");
  const componentsMeta = document.getElementById("workspaceComponentsMeta");
  const dishesMeta = document.getElementById("workspaceDishesMeta");
  if (!componentsGrid || !compositionsGrid) {
    return;
  }

  componentsGrid.innerHTML = "";
  compositionsGrid.innerHTML = "";

  const data = (result && result.data) || {};
  const components = Array.isArray(data.components) ? data.components : [];
  const compositions = Array.isArray(data.compositions) ? data.compositions : [];

  _cachedLibraryComponents = components;
  _cachedLibraryCompositions = compositions;

  const searchInput = document.getElementById("libraryComponentsSearch");
  const currentQuery = searchInput ? String(searchInput.value || "") : "";

  if (componentsMeta && components.length === 0) {
    componentsMeta.textContent = "No components yet. Start by creating one or importing existing names.";
  }

  if (dishesMeta) {
    dishesMeta.textContent =
      compositions.length === 0
        ? "No dishes yet. Create one or import to start building."
        : String(compositions.length) + (compositions.length === 1 ? " dish" : " dishes") + " in library";
  }

  if (components.length === 0) {
    buildLibraryStartEmptyState(componentsGrid);
  } else {
    applyComponentLibraryFilter(currentQuery);
  }

  if (compositions.length === 0) {
    const empty = document.createElement("div");
    empty.className = "library-empty workspace-library-empty";

    const title = document.createElement("p");
    title.className = "workspace-library-empty-title";
    title.textContent = "No dishes yet";

    const copy = document.createElement("p");
    copy.className = "workspace-library-empty-copy";
    copy.textContent = "Create a dish manually, or import dish lines and continue editing from the library.";

    const actions = document.createElement("div");
    actions.className = "workspace-inline-actions";

    const createBtn = document.createElement("button");
    createBtn.type = "button";
    createBtn.textContent = "Create dish";
    createBtn.addEventListener("click", () => {
      openSimpleModal("quickCreateModal");
      const input = document.getElementById("freeDishName");
      if (input) {
        input.focus();
      }
    });

    const importBtn = document.createElement("button");
    importBtn.type = "button";
    importBtn.textContent = "Import";
    importBtn.addEventListener("click", () => {
      openSimpleModal("importLibraryModal");
      const importInput = document.getElementById("importLibraryLines");
      if (importInput) {
        importInput.focus();
      }
    });

    actions.appendChild(createBtn);
    actions.appendChild(importBtn);
    empty.appendChild(title);
    empty.appendChild(copy);
    empty.appendChild(actions);
    compositionsGrid.appendChild(empty);
  } else {
    const visibleCompositions = compositions.slice(0, COMPONENT_RENDER_LIMIT);
    for (const item of visibleCompositions) {
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

      card.appendChild(openSurface);
      compositionsGrid.appendChild(card);
    }

    if (compositions.length > visibleCompositions.length) {
      const clipped = document.createElement("p");
      clipped.className = "workspace-library-hint";
      clipped.textContent =
        "Showing " + String(visibleCompositions.length) + " of " + String(compositions.length) +
        " dishes. Open Menu Builder for structured menu output.";
      compositionsGrid.appendChild(clipped);
    }
  }
}

function filterLibraryComponents(query) {
  applyComponentLibraryFilter(query);
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
    closeSimpleModal("dishesLibraryModal");
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
let pendingAddedPulseComponentId = null;
let pendingSelectedPulseComponentId = null;
let pendingReorderedPulseComponentId = null;

function stageAddedComponentPulse(componentId) {
  pendingAddedPulseComponentId = String(componentId || "").trim() || null;
}

function stageSelectedComponentPulse(componentId) {
  pendingSelectedPulseComponentId = String(componentId || "").trim() || null;
}

function stageReorderedComponentPulse(componentId) {
  pendingReorderedPulseComponentId = String(componentId || "").trim() || null;
}

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

function setRecipeScalingStatus(message, isError) {
  const status = document.getElementById("recipeScalingStatus");
  if (!status) {
    return;
  }
  status.textContent = String(message || "");
  status.className = isError ? "recipe-scaling-status recipe-scaling-status-error" : "recipe-scaling-status";
}

function resetRecipeScalingPreview(message) {
  const summary = document.getElementById("recipeScalingSummary");
  const list = document.getElementById("recipeScalingRows");
  const target = document.getElementById("recipeScalingTargetPortions");
  const previewBtn = document.getElementById("btnRecipeScalingPreview");

  if (summary) {
    summary.textContent = String(message || "Select a recipe to preview scaling.");
  }
  if (list) {
    list.innerHTML = "";
  }
  if (target) {
    target.value = "";
    target.disabled = true;
  }
  if (previewBtn) {
    previewBtn.disabled = true;
  }
  setRecipeScalingStatus("", false);
}

function renderRecipeScalingPreview(preview) {
  const summary = document.getElementById("recipeScalingSummary");
  const list = document.getElementById("recipeScalingRows");
  if (!summary || !list) {
    return;
  }

  list.innerHTML = "";
  summary.textContent =
    "Yield " +
    String(preview.source_yield_portions) +
    " -> target " +
    String(preview.target_portions) +
    " | factor " +
    String(preview.scaling_factor || "");

  const rows = Array.isArray(preview.ingredient_lines) ? preview.ingredient_lines : [];
  if (rows.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No ingredients to scale";
    list.appendChild(li);
    return;
  }

  for (const row of rows) {
    const li = document.createElement("li");
    const note = row.note ? " (" + String(row.note) + ")" : "";
    li.textContent =
      String(row.ingredient_name || "") +
      ": " +
      String(row.original_amount_value || "") +
      " -> " +
      String(row.scaled_amount_value || "") +
      " " +
      String(row.amount_unit || "") +
      note;
    list.appendChild(li);
  }
}

function setListContent(listId, items, emptyMessage) {
  const list = document.getElementById(listId);
  if (!list) {
    return;
  }
  list.innerHTML = "";
  const values = Array.isArray(items) ? items : [];
  if (values.length === 0) {
    const li = document.createElement("li");
    li.textContent = String(emptyMessage || "None");
    list.appendChild(li);
    return;
  }
  for (const item of values) {
    const li = document.createElement("li");
    li.textContent = String(item || "");
    list.appendChild(li);
  }
}

const CONFLICT_TOKEN_META = {
  lactose_relevant: { icon: "🥛", label: "Milk/Lactose" },
  gluten_relevant: { icon: "🌾", label: "Gluten" },
  fish_relevant: { icon: "🐟", label: "Fish" },
  egg_relevant: { icon: "🥚", label: "Egg" },
  nut_relevant: { icon: "🥜", label: "Nuts" },
};

const SIGNAL_TOKEN_META = {
  milk: { icon: "🥛", label: "Milk" },
  lactose: { icon: "🥛", label: "Lactose" },
  gluten: { icon: "🌾", label: "Gluten" },
  fish: { icon: "🐟", label: "Fish" },
  egg: { icon: "🥚", label: "Egg" },
  nuts: { icon: "🥜", label: "Nuts" },
};

let currentCompositionConflictsByComponentId = {};

function tokenLabelForConflict(conflictKey) {
  const meta = CONFLICT_TOKEN_META[String(conflictKey || "")];
  if (meta) {
    return meta.icon + " " + meta.label;
  }
  return String(conflictKey || "").replace(/_/g, " ");
}

function tokenLabelForSignal(signalKey) {
  const meta = SIGNAL_TOKEN_META[String(signalKey || "")];
  if (meta) {
    return meta.icon + " " + meta.label;
  }
  return String(signalKey || "");
}

function renderTokenList(listId, items, emptyMessage, labelBuilder) {
  const list = document.getElementById(listId);
  if (!list) {
    return;
  }
  list.innerHTML = "";
  const values = Array.isArray(items) ? items : [];
  if (values.length === 0) {
    const li = document.createElement("li");
    li.textContent = String(emptyMessage || "None");
    li.className = "declaration-list-empty";
    list.appendChild(li);
    return;
  }

  for (const item of values) {
    const li = document.createElement("li");
    li.className = "declaration-token-item";
    const token = document.createElement("span");
    token.className = "declaration-token";
    token.textContent = String(labelBuilder ? labelBuilder(item) : item || "");
    li.appendChild(token);
    list.appendChild(li);
  }
}

function renderConflictTokenList(listId, conflictPreview) {
  const preview = conflictPreview || {};
  const conflictsPresent = Array.isArray(preview.conflicts_present)
    ? preview.conflicts_present
    : [];
  const conflictSources = Array.isArray(preview.conflict_sources)
    ? preview.conflict_sources
    : [];

  const sourceMap = {};
  for (const source of conflictSources) {
    const conflictKey = String(source.conflict_key || "");
    const traits = Array.isArray(source.triggering_trait_signals)
      ? source.triggering_trait_signals
      : [];
    const conflictLabel = tokenLabelForConflict(conflictKey);
    const traitLabel = traits.length > 0 ? traits.map((v) => tokenLabelForSignal(v)).join(", ") : "";
    if (!sourceMap[conflictKey]) {
      sourceMap[conflictKey] = [];
    }
    if (traitLabel) {
      sourceMap[conflictKey].push(conflictLabel + " · " + traitLabel);
    }
  }

  const items = [];
  for (const conflict of conflictsPresent) {
    const key = String(conflict || "");
    if (sourceMap[key] && sourceMap[key].length > 0) {
      items.push(sourceMap[key][0]);
    } else {
      items.push(tokenLabelForConflict(key));
    }
  }

  renderTokenList(listId, items, "No potential conflicts", (item) => String(item || ""));
}

function updateComponentConflictBadgesDom() {
  const blocks = document.querySelectorAll(".component-block[data-component-id]");
  for (const block of blocks) {
    const componentId = String(block.getAttribute("data-component-id") || "");
    const count = Number(currentCompositionConflictsByComponentId[componentId] || 0);
    const badge = block.querySelector(".component-conflict-badge");
    if (!badge) {
      continue;
    }
    if (count > 0) {
      badge.classList.remove("hidden");
      badge.textContent = "⚑ " + String(count);
      badge.title = "Potential diet conflicts detected";
    } else {
      badge.classList.add("hidden");
      badge.textContent = "";
      badge.title = "";
    }
  }
}

function renderComponentDeclarationPreview(payload) {
  const enabled = Boolean(payload && payload.declaration_enabled);
  const readiness = enabled ? (payload.readiness || {}) : null;
  const status = document.getElementById("componentDeclarationStatus");
  const disabledNotice = document.getElementById("componentDeclarationDisabled");
  const summary = document.getElementById("componentDeclarationSignalsSummary");

  if (disabledNotice) {
    if (enabled) {
      disabledNotice.classList.add("hidden");
    } else {
      disabledNotice.classList.remove("hidden");
      disabledNotice.textContent = "Declaration preview unavailable right now.";
    }
  }

  if (status) {
    status.textContent = "Read-only preview. No automation applied.";
  }

  const signals = readiness && Array.isArray(readiness.trait_signals_present)
    ? readiness.trait_signals_present
    : [];
  const conflictPreview = readiness && readiness.conflict_preview ? readiness.conflict_preview : {};
  if (summary) {
    summary.textContent = enabled
      ? (signals.length > 0
        ? "Signals present: " + signals.join(", ")
        : "No declaration signals present")
      : "Declaration preview disabled";
  }

  renderTokenList("componentDeclarationSignals", signals, "No signals", (item) => tokenLabelForSignal(item));
  renderConflictTokenList("componentConflictList", conflictPreview);

  const provenanceItems = [];
  const sources = readiness && Array.isArray(readiness.ingredient_sources)
    ? readiness.ingredient_sources
    : [];
  for (const source of sources) {
    provenanceItems.push(
      String(source.ingredient_name || "") +
      " -> " +
      (Array.isArray(source.trait_signals) ? source.trait_signals.join(", ") : "") +
      " (recipe " +
      String(source.recipe_id || "") +
      ")",
    );
  }
  setListContent("componentDeclarationProvenance", provenanceItems, "No ingredient provenance");

  const warnings = readiness && Array.isArray(readiness.warnings) ? readiness.warnings : [];
  setListContent("componentDeclarationWarnings", warnings, "No warnings");
}

function renderCompositionDeclarationPreview(payload) {
  const enabled = Boolean(payload && payload.declaration_enabled);
  const readiness = enabled ? (payload.readiness || {}) : null;
  const status = document.getElementById("compositionDeclarationStatus");
  const disabledNotice = document.getElementById("compositionDeclarationDisabled");
  const summary = document.getElementById("compositionDeclarationSignalsSummary");

  if (disabledNotice) {
    if (enabled) {
      disabledNotice.classList.add("hidden");
    } else {
      disabledNotice.classList.remove("hidden");
      disabledNotice.textContent = "Declaration preview unavailable right now.";
    }
  }

  if (status) {
    status.textContent = "Read-only preview. No automation applied.";
  }

  const signals = readiness && Array.isArray(readiness.trait_signals_present)
    ? readiness.trait_signals_present
    : [];
  const conflictPreview = readiness && readiness.conflict_preview ? readiness.conflict_preview : {};
  currentCompositionConflictsByComponentId = {};
  const components = readiness && Array.isArray(readiness.components) ? readiness.components : [];
  for (const component of components) {
    const componentId = String(component.component_id || "");
    const componentConflicts = component && component.conflict_preview
      ? component.conflict_preview
      : {};
    const componentConflictCount = Array.isArray(componentConflicts.conflicts_present)
      ? componentConflicts.conflicts_present.length
      : 0;
    currentCompositionConflictsByComponentId[componentId] = componentConflictCount;
  }
  if (summary) {
    summary.textContent = enabled
      ? (signals.length > 0
        ? "Signals present: " + signals.join(", ")
        : "No declaration signals present")
      : "Declaration preview disabled";
  }

  renderTokenList("compositionDeclarationSignals", signals, "No signals", (item) => tokenLabelForSignal(item));
  renderConflictTokenList("compositionConflictList", conflictPreview);
  const warnings = readiness && Array.isArray(readiness.warnings) ? readiness.warnings : [];
  setListContent("compositionDeclarationWarnings", warnings, "No warnings");
  updateComponentConflictBadgesDom();
}

async function loadComponentDeclarationPreview(componentId) {
  const componentIdValue = String(componentId || "").trim();
  if (!componentIdValue) {
    renderComponentDeclarationPreview({ declaration_enabled: false, readiness: null });
    return;
  }

  const result = await callApi(
    "/api/builder/components/" + encodeURIComponent(componentIdValue) + "/declaration-readiness",
    { method: "GET" },
  );
  if (!result || result.status >= 400 || !result.data || !result.data.ok) {
    renderComponentDeclarationPreview({ declaration_enabled: false, readiness: null });
    return;
  }
  renderComponentDeclarationPreview(result.data);
}

async function loadCompositionDeclarationPreview(compositionId) {
  const compositionIdValue = String(compositionId || "").trim();
  if (!compositionIdValue) {
    renderCompositionDeclarationPreview({ declaration_enabled: false, readiness: null });
    return;
  }

  const result = await callApi(
    "/api/builder/compositions/" + encodeURIComponent(compositionIdValue) + "/declaration-readiness",
    { method: "GET" },
  );
  if (!result || result.status >= 400 || !result.data || !result.data.ok) {
    renderCompositionDeclarationPreview({ declaration_enabled: false, readiness: null });
    return;
  }
  renderCompositionDeclarationPreview(result.data);
}

async function loadRecipeScalingPreview() {
  if (!currentRecipeComponent || !currentRecipeComponent.component_id || !currentSelectedRecipeId) {
    setRecipeScalingStatus("Select a recipe first", true);
    return;
  }

  const targetInput = document.getElementById("recipeScalingTargetPortions");
  const targetRaw = targetInput ? String(targetInput.value || "").trim() : "";
  const targetValue = Number(targetRaw);
  if (!targetRaw || !Number.isFinite(targetValue) || targetValue <= 0) {
    setRecipeScalingStatus("Target portions must be > 0", true);
    return;
  }

  setRecipeScalingStatus("Loading scaling preview...", false);
  const result = await callApi(
    "/api/builder/components/" +
      encodeURIComponent(String(currentRecipeComponent.component_id)) +
      "/recipes/" +
      encodeURIComponent(String(currentSelectedRecipeId)) +
      "/scaling-preview?target_portions=" +
      encodeURIComponent(String(Math.trunc(targetValue))),
    { method: "GET" },
  );

  if (!result || result.status >= 400 || !result.data || !result.data.ok) {
    const message =
      String((result && result.data && (result.data.message || result.data.error)) || "Unable to load scaling preview");
    setRecipeScalingStatus(message, true);
    return;
  }

  renderRecipeScalingPreview(result.data.preview || {});
  setRecipeScalingStatus("Scaling preview ready", false);
}

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
  stageSelectedComponentPulse(selectedComponentId);
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
  resetRecipeScalingPreview("Select a recipe to preview scaling.");
  setComponentDetailTextPreview("No composition selected");
  renderComponentDeclarationPreview({ declaration_enabled: false, readiness: null });
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

  resetRecipeScalingPreview("Select a recipe to preview scaling.");

  try {
    await loadComponentDeclarationPreview(componentIdValue);
  } catch (_error) {
    renderComponentDeclarationPreview({ declaration_enabled: false, readiness: null });
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

function openSimpleModal(modalId) {
  const modal = document.getElementById(String(modalId || ""));
  if (modal) {
    modal.classList.remove("hidden");
  }
}

function closeSimpleModal(modalId) {
  const modal = document.getElementById(String(modalId || ""));
  if (modal) {
    modal.classList.add("hidden");
  }
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
  const scalingTarget = document.getElementById("recipeScalingTargetPortions");
  const scalingBtn = document.getElementById("btnRecipeScalingPreview");
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
  resetRecipeScalingPreview("Click preview to scale ingredient rows.");
  if (scalingTarget) {
    scalingTarget.disabled = false;
    scalingTarget.value = String(recipe.yield_portions || "");
  }
  if (scalingBtn) {
    scalingBtn.disabled = false;
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
        pill.classList.add("component-palette-pill-pick");
        setTimeout(() => {
          pill.classList.remove("component-palette-pill-pick");
        }, 260);
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

  if (!title || !list || !composition) {
    return;
  }

  currentBuilderComposition = composition;
  resetRecipePanel("Component: not selected");
  title.textContent = "Dish: " + String(composition.composition_name || "");
  list.innerHTML = "";

  loadCompositionDeclarationPreview(String(composition.composition_id || "")).catch(() => {
    renderCompositionDeclarationPreview({ declaration_enabled: false, readiness: null });
  });

  const components = Array.isArray(composition.components) ? composition.components : [];

  if (components.length === 0) {
    selectedComponentId = null;
    const li = document.createElement("li");
    li.className = "component-build-surface-empty";
    li.textContent = "No components yet. Use Add component to start building this dish.";
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
    block.dataset.componentId = componentIdValue;
    block.draggable = true;
    const entryKey = componentEntryKey(component);
    block.dataset.entryKey = entryKey;

    if (selectedComponentId === componentIdValue) {
      block.classList.add("component-block-selected");
    }
    if (pendingAddedPulseComponentId === componentIdValue) {
      block.classList.add("component-block-just-added");
    }
    if (pendingSelectedPulseComponentId === componentIdValue) {
      block.classList.add("component-block-just-selected");
    }
    if (pendingReorderedPulseComponentId === componentIdValue) {
      block.classList.add("component-block-just-reordered");
    }

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
      stageReorderedComponentPulse(componentIdValue);
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
    const conflictBadge = document.createElement("span");
    conflictBadge.className = "component-conflict-badge hidden";
    right.appendChild(conflictBadge);
    right.appendChild(dataIcon);
    right.appendChild(overflow);

    block.appendChild(surface);
    block.appendChild(right);
    li.appendChild(block);
    list.appendChild(li);
  }

  updateComponentConflictBadgesDom();
  renderComponentPalette();
  pendingAddedPulseComponentId = null;
  pendingSelectedPulseComponentId = null;
  pendingReorderedPulseComponentId = null;
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
      const attachedId = String(componentId || "").trim();
      selectedComponentId = attachedId || selectedComponentId;
      stageAddedComponentPulse(attachedId);
      stageSelectedComponentPulse(attachedId);
      closeSimpleModal("addComponentModal");
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

function importTypeLabel(importType) {
  const value = String(importType || "");
  if (value === IMPORT_TYPE_MENU) {
    return "Menu";
  }
  if (value === IMPORT_TYPE_COMPONENT_LIST) {
    return "Component list";
  }
  if (value === IMPORT_TYPE_RECIPE_TEXT) {
    return "Recipe text";
  }
  return "Dish list";
}

function buildCompositionQueueFromSummary(summary) {
  const queue = {};
  const rows = Array.isArray(summary && summary.row_results) ? summary.row_results : [];
  for (const row of rows) {
    const key = normalizeImportText(row.raw_text);
    const compositionId = String(row.composition_id || "").trim();
    if (!key || !compositionId) {
      continue;
    }
    if (!queue[key]) {
      queue[key] = [];
    }
    queue[key].push(compositionId);
  }
  return queue;
}

function nextCompositionIdForRawText(compositionQueue, rawText) {
  const key = normalizeImportText(rawText);
  const entries = compositionQueue[key];
  if (!entries || entries.length === 0) {
    return "";
  }
  return String(entries.shift() || "");
}

function generateImportWeekKey(index) {
  const now = new Date();
  const y = String(now.getFullYear());
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return "IMPORT-" + y + m + d + "-" + String(index + 1).padStart(2, "0");
}

async function createStructuredMenusFromImport(groupedMenu, summary) {
  const groups = normalizeRecentImportGroups(groupedMenu);
  if (groups.length === 0) {
    return { created_menus: 0, created_rows: 0, failed_rows: 0, groups: [] };
  }

  const compositionQueue = buildCompositionQueueFromSummary(summary);
  let createdMenus = 0;
  let createdRows = 0;
  let failedRows = 0;
  const sessionGroups = [];

  for (let groupIndex = 0; groupIndex < groups.length; groupIndex += 1) {
    const group = groups[groupIndex];
    const menuTitle = String(group.week_label || "Imported menu " + String(groupIndex + 1));

    const menuResult = await callApi("/api/builder/menus", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        title: menuTitle,
        site_id: "site_1",
        week_key: generateImportWeekKey(groupIndex),
      },
    });

    if (!menuResult || !menuResult.data || !menuResult.data.ok || !menuResult.data.menu) {
      failedRows += (group.items || []).length;
      continue;
    }

    createdMenus += 1;
    const menuId = String(menuResult.data.menu.menu_id || "");
    const sectionCounters = {};

    for (const item of group.items || []) {
      const compositionId = nextCompositionIdForRawText(compositionQueue, item.raw_text);
      if (!compositionId) {
        failedRows += 1;
        continue;
      }

      const sectionLabel = String(item.section_label || "Section 1");
      const sortOrder = Number(sectionCounters[sectionLabel] || 0);
      sectionCounters[sectionLabel] = sortOrder + 1;

      const rowResult = await callApi(
        "/api/builder/menus/" + encodeURIComponent(menuId) + "/rows",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: {
            day: sectionLabel,
            meal_slot: "section",
            composition_id: compositionId,
            note: "",
            sort_order: sortOrder,
          },
        },
      );

      if (rowResult && rowResult.data && rowResult.data.ok) {
        createdRows += 1;
      } else {
        failedRows += 1;
      }
    }

    sessionGroups.push({
      week_label: menuTitle,
      menu_id: menuId,
      items: (group.items || []).map((item) => ({
        raw_text: item.raw_text,
        section_label: item.section_label,
      })),
    });
  }

  return {
    created_menus: createdMenus,
    created_rows: createdRows,
    failed_rows: failedRows,
    groups: sessionGroups,
  };
}

function captureCurrentComponentIds() {
  return new Set((_cachedLibraryComponents || []).map((item) => String(item.component_id || "")));
}

function updateRecentComponentsFromSnapshot(previousSet) {
  const before = previousSet instanceof Set ? previousSet : new Set();
  const now = (_cachedLibraryComponents || []).map((item) => String(item.component_id || ""));
  _recentComponentIds = now.filter((id) => id && !before.has(id));
}

function setLastImportSession(importType, groups, note) {
  _lastImportSession = {
    import_type: String(importType || IMPORT_TYPE_DISH_LIST),
    import_type_label: importTypeLabel(importType),
    groups: normalizeRecentImportGroups(groups || []),
    note: String(note || ""),
  };
}

function bindBuilderHandlers() {
  const openComponentCreateModalBtn = document.getElementById("openComponentCreateModalBtn");
  const openImportLibraryModalBtn = document.getElementById("openImportLibraryModalBtn");
  const componentCreateModalCloseBtn = document.getElementById("componentCreateModalClose");
  const openDishesLibraryModalBtn = document.getElementById("openDishesLibraryModalBtn");
  const openNewDishModalBtn = document.getElementById("openNewDishModalBtn");
  const openImportModalBtn = document.getElementById("openImportModalBtn");
  const dishesLibraryModalCloseBtn = document.getElementById("dishesLibraryModalClose");
  const quickCreateModalCloseBtn = document.getElementById("quickCreateModalClose");
  const importLibraryModalCloseBtn = document.getElementById("importLibraryModalClose");
  const openAddComponentModalBtn = document.getElementById("openAddComponentModalBtn");
  const addComponentModalCloseBtn = document.getElementById("addComponentModalClose");
  const createDishBtn = document.getElementById("btnCreateDish");
  const createComponentBtn = document.getElementById("btnCreateComponent");
  const importLibraryBtn = document.getElementById("btnImportLibrary");
  const importLibraryPreviewBtn = document.getElementById("btnImportLibraryPreview");
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
  const recipeScalingPreviewBtn = document.getElementById("btnRecipeScalingPreview");
  const libraryComponentsSearchInput = document.getElementById("libraryComponentsSearch");
  const libraryComponentsScopeSelect = document.getElementById("libraryComponentsScope");

  if (libraryComponentsSearchInput) {
    libraryComponentsSearchInput.addEventListener("input", () => {
      filterLibraryComponents(libraryComponentsSearchInput.value);
    });
  }

  if (libraryComponentsScopeSelect) {
    libraryComponentsScopeSelect.addEventListener("change", () => {
      const query = libraryComponentsSearchInput ? String(libraryComponentsSearchInput.value || "") : "";
      filterLibraryComponents(query);
    });
  }

  if (openComponentCreateModalBtn) {
    openComponentCreateModalBtn.addEventListener("click", () => {
      openSimpleModal("componentCreateModal");
      const freeComponentNameEl = document.getElementById("freeComponentName");
      if (freeComponentNameEl) {
        freeComponentNameEl.focus();
      }
    });
  }

  if (openImportLibraryModalBtn) {
    openImportLibraryModalBtn.addEventListener("click", () => {
      openSimpleModal("importLibraryModal");
      const importInput = document.getElementById("importLibraryLines");
      if (importInput) {
        importInput.focus();
      }
    });
  }

  if (componentCreateModalCloseBtn) {
    componentCreateModalCloseBtn.addEventListener("click", () => {
      closeSimpleModal("componentCreateModal");
    });
  }

  if (openDishesLibraryModalBtn) {
    openDishesLibraryModalBtn.addEventListener("click", () => {
      openSimpleModal("dishesLibraryModal");
    });
  }

  if (openNewDishModalBtn) {
    openNewDishModalBtn.addEventListener("click", () => {
      openSimpleModal("quickCreateModal");
      const freeDishNameEl = document.getElementById("freeDishName");
      if (freeDishNameEl) {
        freeDishNameEl.focus();
      }
    });
  }

  if (openImportModalBtn) {
    openImportModalBtn.addEventListener("click", () => {
      openSimpleModal("importLibraryModal");
      const importInput = document.getElementById("importLibraryLines");
      if (importInput) {
        importInput.focus();
      }
    });
  }

  if (dishesLibraryModalCloseBtn) {
    dishesLibraryModalCloseBtn.addEventListener("click", () => {
      closeSimpleModal("dishesLibraryModal");
    });
  }

  if (quickCreateModalCloseBtn) {
    quickCreateModalCloseBtn.addEventListener("click", () => {
      closeSimpleModal("quickCreateModal");
    });
  }

  if (importLibraryModalCloseBtn) {
    importLibraryModalCloseBtn.addEventListener("click", () => {
      closeSimpleModal("importLibraryModal");
    });
  }

  if (openAddComponentModalBtn) {
    openAddComponentModalBtn.addEventListener("click", () => {
      openSimpleModal("addComponentModal");
      const paletteSearch = document.getElementById("builderPaletteSearch");
      if (paletteSearch) {
        paletteSearch.focus();
      }
    });
  }

  if (addComponentModalCloseBtn) {
    addComponentModalCloseBtn.addEventListener("click", () => {
      closeSimpleModal("addComponentModal");
    });
  }

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
          closeSimpleModal("dishesLibraryModal");
          closeSimpleModal("quickCreateModal");
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
          closeSimpleModal("componentCreateModal");
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
      const importSummaryView = document.getElementById("importSummaryView");
      const importType = selectedImportType();
      const beforeComponentIds = captureCurrentComponentIds();
      showLoading("importOut");
      if (importSummaryView) {
        importSummaryView.textContent = "Loading import summary...";
      }

      if (pendingImportSource !== "pasted") {
        setFileImportStatus("Preview pasted lines first, then import selected items.", true);
        return;
      }

      const selected = selectedFileImportLines();
      if (selected.length === 0) {
        setFileImportStatus("Select at least one preview line before import.", true);
        return;
      }

      try {
        const rawLines = selected;
        let groupedMenu = [];
        let linesToImport = rawLines;
        if (importType === IMPORT_TYPE_MENU) {
          groupedMenu = parseMenuImportStructure(rawLines);
          const extracted = buildDishLinesFromGroupedMenu(groupedMenu);
          linesToImport = extracted.length > 0 ? extracted : rawLines;
        }

        const result = await callApi("/api/builder/import", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: { lines: linesToImport },
        });

        const summary = result && result.data ? result.data.summary : null;
        if (result && result.data && result.data.ok) {
          if (importType === IMPORT_TYPE_MENU && Array.isArray(groupedMenu) && groupedMenu.length > 0 && summary) {
            const menuBuildResult = await createStructuredMenusFromImport(groupedMenu, summary);
            setLastImportSession(
              importType,
              menuBuildResult.groups,
              "Created " + String(menuBuildResult.created_menus) + " menus from structured import.",
            );
          } else {
            const rows = Array.isArray(summary && summary.row_results) ? summary.row_results : [];
            setLastImportSession(importType, [{ week_label: "Imported items", items: rows }], "Import completed.");
          }
        }

        renderImportSummary(result);
        showJson("importOut", result);
        await loadLibrary();
        updateRecentComponentsFromSnapshot(beforeComponentIds);
        const query = libraryComponentsSearchInput ? String(libraryComponentsSearchInput.value || "") : "";
        filterLibraryComponents(query);
        pendingFileImportItems = [];
        pendingFileIgnoredItems = [];
        importPreviewVisibleCount = 0;
        importIgnoredExpanded = false;
        pendingImportSource = "";
        refreshFilePreviewLists();
        setFileImportStatus("Pasted import completed.", false);
      } catch (error) {
        const failResult = { status: 0, data: { ok: false, error: String(error.message || error) } };
        renderImportSummary(failResult);
        showJson("importOut", failResult);
      }
    });
  }

  if (importLibraryPreviewBtn) {
    importLibraryPreviewBtn.addEventListener("click", async () => {
      await previewPastedImportLines();
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
        pendingImportSource = "file";
        renderFileImportPreview(result);
        showJson("importOut", result);
      } catch (error) {
        pendingImportSource = "";
        const fail = { status: 0, data: { ok: false, error: String(error.message || error) } };
        renderFileImportPreview(fail);
        showJson("importOut", fail);
      }
    });
  }

  if (importFileConfirmBtn) {
    importFileConfirmBtn.addEventListener("click", async () => {
      const selectedLines = selectedFileImportLines();
      const importType = selectedImportType();
      const beforeComponentIds = captureCurrentComponentIds();
      if (selectedLines.length === 0) {
        setFileImportStatus("No preview lines available. Run preview first.", true);
        return;
      }

      showLoading("importOut");
      setFileImportStatus("Importing previewed lines...", false);
      try {
        let groupedMenu = [];
        let linesToImport = selectedLines;
        if (importType === IMPORT_TYPE_MENU) {
          groupedMenu = parseMenuImportStructure(selectedLines);
          const extracted = buildDishLinesFromGroupedMenu(groupedMenu);
          linesToImport = extracted.length > 0 ? extracted : selectedLines;
        }

        const result = await callApi("/api/builder/import/file/confirm", {
          method: "POST",
          body: {
            lines: linesToImport,
            ignored_noise_count: pendingFileIgnoredItems.length,
          },
        });

        const summary = result && result.data ? result.data.summary : null;
        if (result && result.data && result.data.ok) {
          if (importType === IMPORT_TYPE_MENU && Array.isArray(groupedMenu) && groupedMenu.length > 0 && summary) {
            const menuBuildResult = await createStructuredMenusFromImport(groupedMenu, summary);
            setLastImportSession(
              importType,
              menuBuildResult.groups,
              "Created " + String(menuBuildResult.created_menus) + " menus from structured import.",
            );
          } else {
            const rows = Array.isArray(summary && summary.row_results) ? summary.row_results : [];
            setLastImportSession(importType, [{ week_label: "Imported items", items: rows }], "Import completed.");
          }
        }

        renderImportSummary(result);
        showJson("importOut", result);
        if (result && result.status < 400) {
          pendingFileImportItems = [];
          pendingFileIgnoredItems = [];
          importPreviewVisibleCount = 0;
          importIgnoredExpanded = false;
          refreshFilePreviewLists();
          importFileConfirmBtn.disabled = true;
          pendingImportSource = "";
          setFileImportStatus("File import completed.", false);
        } else {
          setFileImportStatus("File import failed", true);
        }
        await loadLibrary();
        updateRecentComponentsFromSnapshot(beforeComponentIds);
        const query = libraryComponentsSearchInput ? String(libraryComponentsSearchInput.value || "") : "";
        filterLibraryComponents(query);
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

      const beforeIds = new Set(
        (Array.isArray(currentBuilderComposition.components) ? currentBuilderComposition.components : []).map((item) =>
          String(item.component_id || ""),
        ),
      );

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
          const nextComponents = Array.isArray(result.data.composition.components)
            ? result.data.composition.components
            : [];
          const addedComponent = nextComponents.find((item) => !beforeIds.has(String(item.component_id || "")));
          if (addedComponent) {
            const addedId = String(addedComponent.component_id || "").trim();
            selectedComponentId = addedId || selectedComponentId;
            stageAddedComponentPulse(addedId);
            stageSelectedComponentPulse(addedId);
          }
          closeSimpleModal("addComponentModal");
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

  if (recipeScalingPreviewBtn) {
    recipeScalingPreviewBtn.addEventListener("click", async () => {
      await loadRecipeScalingPreview();
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
