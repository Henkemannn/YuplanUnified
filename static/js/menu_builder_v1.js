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
  const response = await fetch(url, {
    method: options.method || "GET",
    headers: options.headers || {},
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await response
    .json()
    .catch(() => ({ ok: false, error: "invalid_json", message: "Response was not JSON" }));
  return { status: response.status, data };
}

let allCompositions = [];
let currentRows = [];
let currentGroups = [];
let currentRowIndicatorsByDetailId = {};

const CONFLICT_TOKEN_META = {
  lactose_relevant: { icon: "🥛", label: "Milk/Lactose" },
  gluten_relevant: { icon: "🌾", label: "Gluten" },
  fish_relevant: { icon: "🐟", label: "Fish" },
  egg_relevant: { icon: "🥚", label: "Egg" },
  nut_relevant: { icon: "🥜", label: "Nuts" },
};

function tokenLabelForConflict(conflictKey) {
  const meta = CONFLICT_TOKEN_META[String(conflictKey || "")];
  if (meta) {
    return meta.icon + " " + meta.label;
  }
  return String(conflictKey || "").replace(/_/g, " ");
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

function buildRowIndicators(readinessRows) {
  const rows = Array.isArray(readinessRows) ? readinessRows : [];
  const indicators = {};
  for (const row of rows) {
    const detailId = String(row.menu_detail_id || "");
    if (!detailId) {
      continue;
    }
    const rowConflicts = row && row.conflict_preview && Array.isArray(row.conflict_preview.conflicts_present)
      ? row.conflict_preview.conflicts_present
      : [];
    const components = Array.isArray(row.components) ? row.components : [];
    const hasRecipe = components.some((component) => Boolean(component && component.primary_recipe_id));
    const hasComponentConflicts = components.some((component) => {
      const componentConflicts = component && component.conflict_preview && Array.isArray(component.conflict_preview.conflicts_present)
        ? component.conflict_preview.conflicts_present
        : [];
      return componentConflicts.length > 0;
    });
    indicators[detailId] = {
      hasRecipe,
      hasConflicts: rowConflicts.length > 0 || hasComponentConflicts,
    };
  }
  return indicators;
}

function renderRowIndicators(menuDetailId) {
  const wrap = document.createElement("div");
  wrap.className = "menu-row-indicators";
  const indicator = currentRowIndicatorsByDetailId[String(menuDetailId || "")] || {};

  if (indicator.hasRecipe) {
    const recipe = document.createElement("span");
    recipe.className = "menu-row-indicator menu-row-indicator-recipe";
    recipe.textContent = "🍳";
    recipe.title = "Has recipe";
    wrap.appendChild(recipe);
  }
  if (indicator.hasConflicts) {
    const conflict = document.createElement("span");
    conflict.className = "menu-row-indicator menu-row-indicator-conflict";
    conflict.textContent = "⚑";
    conflict.title = "Has potential conflicts";
    wrap.appendChild(conflict);
  }

  return wrap;
}

function renderQuickCompositionPalette(query) {
  const host = document.getElementById("rowCompositionPalette");
  if (!host) {
    return;
  }
  host.innerHTML = "";
  const filtered = filterCompositions(query).slice(0, 24);
  if (filtered.length === 0) {
    const empty = document.createElement("span");
    empty.className = "menu-quick-palette-empty";
    empty.textContent = "No compositions";
    host.appendChild(empty);
    return;
  }

  for (const composition of filtered) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "menu-quick-pill";
    btn.textContent = String(composition.composition_name || composition.composition_id || "");
    const compositionId = String(composition.composition_id || "");
    btn.title = "Add " + btn.textContent + " to current menu";
    btn.addEventListener("click", async () => {
      await addMenuRowByCompositionId(compositionId);
    });
    host.appendChild(btn);
  }
}

async function addMenuRowByCompositionId(compositionId) {
  const menuId = getActiveMenuId();
  const dayEl = document.getElementById("rowDay");
  const mealSlotEl = document.getElementById("rowMealSlot");
  const noteEl = document.getElementById("rowNote");
  const sortOrderEl = document.getElementById("rowSortOrder");
  const compositionEl = document.getElementById("rowCompositionId");

  if (!menuId) {
    showJson("addMenuRowOut", { ok: false, error: "active menu_id is required" });
    return;
  }

  const selectedCompositionId = String(compositionId || (compositionEl ? compositionEl.value : "") || "").trim();
  if (!selectedCompositionId) {
    showJson("addMenuRowOut", { ok: false, error: "composition_id is required" });
    return;
  }
  if (compositionEl) {
    compositionEl.value = selectedCompositionId;
  }

  const payload = {
    day: dayEl ? String(dayEl.value || "").trim() : "",
    meal_slot: mealSlotEl ? String(mealSlotEl.value || "").trim() : "",
    composition_id: selectedCompositionId,
    note: noteEl ? String(noteEl.value || "").trim() : "",
    sort_order: sortOrderEl ? Number.parseInt(String(sortOrderEl.value || "0"), 10) : 0,
  };

  showLoading("addMenuRowOut");
  const result = await callApi("/api/builder/menus/" + encodeURIComponent(menuId) + "/rows", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: payload,
  });
  showJson("addMenuRowOut", result);
  if (result && result.data && result.data.ok) {
    if (noteEl) {
      noteEl.value = "";
    }
    await refreshRows();
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

function isMenuDeclarationVisible() {
  const toggle = document.getElementById("menuDeclarationVisibleToggle");
  return toggle ? Boolean(toggle.checked) : true;
}

function renderMenuDeclarationPreview(payload) {
  const status = document.getElementById("menuDeclarationStatus");
  const disabled = document.getElementById("menuDeclarationDisabled");
  const summary = document.getElementById("menuDeclarationSignalsSummary");
  const enabled = Boolean(payload && payload.declaration_enabled);
  const readiness = enabled ? (payload.readiness || {}) : null;
  const signals = readiness && Array.isArray(readiness.trait_signals_present)
    ? readiness.trait_signals_present
    : [];
  const conflictPreview = readiness && readiness.conflict_preview ? readiness.conflict_preview : {};
  const conflictsPresent = Array.isArray(conflictPreview.conflicts_present)
    ? conflictPreview.conflicts_present
    : [];
  const conflictSources = Array.isArray(conflictPreview.conflict_sources)
    ? conflictPreview.conflict_sources
    : [];

  if (status) {
    status.textContent = "Read-only preview. No automation applied.";
  }
  if (disabled) {
    if (enabled) {
      disabled.classList.add("hidden");
    } else {
      disabled.classList.remove("hidden");
      disabled.textContent = "Declaration preview unavailable right now.";
    }
  }
  if (summary) {
    if (!enabled) {
      summary.textContent = "Declaration preview disabled";
    } else if (conflictsPresent.length > 0) {
      summary.textContent = "This menu contains: " + conflictsPresent.map((v) => tokenLabelForConflict(v)).join(", ");
    } else if (signals.length > 0) {
      summary.textContent = "This menu contains declaration signals.";
    } else {
      summary.textContent = "This menu contains no declaration conflicts.";
    }
  }

  renderTokenList("menuDeclarationSignals", signals, "No signals", (item) => String(item || ""));
  const conflictItems = [];
  for (const source of conflictSources) {
    const traits = Array.isArray(source.triggering_trait_signals)
      ? source.triggering_trait_signals.join(", ")
      : "";
    conflictItems.push(tokenLabelForConflict(source.conflict_key) + (traits ? " · " + traits : ""));
  }
  if (conflictItems.length === 0 && conflictsPresent.length > 0) {
    for (const conflict of conflictsPresent) {
      conflictItems.push(tokenLabelForConflict(conflict));
    }
  }
  renderTokenList("menuConflictList", conflictItems, "No potential conflicts", (item) => String(item || ""));

  const warnings = [];
  if (readiness && Array.isArray(readiness.warnings)) {
    warnings.push(...readiness.warnings);
  }
  const rows = readiness && Array.isArray(readiness.rows) ? readiness.rows : [];
  currentRowIndicatorsByDetailId = enabled ? buildRowIndicators(rows) : {};
  const searchInput = document.getElementById("compositionSearch");
  renderMenuRowsGrouped(currentGroups, searchInput ? String(searchInput.value || "") : "");
  for (const row of rows) {
    const rowWarnings = Array.isArray(row.warnings) ? row.warnings : [];
    for (const warning of rowWarnings) {
      warnings.push("Row " + String(row.menu_detail_id || "") + ": " + String(warning || ""));
    }
  }
  setListContent("menuDeclarationWarnings", warnings, "No warnings");
}

async function refreshDeclarationPreview() {
  const menuId = getActiveMenuId();
  if (!menuId) {
    renderMenuDeclarationPreview({ declaration_enabled: false, readiness: null });
    return;
  }

  const include = isMenuDeclarationVisible() ? "1" : "0";
  const result = await callApi(
    "/api/builder/menus/" + encodeURIComponent(menuId) + "/declaration-readiness?include_declaration=" + include,
    { method: "GET" },
  );
  if (!result || result.status >= 400 || !result.data || !result.data.ok) {
    renderMenuDeclarationPreview({ declaration_enabled: false, readiness: null });
    return;
  }
  renderMenuDeclarationPreview(result.data);
}

function getActiveMenuId() {
  const el = document.getElementById("activeMenuId");
  return el ? String(el.value || "").trim() : "";
}

function setActiveMenuId(menuId) {
  const el = document.getElementById("activeMenuId");
  if (el) {
    el.value = String(menuId || "");
  }
}

function normalizeText(value) {
  return String(value || "").trim().toLowerCase();
}

function filterCompositions(query) {
  const q = normalizeText(query);
  if (!q) {
    return allCompositions;
  }
  return allCompositions.filter((item) => {
    const id = normalizeText(item.composition_id);
    const name = normalizeText(item.composition_name);
    return id.includes(q) || name.includes(q);
  });
}

function renderCompositionOptionsForSelect(selectId, compositions, selectedValue) {
  const select = document.getElementById(selectId);
  if (!select) {
    return;
  }
  select.innerHTML = "";

  const list = Array.isArray(compositions) ? compositions : [];
  for (const row of list) {
    const opt = document.createElement("option");
    const value = String(row.composition_id || "");
    opt.value = value;
    opt.textContent = String(row.composition_name || row.composition_id || "");
    if (selectedValue && selectedValue === value) {
      opt.selected = true;
    }
    select.appendChild(opt);
  }
}

function renderCompositionOptions(query) {
  const filtered = filterCompositions(query);
  const addSelected = (() => {
    const el = document.getElementById("rowCompositionId");
    return el ? String(el.value || "") : "";
  })();
  const editSelected = (() => {
    const el = document.getElementById("editRowCompositionId");
    return el ? String(el.value || "") : "";
  })();
  renderCompositionOptionsForSelect("rowCompositionId", filtered, addSelected);
  renderCompositionOptionsForSelect("editRowCompositionId", filtered, editSelected);
  renderQuickCompositionPalette(query);
}

async function loadCompositionOptions() {
  const result = await callApi("/api/builder/library", { method: "GET" });
  allCompositions = (result && result.data && result.data.compositions) || [];
  renderCompositionOptions("");
  showJson("menuRowsOut", {
    ok: true,
    message: "Library compositions loaded",
    count: allCompositions.length,
  });
}

function rowMatchesQuery(row, query) {
  const q = normalizeText(query);
  if (!q) {
    return true;
  }
  const idText = normalizeText(row.composition_id);
  const nameText = normalizeText(row.composition_name);
  const unresolvedText = normalizeText(row.unresolved_text);
  return idText.includes(q) || nameText.includes(q) || unresolvedText.includes(q);
}

function renderMenuRowsGrouped(groups, query) {
  const body = document.getElementById("menuRowsBody");
  if (!body) {
    return;
  }
  body.innerHTML = "";

  const groupList = Array.isArray(groups) ? groups : [];
  if (groupList.length === 0) {
    const empty = document.createElement("div");
    empty.textContent = "No rows";
    body.appendChild(empty);
    return;
  }

  let renderedCount = 0;

  for (const group of groupList) {
    const rows = Array.isArray(group.rows) ? group.rows : [];
    const filteredRows = rows.filter((row) => rowMatchesQuery(row, query));
    if (filteredRows.length === 0) {
      continue;
    }

    const section = document.createElement("section");
    section.className = "menu-group";

    const header = document.createElement("div");
    header.className = "menu-group-header";
    header.textContent =
      String(group.day || "") + " - " + String(group.meal_slot || "") + " (" + String(filteredRows.length) + ")";
    section.appendChild(header);

    const list = document.createElement("div");
    list.className = "menu-group-list";

    for (const row of filteredRows) {
      const card = document.createElement("article");
      const unresolved = row.is_unresolved || row.composition_ref_type === "unresolved";
      card.className = unresolved ? "menu-row-card unresolved" : "menu-row-card";

      const titleWrap = document.createElement("div");
      titleWrap.className = "menu-row-title-wrap";

      const title = document.createElement("div");
      title.className = "menu-row-title";
      if (unresolved) {
        title.textContent = "Unresolved: " + String(row.unresolved_text || "") ;
      } else {
        title.textContent = String(row.composition_name || row.composition_id || "");
      }
      titleWrap.appendChild(title);
      if (!unresolved) {
        titleWrap.appendChild(renderRowIndicators(row.menu_detail_id));
      }
      card.appendChild(titleWrap);

      const meta = document.createElement("div");
      meta.className = "menu-row-meta";
      meta.textContent =
        "sort " + String(row.sort_order || 0) +
        " | ref " + String(row.composition_ref_type || "") +
        (row.composition_id ? " | id " + String(row.composition_id) : "");
      card.appendChild(meta);

      if (row.note) {
        const note = document.createElement("div");
        note.className = "menu-row-note";
        note.textContent = "Note: " + String(row.note || "");
        card.appendChild(note);
      }

      const actions = document.createElement("div");
      actions.className = "menu-row-actions";

      const editBtn = document.createElement("button");
      editBtn.type = "button";
      editBtn.textContent = "Edit";
      editBtn.addEventListener("click", () => {
        openEditPanel(row);
      });
      actions.appendChild(editBtn);

      const deleteBtn = document.createElement("button");
      deleteBtn.type = "button";
      deleteBtn.textContent = "Delete";
      deleteBtn.style.marginLeft = "6px";
      deleteBtn.addEventListener("click", async () => {
        await deleteRow(row.menu_detail_id);
      });
      actions.appendChild(deleteBtn);

      card.appendChild(actions);
      list.appendChild(card);
      renderedCount += 1;
    }

    section.appendChild(list);
    body.appendChild(section);
  }

  if (renderedCount === 0) {
    const empty = document.createElement("div");
    empty.textContent = "No rows match current filter";
    body.appendChild(empty);
  }
}

function openEditPanel(row) {
  const panel = document.getElementById("editRowPanel");
  const rowId = document.getElementById("editRowId");
  const day = document.getElementById("editRowDay");
  const mealSlot = document.getElementById("editRowMealSlot");
  const composition = document.getElementById("editRowCompositionId");
  const note = document.getElementById("editRowNote");
  const sortOrder = document.getElementById("editRowSortOrder");

  if (!panel || !rowId || !day || !mealSlot || !composition || !note || !sortOrder) {
    return;
  }

  rowId.value = String(row.menu_detail_id || "");
  day.value = String(row.day || "monday");
  mealSlot.value = String(row.meal_slot || "lunch");
  composition.value = String(row.composition_id || "");
  note.value = String(row.note || "");
  sortOrder.value = String(row.sort_order || 0);
  panel.classList.remove("hidden");
}

function closeEditPanel() {
  const panel = document.getElementById("editRowPanel");
  const rowId = document.getElementById("editRowId");
  if (panel) {
    panel.classList.add("hidden");
  }
  if (rowId) {
    rowId.value = "";
  }
}

async function refreshRows() {
  const menuId = getActiveMenuId();
  if (!menuId) {
    showJson("menuRowsOut", { ok: false, error: "active menu_id is required" });
    return;
  }

  showLoading("menuRowsOut");
  const result = await callApi("/api/builder/menus/" + encodeURIComponent(menuId) + "/rows", {
    method: "GET",
  });
  const rows = (result && result.data && result.data.rows) || [];
  const groups = (result && result.data && result.data.groups) || [];
  const searchInput = document.getElementById("compositionSearch");
  const query = searchInput ? String(searchInput.value || "") : "";
  currentRows = rows;
  currentGroups = groups;
  renderMenuRowsGrouped(groups, query);
  await refreshDeclarationPreview();
  showJson("menuRowsOut", result);
}

async function deleteRow(menuDetailId) {
  const menuId = getActiveMenuId();
  if (!menuId) {
    showJson("menuRowsOut", { ok: false, error: "active menu_id is required" });
    return;
  }
  const confirmed = window.confirm("Delete this menu row?");
  if (!confirmed) {
    return;
  }
  const result = await callApi(
    "/api/builder/menus/" + encodeURIComponent(menuId) + "/rows/" + encodeURIComponent(String(menuDetailId || "")),
    { method: "DELETE" },
  );
  showJson("menuRowsOut", result);
  await refreshRows();
}

async function saveRowEdit() {
  const menuId = getActiveMenuId();
  const rowId = document.getElementById("editRowId");
  const day = document.getElementById("editRowDay");
  const mealSlot = document.getElementById("editRowMealSlot");
  const composition = document.getElementById("editRowCompositionId");
  const note = document.getElementById("editRowNote");
  const sortOrder = document.getElementById("editRowSortOrder");

  if (!menuId) {
    showJson("editMenuRowOut", { ok: false, error: "active menu_id is required" });
    return;
  }
  const menuDetailId = rowId ? String(rowId.value || "").trim() : "";
  if (!menuDetailId) {
    showJson("editMenuRowOut", { ok: false, error: "menu_detail_id is required" });
    return;
  }

  const payload = {
    day: day ? String(day.value || "").trim() : "",
    meal_slot: mealSlot ? String(mealSlot.value || "").trim() : "",
    composition_id: composition ? String(composition.value || "").trim() : "",
    note: note ? String(note.value || "").trim() : "",
    sort_order: sortOrder ? Number.parseInt(String(sortOrder.value || "0"), 10) : 0,
  };

  showLoading("editMenuRowOut");
  const result = await callApi(
    "/api/builder/menus/" + encodeURIComponent(menuId) + "/rows/" + encodeURIComponent(menuDetailId),
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: payload,
    },
  );
  showJson("editMenuRowOut", result);
  if (result && result.data && result.data.ok) {
    closeEditPanel();
    await refreshRows();
  }
}

function bindHandlers() {
  const createMenuBtn = document.getElementById("btnCreateMenu");
  const addRowBtn = document.getElementById("btnAddMenuRow");
  const refreshRowsBtn = document.getElementById("btnRefreshRows");
  const compositionSearch = document.getElementById("compositionSearch");
  const saveEditBtn = document.getElementById("btnSaveRowEdit");
  const cancelEditBtn = document.getElementById("btnCancelRowEdit");
  const declarationToggle = document.getElementById("menuDeclarationVisibleToggle");

  if (createMenuBtn) {
    createMenuBtn.addEventListener("click", async () => {
      const menuTitleEl = document.getElementById("menuTitle");
      const menuIdEl = document.getElementById("menuId");
      const siteIdEl = document.getElementById("siteId");
      const weekKeyEl = document.getElementById("weekKey");

      const payload = {
        title: menuTitleEl ? String(menuTitleEl.value || "").trim() : "",
        menu_id: menuIdEl ? String(menuIdEl.value || "").trim() : "",
        site_id: siteIdEl ? String(siteIdEl.value || "").trim() : "",
        week_key: weekKeyEl ? String(weekKeyEl.value || "").trim() : "",
      };

      showLoading("createMenuOut");
      const result = await callApi("/api/builder/menus", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: payload,
      });
      showJson("createMenuOut", result);
      if (result && result.data && result.data.ok && result.data.menu && result.data.menu.menu_id) {
        setActiveMenuId(result.data.menu.menu_id);
        await refreshRows();
      }
    });
  }

  if (addRowBtn) {
    addRowBtn.addEventListener("click", async () => {
      await addMenuRowByCompositionId("");
    });
  }

  if (refreshRowsBtn) {
    refreshRowsBtn.addEventListener("click", async () => {
      await refreshRows();
    });
  }

  if (compositionSearch) {
    compositionSearch.addEventListener("input", () => {
      renderCompositionOptions(String(compositionSearch.value || ""));
      renderMenuRowsGrouped(currentGroups, String(compositionSearch.value || ""));
    });
  }

  if (saveEditBtn) {
    saveEditBtn.addEventListener("click", async () => {
      await saveRowEdit();
    });
  }

  if (cancelEditBtn) {
    cancelEditBtn.addEventListener("click", () => {
      closeEditPanel();
    });
  }

  if (declarationToggle) {
    declarationToggle.addEventListener("change", async () => {
      await refreshDeclarationPreview();
    });
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  bindHandlers();
  try {
    await loadCompositionOptions();
  } catch (error) {
    showJson("menuRowsOut", { ok: false, error: String(error.message || error) });
  }
});
