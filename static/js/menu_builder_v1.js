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

  const names = Object.keys(bySection).sort((a, b) => a.localeCompare(b));
  const sections = names.map((name) => {
    const items = bySection[name].slice().sort((left, right) => {
      const leftSort = Number(left.sort_order || 0);
      const rightSort = Number(right.sort_order || 0);
      if (leftSort !== rightSort) {
        return leftSort - rightSort;
      }
      return String(left.menu_detail_id || "").localeCompare(String(right.menu_detail_id || ""));
    });
    return { name, rows: items };
  });

  for (const draft of sectionDrafts) {
    const draftName = normalize(draft);
    if (!draftName) {
      continue;
    }
    if (!sections.some((item) => normalizeLower(item.name) === normalizeLower(draftName))) {
      sections.push({ name: draftName, rows: [] });
    }
  }

  return sections;
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
      openDishPicker(section.name);
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
    actions.appendChild(renameBtn);
    actions.appendChild(removeBtn);

    header.appendChild(title);
    header.appendChild(actions);
    block.appendChild(header);

    const list = document.createElement("div");
    list.className = "menu-dish-list";

    if (section.rows.length === 0) {
      const empty = document.createElement("div");
      empty.className = "menu-empty";
      empty.textContent = "No dishes in this section yet.";
      list.appendChild(empty);
    } else {
      for (const row of section.rows) {
        const item = document.createElement("div");
        item.className = "menu-dish-row";

        const left = document.createElement("div");

        const label = document.createElement("div");
        label.className = "menu-dish-label";
        label.textContent = String(row.composition_name || row.composition_id || "Dish");

        const meta = document.createElement("div");
        meta.className = "menu-dish-meta";
        meta.textContent = "dish_id: " + String(row.composition_id || "") + " | sort: " + String(row.sort_order || 0);

        left.appendChild(label);
        left.appendChild(meta);

        const removeDishBtn = document.createElement("button");
        removeDishBtn.type = "button";
        removeDishBtn.textContent = "Remove";
        removeDishBtn.addEventListener("click", async () => {
          await removeDish(row.menu_detail_id);
        });

        item.appendChild(left);
        item.appendChild(removeDishBtn);
        list.appendChild(item);
      }
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

function openDishPicker(sectionName) {
  if (!activeMenuId) {
    showText("menuSectionsOut", "Create or open a menu first.");
    return;
  }

  pickerOpenSection = String(sectionName || "");
  const meta = document.getElementById("dishPickerSectionMeta");
  if (meta) {
    meta.textContent = "Section: " + pickerOpenSection;
  }
  const search = document.getElementById("dishPickerSearch");
  if (search) {
    search.value = "";
  }
  showText("dishPickerOut", "");
  renderDishPicker();
  openModal("dishPickerModal");
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

  const sectionRows = currentRows.filter((row) => normalizeLower(row.day) === normalizeLower(sectionName));
  const sortOrder = sectionRows.length;

  showLoading("dishPickerOut");
  const result = await callApi(
    "/api/builder/menus/" + encodeURIComponent(activeMenuId) + "/rows",
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: {
        day: sectionName,
        meal_slot: DEFAULT_MEAL_SLOT,
        composition_id: compositionIdValue,
        note: "",
        sort_order: sortOrder,
      },
    },
  );

  if (!result || !result.data || !result.data.ok) {
    showText("dishPickerOut", "Could not attach dish.");
    return;
  }

  showText("dishPickerOut", "Dish attached.");
  await refreshRows();
  closeModal("dishPickerModal");
}

async function removeDish(menuDetailId) {
  const detailIdValue = normalize(menuDetailId);
  if (!activeMenuId || !detailIdValue) {
    return;
  }
  const confirmed = window.confirm("Remove this dish from section?");
  if (!confirmed) {
    return;
  }

  const result = await callApi(
    "/api/builder/menus/" + encodeURIComponent(activeMenuId) + "/rows/" + encodeURIComponent(detailIdValue),
    { method: "DELETE" },
  );
  if (!result || !result.data || !result.data.ok) {
    showText("menuSectionsOut", "Could not remove dish.");
    return;
  }
  showText("menuSectionsOut", "Dish removed.");
  await refreshRows();
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
    sectionDrafts = sectionDrafts.map((name) => (normalizeLower(name) === normalizeLower(oldValue) ? nextValue : name));
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

  sectionDrafts = sectionDrafts.map((name) => (normalizeLower(name) === normalizeLower(oldValue) ? nextValue : name));
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
    sectionDrafts = sectionDrafts.filter((name) => normalizeLower(name) !== normalizeLower(sectionValue));
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

  sectionDrafts = sectionDrafts.filter((name) => normalizeLower(name) !== normalizeLower(sectionValue));
  showText("menuSectionsOut", "Section removed.");
  await refreshRows();
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
  sectionDrafts = ["Section 1"];
  showText("createMenuOut", "Menu created and opened.");
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
  const existsInDrafts = sectionDrafts.some((section) => normalizeLower(section) === normalizeLower(name));
  if (existsInRows || existsInDrafts) {
    showText("menuSectionsOut", "Section already exists.");
    return;
  }

  sectionDrafts.push(name);
  if (input) {
    input.value = "";
  }
  renderSections();
  showText("menuSectionsOut", "Section added. Add dishes to persist it.");
}

function bindHandlers() {
  const btnNewMenu = document.getElementById("btnNewMenu");
  const btnCreateMenu = document.getElementById("btnCreateMenu");
  const btnAddSection = document.getElementById("btnAddSection");
  const btnRefreshSections = document.getElementById("btnRefreshSections");
  const btnRefreshMenuLibrary = document.getElementById("btnRefreshMenuLibrary");
  const dishPickerClose = document.getElementById("dishPickerClose");
  const dishPickerSearch = document.getElementById("dishPickerSearch");

  if (btnNewMenu) {
    btnNewMenu.addEventListener("click", () => {
      setActiveMenu({ menu_id: "", title: "" });
      currentRows = [];
      sectionDrafts = [];
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
