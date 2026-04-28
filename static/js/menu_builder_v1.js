function showText(targetId, text) {
  const el = document.getElementById(targetId);
  if (!el) {
    return;
  }
  el.textContent = String(text || "");
}

function showLoading(targetId) {
  showText(targetId, "Loading...");
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

const DEFAULT_SITE_ID = "site_1";
const DEFAULT_WEEK_KEY = "2026-W16";
const DEFAULT_MEAL_SLOT = "section";

let allDishes = [];
let activeMenuId = "";
let activeMenuTitle = "";
let currentRows = [];
let sectionDrafts = [];
let pickerOpenSection = "";
let pickerOpenSlotIndex = null;

function makeSectionDraft(name, slotLabels) {
  return {
    name: String(name || "").trim(),
    slotLabels: Array.isArray(slotLabels)
      ? slotLabels.map((item) => String(item || "").trim()).filter(Boolean)
      : [],
  };
}

function defaultSlotLabel(index) {
  return "Option " + String(Number(index) + 1);
}

function defaultSectionLabel(menuType, index) {
  const i = Number(index) + 1;
  if (String(menuType || "") === "weekly_lunch") {
    return "Day " + String(i);
  }
  return "Section " + String(i);
}

function findDraftIndexByName(name) {
  const target = normalizeLower(name);
  return sectionDrafts.findIndex((item) => normalizeLower(item.name) === target);
}

function getDraftSectionByName(name) {
  const index = findDraftIndexByName(name);
  return index >= 0 ? sectionDrafts[index] : null;
}

function ensureDraftSection(name) {
  const value = normalize(name);
  if (!value) {
    return null;
  }
  const existing = getDraftSectionByName(value);
  if (existing) {
    return existing;
  }
  const next = makeSectionDraft(value, [defaultSlotLabel(0)]);
  sectionDrafts.push(next);
  return next;
}

function ensureSlotLabel(sectionName, slotIndex) {
  const draft = ensureDraftSection(sectionName);
  if (!draft) {
    return;
  }
  const targetIndex = Math.max(0, Number(slotIndex) || 0);
  while (draft.slotLabels.length <= targetIndex) {
    draft.slotLabels.push(defaultSlotLabel(draft.slotLabels.length));
  }
}

function syncDraftsWithRows(rows) {
  const grouped = {};
  for (const row of rows || []) {
    const section = normalize(row.day);
    if (!section) {
      continue;
    }
    if (!grouped[section]) {
      grouped[section] = [];
    }
    grouped[section].push(row);
  }

  for (const name of Object.keys(grouped)) {
    const draft = ensureDraftSection(name);
    if (!draft) {
      continue;
    }
    const count = Math.max(1, grouped[name].length);
    while (draft.slotLabels.length < count) {
      draft.slotLabels.push(defaultSlotLabel(draft.slotLabels.length));
    }
  }
}

function normalize(value) {
  return String(value || "").trim();
}

function normalizeLower(value) {
  return normalize(value).toLowerCase();
}

function setActiveMenu(menu) {
  activeMenuId = String((menu && menu.menu_id) || "");
  activeMenuTitle = String((menu && menu.title) || "");
  const meta = document.getElementById("activeMenuMeta");
  if (!meta) {
    return;
  }
  if (!activeMenuId) {
    meta.textContent = "No active menu";
    return;
  }
  meta.textContent =
    "Active menu: " +
    (activeMenuTitle ? activeMenuTitle + " (" + activeMenuId + ")" : activeMenuId);
}

function rowsToSlotMap(rows) {
  const mapping = {};
  const leftovers = [];

  for (const row of rows) {
    const sort = Number(row.sort_order);
    if (Number.isInteger(sort) && sort >= 0 && !mapping[sort]) {
      mapping[sort] = row;
    } else {
      leftovers.push(row);
    }
  }

  let idx = 0;
  for (const row of leftovers) {
    while (mapping[idx]) {
      idx += 1;
    }
    mapping[idx] = row;
    idx += 1;
  }

  return mapping;
}

function sectionsFromRows(rows) {
  const bySection = {};
  for (const row of rows) {
    const sectionName = normalize(row.day);
    if (!sectionName) {
      continue;
    }
    if (!bySection[sectionName]) {
      bySection[sectionName] = [];
    }
    bySection[sectionName].push(row);
  }

  const sectionNames = [];
  for (const draft of sectionDrafts) {
    const name = normalize(draft.name);
    if (name && !sectionNames.some((item) => normalizeLower(item) === normalizeLower(name))) {
      sectionNames.push(name);
    }
  }
  for (const name of Object.keys(bySection).sort((a, b) => a.localeCompare(b))) {
    if (!sectionNames.some((item) => normalizeLower(item) === normalizeLower(name))) {
      sectionNames.push(name);
    }
  }

  const sections = sectionNames.map((name) => {
    const items = (bySection[name] || []).slice().sort((left, right) => {
      const leftSort = Number(left.sort_order || 0);
      const rightSort = Number(right.sort_order || 0);
      if (leftSort !== rightSort) {
        return leftSort - rightSort;
      }
      return String(left.menu_detail_id || "").localeCompare(String(right.menu_detail_id || ""));
    });

    const draft = getDraftSectionByName(name) || makeSectionDraft(name, []);
    const slotMap = rowsToSlotMap(items);
    const maxSlotIndex = Math.max(
      draft.slotLabels.length - 1,
      ...Object.keys(slotMap).map((value) => Number(value)).filter((value) => Number.isInteger(value) && value >= 0),
    );
    const slotCount = Math.max(1, maxSlotIndex + 1);
    const slots = [];
    for (let i = 0; i < slotCount; i += 1) {
      slots.push({
        index: i,
        label: normalize(draft.slotLabels[i]) || defaultSlotLabel(i),
        row: slotMap[i] || null,
      });
    }

    return {
      name,
      rows: items,
      slotLabels: draft.slotLabels.slice(),
      slots,
    };
  });

  return sections;
}

function nextEmptySlotIndex(section) {
  const slots = Array.isArray(section && section.slots) ? section.slots : [];
  const empty = slots.find((slot) => !slot.row);
  if (empty) {
    return Number(empty.index || 0);
  }
  return slots.length;
}

function setSlotLabel(sectionName, slotIndex, value) {
  const draft = ensureDraftSection(sectionName);
  if (!draft) {
    return;
  }
  const index = Math.max(0, Number(slotIndex) || 0);
  ensureSlotLabel(sectionName, index);
  draft.slotLabels[index] = normalize(value) || defaultSlotLabel(index);
}

function removeSlotLabel(sectionName, slotIndex) {
  const draft = getDraftSectionByName(sectionName);
  if (!draft) {
    return;
  }
  const index = Math.max(0, Number(slotIndex) || 0);
  if (index >= draft.slotLabels.length) {
    return;
  }
  draft.slotLabels.splice(index, 1);
  if (draft.slotLabels.length === 0) {
    draft.slotLabels.push(defaultSlotLabel(0));
  }
}

function getRowForSectionSlot(sectionName, slotIndex) {
  const section = normalize(sectionName);
  const index = Math.max(0, Number(slotIndex) || 0);
  return currentRows.find(
    (row) => normalizeLower(row.day) === normalizeLower(section) && Number(row.sort_order) === index,
  ) || null;
}

async function resequenceSectionRows(sectionName) {
  const rows = currentRows
    .filter((row) => normalizeLower(row.day) === normalizeLower(sectionName))
    .slice()
    .sort((left, right) => {
      const leftSort = Number(left.sort_order || 0);
      const rightSort = Number(right.sort_order || 0);
      if (leftSort !== rightSort) {
        return leftSort - rightSort;
      }
      return String(left.menu_detail_id || "").localeCompare(String(right.menu_detail_id || ""));
    });

  for (let i = 0; i < rows.length; i += 1) {
    const row = rows[i];
    if (Number(row.sort_order) === i) {
      continue;
    }
    const result = await callApi(
      "/api/builder/menus/" + encodeURIComponent(activeMenuId) + "/rows/" + encodeURIComponent(String(row.menu_detail_id || "")),
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: {
          day: String(row.day || sectionName),
          meal_slot: String(row.meal_slot || DEFAULT_MEAL_SLOT),
          composition_id: String(row.composition_id || ""),
          note: String(row.note || ""),
          sort_order: i,
        },
      },
    );
    if (!result || !result.data || !result.data.ok) {
      throw new Error("Could not resequence section rows.");
    }
  }
}

function renderSections() {
  const host = document.getElementById("menuSections");
  if (!host) {
    return;
  }
  host.innerHTML = "";

  const sections = sectionsFromRows(currentRows);
  if (sections.length === 0) {
    const empty = document.createElement("div");
    empty.className = "menu-empty";
    empty.textContent = "No sections yet. Add your first section.";
    host.appendChild(empty);
    return;
  }

  for (const section of sections) {
    const block = document.createElement("section");
    block.className = "menu-section";

    const header = document.createElement("div");
    header.className = "menu-section-header";

    const title = document.createElement("p");
    title.className = "menu-section-name";
    title.textContent = section.name;

    const actions = document.createElement("div");
    actions.className = "menu-section-actions";

    const addDishBtn = document.createElement("button");
    addDishBtn.type = "button";
    addDishBtn.textContent = "Add dish";
    addDishBtn.addEventListener("click", () => {
      openDishPicker(section.name, nextEmptySlotIndex(section));
    });

    const addSlotBtn = document.createElement("button");
    addSlotBtn.type = "button";
    addSlotBtn.textContent = "Add slot";
    addSlotBtn.addEventListener("click", () => {
      addSlotToSection(section.name);
    });

    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.textContent = "Rename";
    renameBtn.addEventListener("click", async () => {
      await renameSection(section.name);
    });

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.textContent = "Remove section";
    removeBtn.addEventListener("click", async () => {
      await removeSection(section.name);
    });

    actions.appendChild(addDishBtn);
  actions.appendChild(addSlotBtn);
    actions.appendChild(renameBtn);
    actions.appendChild(removeBtn);

    header.appendChild(title);
    header.appendChild(actions);
    block.appendChild(header);

    const list = document.createElement("div");
    list.className = "menu-dish-list";

    for (const slot of section.slots) {
      const slotRow = document.createElement("div");
      slotRow.className = "menu-slot-row";

      const slotTop = document.createElement("div");
      slotTop.className = "menu-slot-top";

      const slotName = document.createElement("p");
      slotName.className = "menu-slot-name";
      slotName.textContent = slot.label;

      const slotActions = document.createElement("div");
      slotActions.className = "menu-slot-actions";

      const renameSlotBtn = document.createElement("button");
      renameSlotBtn.type = "button";
      renameSlotBtn.textContent = "Rename slot";
      renameSlotBtn.addEventListener("click", () => {
        renameSlot(section.name, slot.index);
      });

      const pickDishBtn = document.createElement("button");
      pickDishBtn.type = "button";
      pickDishBtn.textContent = "Pick dish";
      pickDishBtn.addEventListener("click", () => {
        openDishPicker(section.name, slot.index);
      });

      const typeDishBtn = document.createElement("button");
      typeDishBtn.type = "button";
      typeDishBtn.textContent = "Type new dish";
      typeDishBtn.addEventListener("click", async () => {
        await addFreeTextDish(section.name, slot.index);
      });

      slotActions.appendChild(renameSlotBtn);
      slotActions.appendChild(pickDishBtn);
      slotActions.appendChild(typeDishBtn);

      if (slot.row) {
        const removeDishBtn = document.createElement("button");
        removeDishBtn.type = "button";
        removeDishBtn.textContent = "Remove dish";
        removeDishBtn.addEventListener("click", async () => {
          await removeDish(slot.row.menu_detail_id);
        });
        slotActions.appendChild(removeDishBtn);
      }

      const removeSlotBtn = document.createElement("button");
      removeSlotBtn.type = "button";
      removeSlotBtn.textContent = "Remove slot";
      removeSlotBtn.addEventListener("click", async () => {
        await removeSlot(section.name, slot.index);
      });
      slotActions.appendChild(removeSlotBtn);

      slotTop.appendChild(slotName);
      slotTop.appendChild(slotActions);
      slotRow.appendChild(slotTop);

      if (!slot.row) {
        const empty = document.createElement("div");
        empty.className = "menu-empty";
        empty.textContent = "No dish in this slot yet.";
        slotRow.appendChild(empty);
      } else {
        const dishRow = document.createElement("div");
        dishRow.className = "menu-dish-row";

        const left = document.createElement("div");
        const label = document.createElement("div");
        label.className = "menu-dish-label";
        label.textContent = String(slot.row.composition_name || slot.row.composition_id || "Dish");

        const meta = document.createElement("div");
        meta.className = "menu-dish-meta";
        meta.textContent = "dish_id: " + String(slot.row.composition_id || "") + " | slot: " + String(slot.index + 1);

        left.appendChild(label);
        left.appendChild(meta);
        dishRow.appendChild(left);
        slotRow.appendChild(dishRow);
      }

      list.appendChild(slotRow);
    }

    block.appendChild(list);
    host.appendChild(block);
  }
}

function openModal(id) {
  const el = document.getElementById(id);
  if (!el) {
    return;
  }
  el.classList.remove("hidden");
}

function closeModal(id) {
  const el = document.getElementById(id);
  if (!el) {
    return;
  }
  el.classList.add("hidden");
}

function filterDishes(query) {
  const q = normalizeLower(query);
  if (!q) {
    return allDishes;
  }
  return allDishes.filter((item) => {
    const id = normalizeLower(item.composition_id);
    const name = normalizeLower(item.composition_name);
    return id.includes(q) || name.includes(q);
  });
}

function renderDishPicker() {
  const host = document.getElementById("dishPickerList");
  const search = document.getElementById("dishPickerSearch");
  if (!host) {
    return;
  }

  host.innerHTML = "";
  const query = search ? String(search.value || "") : "";
  const filtered = filterDishes(query);
  if (filtered.length === 0) {
    const empty = document.createElement("div");
    empty.className = "menu-empty";
    empty.textContent = "No dishes found.";
    host.appendChild(empty);
    return;
  }

  for (const dish of filtered) {
    const row = document.createElement("div");
    row.className = "menu-picker-item";

    const name = document.createElement("div");
    name.textContent = String(dish.composition_name || dish.composition_id || "");

    const addBtn = document.createElement("button");
    addBtn.type = "button";
    addBtn.textContent = "Attach";
    addBtn.addEventListener("click", async () => {
      await attachDishToSection(String(dish.composition_id || ""));
    });

    row.appendChild(name);
    row.appendChild(addBtn);
    host.appendChild(row);
  }
}

function openDishPicker(sectionName, slotIndex) {
  if (!activeMenuId) {
    showText("menuSectionsOut", "Create or open a menu first.");
    return;
  }

  pickerOpenSection = String(sectionName || "");
  pickerOpenSlotIndex = Number.isInteger(Number(slotIndex)) ? Math.max(0, Number(slotIndex)) : null;
  const meta = document.getElementById("dishPickerSectionMeta");
  if (meta) {
    meta.textContent = "Section: " + pickerOpenSection;
  }
  const slotMeta = document.getElementById("dishPickerSlotMeta");
  if (slotMeta) {
    slotMeta.textContent = pickerOpenSlotIndex === null
      ? "Slot: next available"
      : "Slot: " + String(pickerOpenSlotIndex + 1);
  }
  const search = document.getElementById("dishPickerSearch");
  if (search) {
    search.value = "";
  }
  showText("dishPickerOut", "");
  renderDishPicker();
  openModal("dishPickerModal");
}

async function attachCompositionToSlot(sectionName, slotIndex, compositionId) {
  const sectionValue = normalize(sectionName);
  const compositionIdValue = normalize(compositionId);
  if (!activeMenuId || !sectionValue || !compositionIdValue) {
    return { ok: false };
  }

  const targetSlot = Math.max(0, Number(slotIndex) || 0);
  ensureSlotLabel(sectionValue, targetSlot);
  const existing = getRowForSectionSlot(sectionValue, targetSlot);

  if (existing) {
    const updateResult = await callApi(
      "/api/builder/menus/" + encodeURIComponent(activeMenuId) + "/rows/" + encodeURIComponent(String(existing.menu_detail_id || "")),
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: {
          day: sectionValue,
          meal_slot: String(existing.meal_slot || DEFAULT_MEAL_SLOT),
          composition_id: compositionIdValue,
          note: String(existing.note || ""),
          sort_order: targetSlot,
        },
      },
    );
    return updateResult && updateResult.data && updateResult.data.ok
      ? { ok: true, mode: "updated" }
      : { ok: false };
  }

  const createResult = await callApi(
    "/api/builder/menus/" + encodeURIComponent(activeMenuId) + "/rows",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        day: sectionValue,
        meal_slot: DEFAULT_MEAL_SLOT,
        composition_id: compositionIdValue,
        note: "",
        sort_order: targetSlot,
      },
    },
  );

  return createResult && createResult.data && createResult.data.ok
    ? { ok: true, mode: "created" }
    : { ok: false };
}

async function attachDishToSection(compositionId) {
  if (!activeMenuId) {
    showText("dishPickerOut", "Create or open a menu first.");
    return;
  }

  const compositionIdValue = normalize(compositionId);
  if (!compositionIdValue) {
    showText("dishPickerOut", "Dish id is required.");
    return;
  }

  const sectionName = normalize(pickerOpenSection);
  if (!sectionName) {
    showText("dishPickerOut", "Section is required.");
    return;
  }

  const slotIndex = pickerOpenSlotIndex === null
    ? currentRows.filter((row) => normalizeLower(row.day) === normalizeLower(sectionName)).length
    : pickerOpenSlotIndex;

  showLoading("dishPickerOut");
  const result = await attachCompositionToSlot(sectionName, slotIndex, compositionIdValue);
  if (!result || !result.ok) {
    showText("dishPickerOut", "Could not attach dish.");
    return;
  }

  showText("dishPickerOut", result.mode === "updated" ? "Dish replaced." : "Dish attached.");
  await refreshRows();
  closeModal("dishPickerModal");
}

async function removeDish(menuDetailId, options) {
  const config = options || {};
  const detailIdValue = normalize(menuDetailId);
  if (!activeMenuId || !detailIdValue) {
    return;
  }
  const confirmed = config.confirm === false ? true : window.confirm("Remove this dish from section?");
  if (!confirmed) {
    return;
  }

  const result = await callApi(
    "/api/builder/menus/" + encodeURIComponent(activeMenuId) + "/rows/" + encodeURIComponent(detailIdValue),
    { method: "DELETE" },
  );
  if (!result || !result.data || !result.data.ok) {
    if (!config.quiet) {
      showText("menuSectionsOut", "Could not remove dish.");
    }
    return;
  }
  if (!config.quiet) {
    showText("menuSectionsOut", "Dish removed.");
  }
  if (!config.skipRefresh) {
    await refreshRows();
  }
}

async function renameSection(oldName) {
  const oldValue = normalize(oldName);
  if (!oldValue) {
    return;
  }
  const nextValue = normalize(window.prompt("Rename section", oldValue));
  if (!nextValue || normalizeLower(nextValue) === normalizeLower(oldValue)) {
    return;
  }

  const rowsInSection = currentRows.filter((row) => normalizeLower(row.day) === normalizeLower(oldValue));
  if (rowsInSection.length === 0) {
    const draftIndex = findDraftIndexByName(oldValue);
    if (draftIndex >= 0) {
      sectionDrafts[draftIndex].name = nextValue;
    }
    renderSections();
    return;
  }

  showLoading("menuSectionsOut");
  for (const row of rowsInSection) {
    const result = await callApi(
      "/api/builder/menus/" + encodeURIComponent(activeMenuId) + "/rows/" + encodeURIComponent(String(row.menu_detail_id || "")),
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: {
          day: nextValue,
          meal_slot: String(row.meal_slot || DEFAULT_MEAL_SLOT),
          composition_id: String(row.composition_id || ""),
          note: String(row.note || ""),
          sort_order: Number(row.sort_order || 0),
        },
      },
    );
    if (!result || !result.data || !result.data.ok) {
      showText("menuSectionsOut", "Could not rename section.");
      return;
    }
  }

  const draftIndex = findDraftIndexByName(oldValue);
  if (draftIndex >= 0) {
    sectionDrafts[draftIndex].name = nextValue;
  }
  showText("menuSectionsOut", "Section renamed.");
  await refreshRows();
}

async function removeSection(sectionName) {
  const sectionValue = normalize(sectionName);
  if (!sectionValue) {
    return;
  }
  const confirmed = window.confirm("Remove this section and all its dishes?");
  if (!confirmed) {
    return;
  }

  const rowsInSection = currentRows.filter((row) => normalizeLower(row.day) === normalizeLower(sectionValue));
  if (rowsInSection.length === 0) {
    sectionDrafts = sectionDrafts.filter((item) => normalizeLower(item.name) !== normalizeLower(sectionValue));
    renderSections();
    return;
  }

  showLoading("menuSectionsOut");
  for (const row of rowsInSection) {
    const result = await callApi(
      "/api/builder/menus/" + encodeURIComponent(activeMenuId) + "/rows/" + encodeURIComponent(String(row.menu_detail_id || "")),
      { method: "DELETE" },
    );
    if (!result || !result.data || !result.data.ok) {
      showText("menuSectionsOut", "Could not remove section.");
      return;
    }
  }

  sectionDrafts = sectionDrafts.filter((item) => normalizeLower(item.name) !== normalizeLower(sectionValue));
  showText("menuSectionsOut", "Section removed.");
  await refreshRows();
}

function addSlotToSection(sectionName) {
  const sectionValue = normalize(sectionName);
  if (!sectionValue) {
    return;
  }
  const draft = ensureDraftSection(sectionValue);
  if (!draft) {
    return;
  }
  draft.slotLabels.push(defaultSlotLabel(draft.slotLabels.length));
  renderSections();
  showText("menuSectionsOut", "Slot added.");
}

function renameSlot(sectionName, slotIndex) {
  const sectionValue = normalize(sectionName);
  if (!sectionValue) {
    return;
  }
  const draft = ensureDraftSection(sectionValue);
  if (!draft) {
    return;
  }
  ensureSlotLabel(sectionValue, slotIndex);
  const currentLabel = draft.slotLabels[slotIndex] || defaultSlotLabel(slotIndex);
  const next = normalize(window.prompt("Rename slot", currentLabel));
  if (!next || normalizeLower(next) === normalizeLower(currentLabel)) {
    return;
  }
  setSlotLabel(sectionValue, slotIndex, next);
  renderSections();
  showText("menuSectionsOut", "Slot renamed.");
}

async function removeSlot(sectionName, slotIndex) {
  const sectionValue = normalize(sectionName);
  if (!sectionValue) {
    return;
  }

  const confirmed = window.confirm("Remove this slot? Assigned dish will also be removed.");
  if (!confirmed) {
    return;
  }

  const row = getRowForSectionSlot(sectionValue, slotIndex);
  if (row) {
    await removeDish(row.menu_detail_id, { quiet: true, skipRefresh: true, confirm: false });
  }

  removeSlotLabel(sectionValue, slotIndex);

  try {
    await refreshRows();
    await resequenceSectionRows(sectionValue);
    await refreshRows();
  } catch (_err) {
    showText("menuSectionsOut", "Could not re-order slots after removal.");
    return;
  }

  showText("menuSectionsOut", "Slot removed.");
}

async function addFreeTextDish(sectionName, slotIndex) {
  if (!activeMenuId) {
    showText("menuSectionsOut", "Create or open a menu first.");
    return;
  }

  const name = normalize(window.prompt("Type new dish name", ""));
  if (!name) {
    return;
  }

  showLoading("menuSectionsOut");
  const created = await callApi("/api/builder/compositions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: { composition_name: name },
  });

  if (!created || !created.data || !created.data.ok || !created.data.composition) {
    showText("menuSectionsOut", "Could not create dish from text.");
    return;
  }

  const composition = created.data.composition;
  const compositionId = normalize(composition.composition_id);
  if (!compositionId) {
    showText("menuSectionsOut", "Dish created without id.");
    return;
  }

  allDishes.unshift({
    composition_id: compositionId,
    composition_name: normalize(composition.composition_name) || compositionId,
  });

  const attached = await attachCompositionToSlot(sectionName, slotIndex, compositionId);
  if (!attached || !attached.ok) {
    showText("menuSectionsOut", "Dish was created but could not be attached.");
    return;
  }

  await refreshRows();
  showText("menuSectionsOut", "Dish created and attached.");
}

async function refreshRows() {
  if (!activeMenuId) {
    currentRows = [];
    renderSections();
    return;
  }

  const result = await callApi(
    "/api/builder/menus/" + encodeURIComponent(activeMenuId) + "/rows",
    { method: "GET" },
  );

  if (!result || !result.data || !result.data.ok) {
    showText("menuSectionsOut", "Could not load sections.");
    return;
  }

  currentRows = Array.isArray(result.data.rows) ? result.data.rows : [];
  syncDraftsWithRows(currentRows);
  renderSections();
}

async function loadDishes() {
  const result = await callApi("/api/builder/library", { method: "GET" });
  allDishes = result && result.data && Array.isArray(result.data.compositions)
    ? result.data.compositions
    : [];
}

function renderMenuLibrary(menus) {
  const host = document.getElementById("menuLibraryList");
  if (!host) {
    return;
  }
  host.innerHTML = "";

  const items = Array.isArray(menus) ? menus : [];
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "menu-empty";
    empty.textContent = "No menus yet.";
    host.appendChild(empty);
    return;
  }

  for (const menu of items) {
    const row = document.createElement("div");
    row.className = "menu-library-item";

    const left = document.createElement("div");
    const name = document.createElement("div");
    name.textContent = String(menu.title || menu.menu_id || "");
    const meta = document.createElement("div");
    meta.className = "menu-library-item-meta";
    meta.textContent = "menu_id: " + String(menu.menu_id || "") + " | week_key: " + String(menu.week_key || "");
    left.appendChild(name);
    left.appendChild(meta);

    const openBtn = document.createElement("button");
    openBtn.type = "button";
    openBtn.textContent = "Open";
    openBtn.addEventListener("click", async () => {
      setActiveMenu(menu);
      showText("menuLibraryOut", "Menu opened.");
      await refreshRows();
    });

    const outputBtn = document.createElement("button");
    outputBtn.type = "button";
    outputBtn.textContent = "View/Print";
    outputBtn.addEventListener("click", () => {
      const id = String(menu.menu_id || "");
      if (!id) {
        return;
      }
      window.location.href = "/menu-output-v1?menu_id=" + encodeURIComponent(id);
    });

    const actionWrap = document.createElement("div");
    actionWrap.className = "menu-inline";
    actionWrap.appendChild(openBtn);
    actionWrap.appendChild(outputBtn);

    row.appendChild(left);
    row.appendChild(actionWrap);
    host.appendChild(row);
  }
}

async function refreshMenuLibrary() {
  showLoading("menuLibraryOut");
  const result = await callApi("/api/builder/menus", { method: "GET" });
  if (!result || !result.data || !result.data.ok) {
    showText("menuLibraryOut", "Could not load menu library.");
    return;
  }
  renderMenuLibrary(result.data.menus);
  showText("menuLibraryOut", "Menu library updated.");
}

async function createMenu() {
  const titleInput = document.getElementById("menuTitle");
  const title = titleInput ? normalize(titleInput.value) : "";
  if (!title) {
    showText("createMenuOut", "Menu name is required.");
    return;
  }

  showLoading("createMenuOut");
  const result = await callApi("/api/builder/menus", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: {
      title,
      site_id: DEFAULT_SITE_ID,
      week_key: DEFAULT_WEEK_KEY,
    },
  });

  if (!result || !result.data || !result.data.ok) {
    showText("createMenuOut", "Could not create menu.");
    return;
  }

  setActiveMenu(result.data.menu || {});
  sectionDrafts = [makeSectionDraft("Section 1", [defaultSlotLabel(0)])];
  showText("createMenuOut", "Menu created and opened.");
  showText("menuTemplateOut", "Apply template to generate full structure quickly.");
  await refreshRows();
  await refreshMenuLibrary();
}

function addSectionDraft() {
  const input = document.getElementById("newSectionName");
  const name = input ? normalize(input.value) : "";
  if (!name) {
    showText("menuSectionsOut", "Section name is required.");
    return;
  }
  if (!activeMenuId) {
    showText("menuSectionsOut", "Create or open a menu first.");
    return;
  }

  const existsInRows = currentRows.some((row) => normalizeLower(row.day) === normalizeLower(name));
  const existsInDrafts = sectionDrafts.some((section) => normalizeLower(section.name) === normalizeLower(name));
  if (existsInRows || existsInDrafts) {
    showText("menuSectionsOut", "Section already exists.");
    return;
  }

  sectionDrafts.push(makeSectionDraft(name, [defaultSlotLabel(0)]));
  if (input) {
    input.value = "";
  }
  renderSections();
  showText("menuSectionsOut", "Section added. Add dishes to persist it.");
}

function generateTemplateStructure() {
  if (!activeMenuId) {
    showText("menuTemplateOut", "Create or open a menu first.");
    return;
  }

  const typeEl = document.getElementById("menuTemplateType");
  const sectionCountEl = document.getElementById("menuTemplateSectionCount");
  const slotCountEl = document.getElementById("menuTemplateSlotCount");

  const menuType = typeEl ? normalize(typeEl.value) : "free_menu";
  const sectionCount = Math.max(1, Math.min(30, Number(sectionCountEl && sectionCountEl.value) || 1));
  const slotCount = Math.max(1, Math.min(20, Number(slotCountEl && slotCountEl.value) || 1));

  const nextDrafts = [];
  for (let i = 0; i < sectionCount; i += 1) {
    const slotLabels = [];
    for (let j = 0; j < slotCount; j += 1) {
      slotLabels.push(defaultSlotLabel(j));
    }
    nextDrafts.push(makeSectionDraft(defaultSectionLabel(menuType, i), slotLabels));
  }

  sectionDrafts = nextDrafts;
  renderSections();
  showText(
    "menuTemplateOut",
    "Template generated: " + String(sectionCount) + " sections with " + String(slotCount) + " slots each.",
  );
  showText("menuSectionsOut", "Structure generated. Add dishes from library or type new dishes directly.");
}

function bindHandlers() {
  const btnNewMenu = document.getElementById("btnNewMenu");
  const btnCreateMenu = document.getElementById("btnCreateMenu");
  const btnAddSection = document.getElementById("btnAddSection");
  const btnRefreshSections = document.getElementById("btnRefreshSections");
  const btnRefreshMenuLibrary = document.getElementById("btnRefreshMenuLibrary");
  const btnApplyTemplateBuilder = document.getElementById("btnApplyTemplateBuilder");
  const dishPickerClose = document.getElementById("dishPickerClose");
  const dishPickerSearch = document.getElementById("dishPickerSearch");

  if (btnNewMenu) {
    btnNewMenu.addEventListener("click", () => {
      setActiveMenu({ menu_id: "", title: "" });
      currentRows = [];
      sectionDrafts = [];
      showText("menuTemplateOut", "");
      renderSections();
      showText("createMenuOut", "Enter a menu name and save.");
    });
  }

  if (btnCreateMenu) {
    btnCreateMenu.addEventListener("click", async () => {
      await createMenu();
    });
  }

  if (btnAddSection) {
    btnAddSection.addEventListener("click", () => {
      addSectionDraft();
    });
  }

  if (btnRefreshSections) {
    btnRefreshSections.addEventListener("click", async () => {
      await refreshRows();
    });
  }

  if (btnRefreshMenuLibrary) {
    btnRefreshMenuLibrary.addEventListener("click", async () => {
      await refreshMenuLibrary();
    });
  }

  if (btnApplyTemplateBuilder) {
    btnApplyTemplateBuilder.addEventListener("click", () => {
      generateTemplateStructure();
    });
  }

  if (dishPickerClose) {
    dishPickerClose.addEventListener("click", () => {
      closeModal("dishPickerModal");
    });
  }

  if (dishPickerSearch) {
    dishPickerSearch.addEventListener("input", () => {
      renderDishPicker();
    });
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  bindHandlers();
  await loadDishes();
  await refreshMenuLibrary();
  renderSections();
});
