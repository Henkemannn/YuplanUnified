function showText(targetId, text) {
  const el = document.getElementById(targetId);
  if (!el) {
    return;
  }
  el.textContent = String(text || "");
}

function setState(kind, message) {
  const el = document.getElementById("menuOutputState");
  if (!el) {
    return;
  }
  el.className = "menu-output-state";
  if (kind === "loading") {
    el.classList.add("is-loading");
  } else if (kind === "error") {
    el.classList.add("is-error");
  }
  el.textContent = String(message || "");
}

function updateGeneratedAtLabel() {
  const label = document.getElementById("menuOutputGeneratedAt");
  if (!label) {
    return;
  }
  const now = new Date();
  const text = now.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  label.textContent = "Generated: " + text;
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

function currentMenuIdFromQuery() {
  const params = new URLSearchParams(window.location.search || "");
  return String(params.get("menu_id") || "").trim();
}

function setMenuIdInQuery(menuId) {
  const params = new URLSearchParams(window.location.search || "");
  if (menuId) {
    params.set("menu_id", menuId);
  } else {
    params.delete("menu_id");
  }
  const next = window.location.pathname + (params.toString() ? "?" + params.toString() : "");
  window.history.replaceState({}, "", next);
}

function renderSections(rows) {
  const host = document.getElementById("menuOutputSections");
  if (!host) {
    return;
  }
  host.innerHTML = "";

  const items = Array.isArray(rows) ? rows : [];
  if (items.length === 0) {
    const empty = document.createElement("div");
    empty.className = "menu-output-empty";
    empty.textContent = "No dishes have been added to this menu yet.";
    host.appendChild(empty);
    setState("info", "This menu is ready, but it does not contain any dishes yet.");
    return;
  }

  const grouped = {};
  const order = [];

  for (const row of items) {
    const section = String(row.day || "").trim() || "Section";
    if (!grouped[section]) {
      grouped[section] = [];
      order.push(section);
    }
    grouped[section].push(row);
  }

  for (const sectionName of order) {
    const section = document.createElement("section");
    section.className = "menu-output-section";

    const title = document.createElement("h3");
    title.textContent = sectionName;
    section.appendChild(title);

    const list = document.createElement("ul");
    list.className = "menu-output-dishes";

    const rowsInSection = grouped[sectionName].slice().sort((left, right) => {
      const leftSort = Number(left.sort_order || 0);
      const rightSort = Number(right.sort_order || 0);
      if (leftSort !== rightSort) {
        return leftSort - rightSort;
      }
      return String(left.menu_detail_id || "").localeCompare(String(right.menu_detail_id || ""));
    });

    for (const row of rowsInSection) {
      const li = document.createElement("li");
      li.textContent = String(row.composition_name || row.composition_id || row.unresolved_text || "Dish");
      list.appendChild(li);
    }

    section.appendChild(list);
    host.appendChild(section);
  }

  setState("", "");
}

function fillMenuSelect(menus, selectedMenuId) {
  const select = document.getElementById("menuOutputSelect");
  if (!select) {
    return;
  }
  select.innerHTML = "";

  const list = Array.isArray(menus) ? menus : [];
  for (const menu of list) {
    const option = document.createElement("option");
    option.value = String(menu.menu_id || "");
    option.textContent = String(menu.title || menu.menu_id || "");
    if (option.value === selectedMenuId) {
      option.selected = true;
    }
    select.appendChild(option);
  }
}

async function loadMenuLibrary() {
  const result = await callApi("/api/builder/menus", { method: "GET" });
  if (!result || !result.data || !result.data.ok) {
    setState("error", "Could not load the menu library. Please retry.");
    return null;
  }
  return Array.isArray(result.data.menus) ? result.data.menus : [];
}

async function renderSelectedMenu() {
  const select = document.getElementById("menuOutputSelect");
  const menuId = select ? String(select.value || "").trim() : "";
  const titleEl = document.getElementById("menuOutputTitle");
  const metaEl = document.getElementById("menuOutputMeta");

  if (!menuId) {
    if (titleEl) {
      titleEl.textContent = "Menu output";
    }
    if (metaEl) {
      metaEl.textContent = "Choose a menu to render a clean print-ready page.";
    }
    renderSections([]);
    setState("", "Choose a menu above to view a clean printable output.");
    return;
  }

  setMenuIdInQuery(menuId);
  setState("loading", "Loading menu content...");

  const menuResult = await callApi("/api/builder/menus", { method: "GET" });
  const rowsResult = await callApi("/api/builder/menus/" + encodeURIComponent(menuId) + "/rows", { method: "GET" });

  if (!rowsResult || !rowsResult.data || !rowsResult.data.ok) {
    renderSections([]);
    setState("error", "Could not load menu rows. Try opening the menu again.");
    return;
  }

  const menus = menuResult && menuResult.data && Array.isArray(menuResult.data.menus)
    ? menuResult.data.menus
    : [];
  const menu = menus.find((item) => String(item.menu_id || "") === menuId) || null;

  if (titleEl) {
    titleEl.textContent = String((menu && menu.title) || menuId);
  }
  if (metaEl) {
    const weekKey = menu ? String(menu.week_key || "") : "";
    metaEl.textContent = weekKey
      ? "Week key: " + weekKey + " · Flexible menu structure"
      : "Flexible menu structure";
  }

  updateGeneratedAtLabel();
  renderSections(rowsResult.data.rows || []);
}

function bindHandlers() {
  const openBtn = document.getElementById("btnOpenMenuOutput");
  const printBtn = document.getElementById("btnPrintMenuOutput");
  const exportPdfBtn = document.getElementById("btnExportPdfMenuOutput");

  if (openBtn) {
    openBtn.addEventListener("click", async () => {
      await renderSelectedMenu();
    });
  }

  if (printBtn) {
    printBtn.addEventListener("click", () => {
      window.print();
    });
  }

  if (exportPdfBtn) {
    exportPdfBtn.addEventListener("click", () => {
      setState("", "Use the print dialog and choose Save as PDF.");
      window.print();
    });
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  bindHandlers();
  updateGeneratedAtLabel();
  const menus = await loadMenuLibrary();
  if (menus === null) {
    fillMenuSelect([], "");
    return;
  }
  const fromQuery = currentMenuIdFromQuery();
  const selected = fromQuery || (menus.length > 0 ? String(menus[0].menu_id || "") : "");
  fillMenuSelect(menus, selected);
  await renderSelectedMenu();
});
