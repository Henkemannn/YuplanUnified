function showText(targetId, text) {
  const el = document.getElementById(targetId);
  if (!el) {
    return;
  }
  el.textContent = String(text || "");
}

function showLoading(targetId) {
  showText(targetId, "Working...");
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
let activeDishFilter = "all";

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

const DISH_FILTERS = [
  { key: "all", label: "Alla", terms: [] },
  { key: "fish", label: "Fisk", terms: ["fisk", "fish"] },
  { key: "meat", label: "Kött", terms: ["kött", "kott", "meat", "beef", "pork"] },
  { key: "dessert", label: "Dessert", terms: ["dessert"] },
  { key: "vegetarian", label: "Vegetariskt", terms: ["veget", "veg", "vegetar", "vegetarian"] },
  { key: "soup", label: "Soppa", terms: ["soppa", "soup"] },
];

function uniqueStrings(values) {
  const output = [];
  const seen = new Set();
  for (const value of values || []) {
    const text = dishValueText(value);
    if (!text) {
      continue;
    }
    const key = normalizeLower(text);
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    output.push(text);
  }
  return output;
}

function dishValueText(value) {
  if (value && typeof value === "object") {
    return normalize(value.name || value.label || value.text || value.title || value.value || "");
  }
  return normalize(value);
}

function dishMetadataItems(dish) {
  const items = [];
  const tags = Array.isArray(dish && dish.tags) ? dish.tags : [];
  const categories = Array.isArray(dish && dish.categories) ? dish.categories : [];
  const componentCategories = Array.isArray(dish && dish.component_categories) ? dish.component_categories : [];

  if (dish && dish.library_group) {
    items.push(dish.library_group);
  }
  if (dish && dish.category) {
    items.push(dish.category);
  }
  items.push(...tags);
  items.push(...categories);
  items.push(...componentCategories);
  return uniqueStrings(items).slice(0, 4);
}

function dishSearchText(dish) {
  const fields = [
    dishValueText(dish && dish.composition_id),
    dishValueText(dish && dish.composition_name),
    dishValueText(dish && dish.library_group),
    dishValueText(dish && dish.category),
  ];
  const tags = Array.isArray(dish && dish.tags) ? dish.tags : [];
  const categories = Array.isArray(dish && dish.categories) ? dish.categories : [];
  const componentCategories = Array.isArray(dish && dish.component_categories) ? dish.component_categories : [];
  fields.push(...tags, ...categories, ...componentCategories);
  return normalizeLower(fields.join(" "));
}

function dishMatchesFilter(dish, filterKey) {
  const filter = DISH_FILTERS.find((item) => item.key === filterKey) || DISH_FILTERS[0];
  if (!filter || filter.key === "all") {
    return true;
  }
  const text = dishSearchText(dish);
  return filter.terms.some((term) => text.includes(normalizeLower(term)));
}

function renderDishFilters() {
  const host = document.getElementById("dishBrowserFilters");
  if (!host) {
    return;
  }

  host.innerHTML = "";
  const filters = DISH_FILTERS.filter((filter) => {
    if (filter.key === "all") {
      return true;
    }
    return Array.isArray(allDishes) && allDishes.some((dish) => dishMatchesFilter(dish, filter.key));
  });

  if (!filters.some((filter) => filter.key === activeDishFilter)) {
    activeDishFilter = "all";
  }

  for (const filter of filters) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "menu-filter-chip" + (filter.key === activeDishFilter ? " is-active" : "");
    button.textContent = filter.label;
    button.setAttribute("aria-pressed", String(filter.key === activeDishFilter));
    button.addEventListener("click", () => {
      activeDishFilter = filter.key;
      renderDishFilters();
      renderDishBrowser();
    });
    host.appendChild(button);
  }
}

function setMenuSaveStatus(message) {
  showText("menuSaveStatus", message || "Menyn uppdaterad.");
}

function updateMenuDocumentTitle() {
  const title = document.getElementById("menuDocumentTitle");
  if (!title) {
    return;
  }
  title.textContent = activeMenuId ? (activeMenuTitle || "Namnlös meny") : "Bygg meny";
}

function setActiveMenu(menu) {
  activeMenuId = String((menu && menu.menu_id) || "");
  activeMenuTitle = String((menu && menu.title) || "");
  const meta = document.getElementById("activeMenuMeta");
  const saveStatus = document.getElementById("menuSaveStatus");
  const viewPrintBtn = document.getElementById("btnViewPrintActive");
  const startWrap = document.getElementById("menuStartWrap");
  updateMenuDocumentTitle();

  if (viewPrintBtn) {
    viewPrintBtn.disabled = !activeMenuId;
  }
  if (startWrap) {
    if (activeMenuId) {
      startWrap.classList.add("hidden");
    } else {
      startWrap.classList.remove("hidden");
    }
  }

  if (!meta) {
    return;
  }
  if (!activeMenuId) {
    if (saveStatus) {
      saveStatus.textContent = "Öppna en meny för att fortsätta.";
    }
    meta.textContent = "Öppna en meny för att fortsätta.";
    return;
  }
  if (saveStatus) {
    saveStatus.textContent = "Menyn uppdaterad.";
  }
  meta.textContent = "Aktiv meny: " + (activeMenuTitle || "Namnlös meny");
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
      throw new Error("Kunde inte ordna om sektionsrader.");
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
    empty.textContent = "Lägg till en sektion för att börja bygga menyn.";
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
    addDishBtn.className = "menu-section-action-btn";
    addDishBtn.textContent = "Lägg till rätt";
    addDishBtn.addEventListener("click", () => {
      openDishPicker(section.name, nextEmptySlotIndex(section));
    });

    const renameBtn = document.createElement("button");
    renameBtn.type = "button";
    renameBtn.className = "menu-section-action-btn";
    renameBtn.textContent = "Byt namn";
    renameBtn.addEventListener("click", async () => {
      await renameSection(section.name);
    });

    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "menu-section-action-btn";
    removeBtn.textContent = "Ta bort";
    removeBtn.addEventListener("click", async () => {
      await removeSection(section.name);
    });

    actions.appendChild(addDishBtn);
    actions.appendChild(renameBtn);
    actions.appendChild(removeBtn);

    header.appendChild(title);
    header.appendChild(actions);
    block.appendChild(header);

    const list = document.createElement("div");
    list.className = "menu-dish-list";

    for (const slot of section.slots) {
      if (!slot.row) {
        continue;
      }

      const dishRow = document.createElement("div");
      dishRow.className = "menu-dish-row";

      const left = document.createElement("div");
      const label = document.createElement("div");
      label.className = "menu-dish-label";
      label.textContent = String(slot.row.composition_name || slot.row.composition_id || "Rätt");

      const meta = document.createElement("div");
      meta.className = "menu-dish-meta";
      meta.textContent = "";

      left.appendChild(label);
      left.appendChild(meta);
      dishRow.appendChild(left);

      const removeDishBtn = document.createElement("button");
      removeDishBtn.type = "button";
      removeDishBtn.textContent = "×";
      removeDishBtn.setAttribute("aria-label", "Ta bort rätt");
      removeDishBtn.title = "Ta bort rätt";
      removeDishBtn.className = "menu-row-remove-btn menu-dish-remove";
      removeDishBtn.addEventListener("click", async () => {
        await removeDish(slot.row.menu_detail_id);
      });
      dishRow.appendChild(removeDishBtn);

      list.appendChild(dishRow);
    }

    if (list.childElementCount === 0) {
      const empty = document.createElement("div");
      empty.className = "menu-empty";
      empty.textContent = "Ingen rätt ännu. Välj rätt för att lägga till.";
      block.appendChild(empty);
    } else {
      block.appendChild(list);
    }
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
  const filterKey = normalizeLower(activeDishFilter) || "all";
  return allDishes.filter((item) => {
    if (!dishMatchesFilter(item, filterKey)) {
      return false;
    }
    if (!q) {
      return true;
    }
    return dishSearchText(item).includes(q);
  });
}

function renderDishList(host, query, options) {
  if (!host) {
    return;
  }

  const allowAttach = Boolean(options && options.allowAttach);
  host.innerHTML = "";
  const filtered = filterDishes(query);
  if (filtered.length === 0) {
    const empty = document.createElement("div");
    empty.className = "menu-empty";
    empty.textContent = "Inga rätter matchar filtret.";
    host.appendChild(empty);
    return;
  }

  for (const dish of filtered) {
    const pill = document.createElement("button");
    pill.className = allowAttach ? "menu-dish-picker-pill menu-dish-picker-pill--picker" : "menu-dish-picker-pill menu-browser-pill";
    pill.type = "button";
    const fullName = String(dish.composition_name || dish.composition_id || "");
    pill.title = fullName;
    if (allowAttach) {
      pill.addEventListener("click", async () => {
        await attachDishToSection(String(dish.composition_id || ""));
      });
    } else {
      pill.addEventListener("click", async () => {
        if (!pickerOpenSection) {
          showText("menuSectionsOut", "Välj Lägg till rätt i en sektion först.");
          return;
        }
        await attachDishToSection(String(dish.composition_id || ""));
      });
    }

    const main = document.createElement("div");
    main.className = "menu-dish-picker-pill-main";

    const name = document.createElement("div");
    name.className = "menu-dish-picker-name";
    name.textContent = fullName;
    name.title = fullName;

    main.appendChild(name);

    const metaItems = dishMetadataItems(dish);
    if (metaItems.length > 0) {
      const chips = document.createElement("div");
      chips.className = "menu-dish-card-chips";
      for (const item of metaItems) {
        const chip = document.createElement("span");
        chip.className = "menu-dish-chip";
        chip.textContent = item;
        chips.appendChild(chip);
      }
      main.appendChild(chips);
    }

    if (allowAttach) {
      const category = document.createElement("span");
      category.className = "menu-dish-picker-category";
      category.textContent = String(dish.library_group || "");
      if (!category.textContent) {
        category.hidden = true;
      }

      pill.appendChild(main);
      pill.appendChild(category);
    } else {
      pill.appendChild(main);
    }

    host.appendChild(pill);
  }
}

function renderDishBrowser() {
  const host = document.getElementById("dishBrowserList");
  const search = document.getElementById("dishBrowserSearch");
  if (!host) {
    return;
  }

  renderDishFilters();
  const query = search ? String(search.value || "") : "";
  renderDishList(host, query, { allowAttach: false });
}

function renderDishPicker() {
  const host = document.getElementById("dishPickerList");
  const search = document.getElementById("dishPickerSearch");
  if (!host) {
    return;
  }

  const query = search ? String(search.value || "") : "";
  renderDishList(host, query, { allowAttach: true });
}

function openDishPicker(sectionName, slotIndex) {
  if (!activeMenuId) {
    showText("menuSectionsOut", "Skapa eller öppna en meny först.");
    return;
  }

  pickerOpenSection = String(sectionName || "");
  pickerOpenSlotIndex = Number.isInteger(Number(slotIndex)) ? Math.max(0, Number(slotIndex)) : null;
  const meta = document.getElementById("dishPickerSectionMeta");
  if (meta) {
    meta.textContent = "Sektion: " + pickerOpenSection;
  }
  const slotMeta = document.getElementById("dishPickerSlotMeta");
  if (slotMeta) {
    slotMeta.textContent = pickerOpenSlotIndex === null
      ? "Plats: nästa lediga"
      : "Plats: " + String(pickerOpenSlotIndex + 1);
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
    showText("dishPickerOut", "Skapa eller öppna en meny först.");
    return;
  }

  const compositionIdValue = normalize(compositionId);
  if (!compositionIdValue) {
    showText("dishPickerOut", "Välj en rätt först.");
    return;
  }

  const sectionName = normalize(pickerOpenSection);
  if (!sectionName) {
    showText("dishPickerOut", "Sektion krävs.");
    return;
  }

  const slotIndex = pickerOpenSlotIndex === null
    ? currentRows.filter((row) => normalizeLower(row.day) === normalizeLower(sectionName)).length
    : pickerOpenSlotIndex;

  showLoading("dishPickerOut");
  const result = await attachCompositionToSlot(sectionName, slotIndex, compositionIdValue);
  if (!result || !result.ok) {
    showText("dishPickerOut", "Kunde inte lägga till rätt.");
    return;
  }

  showText("dishPickerOut", result.mode === "updated" ? "Rätt uppdaterad." : "Rätt tillagd.");
  setMenuSaveStatus("Menyn uppdaterad.");
  await refreshRows();
  closeModal("dishPickerModal");
}

async function removeDish(menuDetailId, options) {
  const config = options || {};
  const detailIdValue = normalize(menuDetailId);
  if (!activeMenuId || !detailIdValue) {
    return;
  }
  const confirmed = config.confirm === false ? true : window.confirm("Remove this dish from the section?");
  if (!confirmed) {
    return;
  }

  const result = await callApi(
    "/api/builder/menus/" + encodeURIComponent(activeMenuId) + "/rows/" + encodeURIComponent(detailIdValue),
    { method: "DELETE" },
  );
  if (!result || !result.data || !result.data.ok) {
    if (!config.quiet) {
      showText("menuSectionsOut", "Kunde inte ta bort rätt.");
    }
    return;
  }
  if (!config.quiet) {
    showText("menuSectionsOut", "Rätt borttagen.");
  }
  setMenuSaveStatus("Menyn uppdaterad.");
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
      showText("menuSectionsOut", "Kunde inte byta namn på sektionen.");
      return;
    }
  }

  const draftIndex = findDraftIndexByName(oldValue);
  if (draftIndex >= 0) {
    sectionDrafts[draftIndex].name = nextValue;
  }
  showText("menuSectionsOut", "Sektionens namn uppdaterat.");
  setMenuSaveStatus("Menyn uppdaterad.");
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
      showText("menuSectionsOut", "Kunde inte ta bort sektionen.");
      return;
    }
  }

  sectionDrafts = sectionDrafts.filter((item) => normalizeLower(item.name) !== normalizeLower(sectionValue));
  showText("menuSectionsOut", "Sektion borttagen.");
  setMenuSaveStatus("Menyn uppdaterad.");
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
  const next = normalize(window.prompt("Byt namn på plats", currentLabel));
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
    showText("menuSectionsOut", "Kunde inte ordna om platserna efter borttagning.");
    return;
  }

  showText("menuSectionsOut", "Plats borttagen.");
  setMenuSaveStatus("Menyn uppdaterad.");
}

async function addFreeTextDish(sectionName, slotIndex) {
  showText("menuSectionsOut", "Direkt skapande av rätt är avstängt i v1A.");
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
    showText("menuSectionsOut", "Kunde inte läsa in sektioner.");
    return;
  }

  currentRows = Array.isArray(result.data.rows) ? result.data.rows : [];
  syncDraftsWithRows(currentRows);
  renderSections();
  setMenuSaveStatus("Menyn uppdaterad.");
}

async function loadDishes() {
  const result = await callApi("/api/builder/library", { method: "GET" });
  allDishes = result && result.data && Array.isArray(result.data.compositions)
    ? result.data.compositions
    : [];
  renderDishFilters();
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
    empty.textContent = "Inga menyer ännu.";
    host.appendChild(empty);
    return;
  }

  for (const menu of items) {
    const row = document.createElement("div");
    const isActive = String(menu.menu_id || "") === activeMenuId;
    row.className = "menu-library-item" + (isActive ? " is-active" : "");

    const left = document.createElement("div");
    const name = document.createElement("div");
    name.textContent = String(menu.title || menu.menu_id || "");
    const meta = document.createElement("div");
    meta.className = "menu-library-item-meta";
    meta.textContent = isActive ? "Aktiv meny" : "Öppna för att fortsätta";
    left.appendChild(name);
    left.appendChild(meta);

    const openBtn = document.createElement("button");
    openBtn.type = "button";
    openBtn.className = "menu-library-action-btn";
    openBtn.textContent = "Öppna";
    openBtn.addEventListener("click", async () => {
      setActiveMenu(menu);
      showText("menuLibraryOut", "Meny öppnad.");
      await refreshRows();
    });

    const outputBtn = document.createElement("button");
    outputBtn.type = "button";
    outputBtn.className = "menu-library-action-btn";
    outputBtn.textContent = "Visa / skriv ut";
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
    showText("menuLibraryOut", "Kunde inte läsa in menyer.");
    return;
  }
  renderMenuLibrary(result.data.menus);
  showText("menuLibraryOut", "Menybibliotek uppdaterat.");
}

function selectedStartMode() {
  const modeEl = document.getElementById("menuStartMode");
  return modeEl ? normalize(modeEl.value) : "blank";
}

function updateTemplateBuilderVisibility() {
  const wrap = document.getElementById("menuTemplateWrap");
  if (!wrap) {
    return;
  }
  const show = selectedStartMode() === "template";
  if (show) {
    wrap.classList.remove("hidden");
    return;
  }
  wrap.classList.add("hidden");
}

async function createMenu() {
  const titleInput = document.getElementById("menuTitle");
  const title = titleInput ? normalize(titleInput.value) : "";
  if (!title) {
    showText("createMenuOut", "Menynamn krävs.");
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
    showText("createMenuOut", "Kunde inte skapa meny.");
    return;
  }

  setActiveMenu(result.data.menu || {});
  sectionDrafts = [];
  showText("createMenuOut", "Meny skapad.");
  setMenuSaveStatus("Menyn uppdaterad.");

  showText("menuSectionsOut", "Lägg till en sektion för att börja bygga menyn.");

  await refreshRows();
  await refreshMenuLibrary();
}

function addSectionDraft() {
  const input = document.getElementById("newSectionName");
  const name = input ? normalize(input.value) : "";
  if (!name) {
    showText("menuSectionsOut", "Sektionens namn krävs.");
    return;
  }
  if (!activeMenuId) {
    showText("menuSectionsOut", "Skapa eller öppna en meny först.");
    return;
  }

  const existsInRows = currentRows.some((row) => normalizeLower(row.day) === normalizeLower(name));
  const existsInDrafts = sectionDrafts.some((section) => normalizeLower(section.name) === normalizeLower(name));
  if (existsInRows || existsInDrafts) {
    showText("menuSectionsOut", "Sektionen finns redan.");
    return;
  }

  sectionDrafts.push(makeSectionDraft(name, [defaultSlotLabel(0)]));
  if (input) {
    input.value = "";
  }
  renderSections();
  showText("menuSectionsOut", "Sektion tillagd. Lägg till rätt för att spara.");
}

function generateTemplateStructure() {
  if (!activeMenuId) {
    showText("menuTemplateOut", "Skapa eller öppna en meny först.");
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
    "Menystruktur klar: " + String(sectionCount) + " sektioner med " + String(slotCount) + " alternativ vardera.",
  );
  showText("menuSectionsOut", "Strukturen är klar. Välj rätter från biblioteket.");
}

function bindHandlers() {
  const btnNewMenu = document.getElementById("btnNewMenu");
  const btnOpenMenuPanel = document.getElementById("btnOpenMenuPanel");
  const btnCreateMenu = document.getElementById("btnCreateMenu");
  const btnAddSection = document.getElementById("btnAddSection");
  const btnRefreshSections = document.getElementById("btnRefreshSections");
  const btnRefreshMenuLibrary = document.getElementById("btnRefreshMenuLibrary");
  const btnViewPrintActive = document.getElementById("btnViewPrintActive");
  const dishPickerClose = document.getElementById("dishPickerClose");
  const dishBrowserSearch = document.getElementById("dishBrowserSearch");
  const dishPickerSearch = document.getElementById("dishPickerSearch");

  if (btnNewMenu) {
    btnNewMenu.addEventListener("click", () => {
      setActiveMenu({ menu_id: "", title: "" });
      currentRows = [];
      sectionDrafts = [];
      showText("menuTemplateOut", "");
      renderSections();
      showText("createMenuOut", "Skriv ett namn för en ny meny.");
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

  if (dishBrowserSearch) {
    dishBrowserSearch.addEventListener("input", () => {
      renderDishBrowser();
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

  if (btnViewPrintActive) {
    btnViewPrintActive.addEventListener("click", () => {
      if (!activeMenuId) {
        return;
      }
      window.location.href = "/menu-output-v1?menu_id=" + encodeURIComponent(activeMenuId);
    });
  }

  if (btnOpenMenuPanel) {
    btnOpenMenuPanel.addEventListener("click", () => {
      const startWrap = document.getElementById("menuStartWrap");
      if (startWrap) {
        startWrap.classList.remove("hidden");
        startWrap.scrollIntoView({ block: "start", behavior: "smooth" });
      }
    });
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  bindHandlers();
  setActiveMenu({ menu_id: "", title: "" });
  await loadDishes();
  renderDishBrowser();
  await refreshMenuLibrary();
  renderSections();
});
