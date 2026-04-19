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
    .catch(() => ({ ok: false, error: "invalid_json_response", message: "Response was not valid JSON" }));
  return { status: response.status, data };
}

function parseRows(text) {
  const lines = String(text || "")
    .split(/\r?\n/)
    .map((v) => v.trim())
    .filter(Boolean);
  const rows = [];
  for (const line of lines) {
    const parts = line.split(";");
    if (parts.length < 3) {
      throw new Error("Each row must be in format day;meal_slot;raw_text");
    }
    rows.push({
      day: parts[0].trim(),
      meal_slot: parts[1].trim(),
      raw_text: parts.slice(2).join(";").trim(),
    });
  }
  return rows;
}

function formatDay(value) {
  const text = String(value || "").trim();
  if (!text) {
    return "";
  }
  return text.charAt(0).toUpperCase() + text.slice(1);
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
    "Imported: " +
    String(summary.imported_count || 0) +
    " | Resolved: " +
    String(summary.resolved_count || 0) +
    " | Unresolved: " +
    String(summary.unresolved_count || 0);
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

    const isResolved = String(row.kind || "") === "composition";
    const badge = document.createElement("span");
    badge.className = isResolved ? "status-resolved" : "status-unresolved";
    badge.textContent = isResolved ? "Resolved" : "Needs review";

    const primary = document.createElement("span");
    primary.className = "import-row-primary";
    primary.textContent =
      formatDay(row.day) +
      " " +
      String(row.meal_slot || "") +
      " - " +
      String(row.raw_text || "");

    item.appendChild(badge);
    item.appendChild(primary);

    if (isResolved && row.composition_id) {
      const secondary = document.createElement("div");
      secondary.className = "import-row-secondary";
      secondary.textContent = "composition_id: " + String(row.composition_id);
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

let currentResolve = null;
let currentBuilderComposition = null;
let currentNewItemRole = "component";

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

  console.log("REQUEST:", url, null);
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
  const payload = { component_name: newName };

  console.log("REQUEST:", url, payload);
  showLoading("builderOut");
  try {
    const result = await callApi(url, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: payload,
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

function setNewItemRole(role) {
  const roleValue = role === "connector" ? "connector" : "component";
  const componentBtn = document.getElementById("newItemRoleComponent");
  const connectorBtn = document.getElementById("newItemRoleConnector");
  currentNewItemRole = roleValue;

  if (componentBtn) {
    componentBtn.classList.toggle("role-toggle-active", roleValue === "component");
  }
  if (connectorBtn) {
    connectorBtn.classList.toggle("role-toggle-active", roleValue === "connector");
  }
}

function renderBuilderPanel(composition) {
  const title = document.getElementById("builderCompositionTitle");
  const list = document.getElementById("builderComponentsList");

  if (!title || !list || !composition) {
    return;
  }

  currentBuilderComposition = composition;
  title.textContent = "Composition: " + String(composition.composition_name || "");
  list.innerHTML = "";

  const components = Array.isArray(composition.components) ? composition.components : [];
  if (components.length === 0) {
    const li = document.createElement("li");
    li.textContent = "(empty list)";
    list.appendChild(li);
    return;
  }

  for (const component of components) {
    const li = document.createElement("li");
    const row = document.createElement("div");
    row.className = "component-row";

    const name = document.createElement("span");
    name.textContent = String(component.component_name || component.component_id || "");

    const role = document.createElement("span");
    role.className = "component-role-pill";
    role.textContent = String(component.role || "component");

    const remove = document.createElement("button");
    remove.className = "component-remove-btn";
    remove.type = "button";
    remove.textContent = "X";
    remove.title = "Remove component";
    remove.addEventListener("click", () => {
      removeComponentFromCurrentComposition(String(component.component_id || ""));
    });

    const rename = document.createElement("button");
    rename.className = "component-rename-btn";
    rename.type = "button";
    rename.textContent = "Rename";
    rename.title = "Rename component";
    rename.addEventListener("click", () => {
      renameComponentInCurrentComposition(
        String(component.component_id || ""),
        String(component.component_name || component.component_id || ""),
      );
    });

    const right = document.createElement("div");
    right.className = "component-row-right";
    right.appendChild(role);
    right.appendChild(rename);
    right.appendChild(remove);

    row.appendChild(name);
    row.appendChild(right);
    li.appendChild(row);
    list.appendChild(li);
  }
}

function setResolveCreateState() {
  const createSection = document.querySelector(".create-new-section");
  const builderSection = document.getElementById("modalBuilderSection");
  const createAndResolveBtn = document.getElementById("createAndResolve");
  const resolveCancelBtn = document.getElementById("resolveCancel");
  const newComponentName = document.getElementById("newComponentName");

  if (createSection) {
    createSection.classList.remove("hidden");
  }
  if (builderSection) {
    builderSection.classList.add("hidden");
  }
  if (createAndResolveBtn) {
    createAndResolveBtn.classList.remove("hidden");
  }
  if (resolveCancelBtn) {
    resolveCancelBtn.textContent = "Cancel";
  }
  if (newComponentName) {
    newComponentName.value = "";
  }
  setNewItemRole("component");
  showJson("builderOut", { ok: true, message: "Create and link to start building components" });
}

function setResolveBuildState(composition) {
  const createSection = document.querySelector(".create-new-section");
  const builderSection = document.getElementById("modalBuilderSection");
  const createAndResolveBtn = document.getElementById("createAndResolve");
  const resolveCancelBtn = document.getElementById("resolveCancel");

  if (createSection) {
    createSection.classList.add("hidden");
  }
  if (builderSection) {
    builderSection.classList.remove("hidden");
  }
  if (createAndResolveBtn) {
    createAndResolveBtn.classList.add("hidden");
  }
  if (resolveCancelBtn) {
    resolveCancelBtn.textContent = "Done";
  }
  renderBuilderPanel(composition);
}

function openResolveModal(detail, menuId) {
  const modal = document.getElementById("resolveModal");
  const resolveText = document.getElementById("resolveText");
  const newCompositionName = document.getElementById("newCompositionName");
  if (!modal || !resolveText) {
    return;
  }

  currentResolve = {
    menuId: String(menuId || ""),
    menuDetailId: String(detail.menu_detail_id || ""),
  };
  resolveText.textContent = String(detail.unresolved_text || "");
  if (newCompositionName) {
    newCompositionName.value = String(detail.unresolved_text || "").trim();
  }
  currentBuilderComposition = null;
  setResolveCreateState();
  modal.classList.remove("hidden");
}

function closeResolveModal() {
  const modal = document.getElementById("resolveModal");
  if (modal) {
    modal.classList.add("hidden");
  }
  currentResolve = null;
  currentBuilderComposition = null;
}

async function loadUnresolvedForMenu(menu_id) {
  const resolvedMenuId = String(menu_id || "").trim();
  const url = "/api/builder/menus/" + encodeURIComponent(resolvedMenuId) + "/unresolved";
  const list = document.getElementById("unresolvedList");
  if (list) {
    list.innerHTML = "";
  }
  console.log("REQUEST:", url, null);
  showLoading("unresolvedOut");
  const result = await callApi(url, { method: "GET" });
  const unresolved = (result.data && result.data.unresolved) || [];

  if (list) {
    for (const item of unresolved) {
      const li = document.createElement("li");
      li.className = "unresolved-item";
      li.textContent =
        (item.day || "") + " " + (item.meal_slot || "") + ": " + (item.unresolved_text || "");
      li.addEventListener("click", () => {
        openResolveModal(item, resolvedMenuId);
      });
      list.appendChild(li);
    }
  }

  showJson("unresolvedOut", result);
}

function bindBuilderHandlers() {
  const createMenuBtn = document.getElementById("btnCreateMenu");
  const importRowsBtn = document.getElementById("btnImportRows");
  const loadUnresolvedBtn = document.getElementById("btnLoadUnresolved");
  const loadCostBtn = document.getElementById("btnLoadCost");
  const createAndResolveBtn = document.getElementById("createAndResolve");
  const resolveCancelBtn = document.getElementById("resolveCancel");
  const addComponentBtn = document.getElementById("btnAddComponent");
  const newItemRoleComponentBtn = document.getElementById("newItemRoleComponent");
  const newItemRoleConnectorBtn = document.getElementById("newItemRoleConnector");

  if (newItemRoleComponentBtn) {
    newItemRoleComponentBtn.addEventListener("click", () => {
      setNewItemRole("component");
    });
  }
  if (newItemRoleConnectorBtn) {
    newItemRoleConnectorBtn.addEventListener("click", () => {
      setNewItemRole("connector");
    });
  }

  if (createMenuBtn) {
    createMenuBtn.addEventListener("click", async () => {
      console.log("create menu clicked");
      const createMenuIdEl = document.getElementById("createMenuId");
      const createSiteIdEl = document.getElementById("createSiteId");
      const createWeekKeyEl = document.getElementById("createWeekKey");
      const menu_id = createMenuIdEl ? String(createMenuIdEl.value || "").trim() : "";
      const site_id = createSiteIdEl ? String(createSiteIdEl.value || "").trim() : "";
      const week_key = createWeekKeyEl ? String(createWeekKeyEl.value || "").trim() : "";
      const url = "/api/builder/menus";
      const payload = { menu_id, site_id, week_key };

      console.log("REQUEST:", url, payload);
      showLoading("createMenuOut");
      try {
        const result = await callApi(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: payload,
        });
        showJson("createMenuOut", result);
      } catch (error) {
        showJson("createMenuOut", {
          status: 0,
          data: { ok: false, error: String(error.message || error) },
        });
      }
    });
  }

  if (importRowsBtn) {
    importRowsBtn.addEventListener("click", async () => {
      console.log("import clicked");
      const importMenuIdEl = document.getElementById("importMenuId");
      const importRowsEl = document.getElementById("importRows");
      const importSummaryView = document.getElementById("importSummaryView");
      const menu_id = importMenuIdEl ? String(importMenuIdEl.value || "").trim() : "";
      showLoading("importOut");
      if (importSummaryView) {
        importSummaryView.textContent = "Loading import summary...";
      }
      try {
        const rowsInput = importRowsEl ? String(importRowsEl.value || "") : "";
        const rows = parseRows(rowsInput);
        const url = "/api/builder/menus/" + encodeURIComponent(menu_id) + "/import";
        const payload = { rows };

        console.log("REQUEST:", url, payload);

        const result = await callApi(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: payload,
        });
        renderImportSummary(result);
        showJson("importOut", result);
      } catch (error) {
        const failResult = {
          status: 0,
          data: { ok: false, error: String(error.message || error) },
        };
        renderImportSummary(failResult);
        showJson("importOut", failResult);
      }
    });
  }

  if (loadUnresolvedBtn) {
    loadUnresolvedBtn.addEventListener("click", async () => {
      console.log("load unresolved clicked");
      const unresolvedMenuIdEl = document.getElementById("unresolvedMenuId");
      const menu_id = unresolvedMenuIdEl ? String(unresolvedMenuIdEl.value || "").trim() : "";
      try {
        await loadUnresolvedForMenu(menu_id);
      } catch (error) {
        showJson("unresolvedOut", {
          status: 0,
          data: { ok: false, error: String(error.message || error) },
        });
      }
    });
  }

  if (resolveCancelBtn) {
    resolveCancelBtn.addEventListener("click", () => {
      closeResolveModal();
    });
  }

  if (createAndResolveBtn) {
    createAndResolveBtn.addEventListener("click", async () => {
      if (!currentResolve) {
        showJson("unresolvedOut", {
          status: 0,
          data: { ok: false, error: "no_menu_detail_selected" },
        });
        return;
      }

      const newCompositionName = document.getElementById("newCompositionName");
      const composition_name = newCompositionName
        ? String(newCompositionName.value || "").trim()
        : "";

      if (!composition_name) {
        showJson("unresolvedOut", {
          status: 0,
          data: {
            ok: false,
            error: "composition_name is required",
          },
        });
        return;
      }

      const url =
        "/api/builder/menus/" +
        encodeURIComponent(currentResolve.menuId) +
        "/create-composition-from-row";
      const payload = {
        menu_detail_id: currentResolve.menuDetailId,
        composition_name,
      };
      const refreshMenuId = currentResolve.menuId;

      console.log("REQUEST:", url, payload);
      showLoading("unresolvedOut");
      try {
        const result = await callApi(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: payload,
        });
        showJson("unresolvedOut", result);

        if (result && result.data && result.data.ok && result.data.composition) {
          setResolveBuildState(result.data.composition);
        }

        await loadUnresolvedForMenu(refreshMenuId);
      } catch (error) {
        showJson("unresolvedOut", {
          status: 0,
          data: { ok: false, error: String(error.message || error) },
        });
      }
    });
  }

  if (addComponentBtn) {
    addComponentBtn.addEventListener("click", async () => {
      if (!currentBuilderComposition || !currentBuilderComposition.composition_id) {
        showJson("builderOut", {
          status: 0,
          data: { ok: false, error: "no_composition_selected" },
        });
        return;
      }

      const newComponentNameEl = document.getElementById("newComponentName");
      const component_name = newComponentNameEl
        ? String(newComponentNameEl.value || "").trim()
        : "";
      if (!component_name) {
        showJson("builderOut", {
          status: 0,
          data: { ok: false, error: "component_name is required" },
        });
        return;
      }

      const compositionId = String(currentBuilderComposition.composition_id);
      const url =
        "/api/builder/compositions/" + encodeURIComponent(compositionId) + "/components";
      const payload = {
        component_name,
        role: currentNewItemRole,
      };

      console.log("REQUEST:", url, payload);
      showLoading("builderOut");
      try {
        const result = await callApi(url, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: payload,
        });
        showJson("builderOut", result);
        if (result && result.data && result.data.ok && result.data.composition) {
          renderBuilderPanel(result.data.composition);
          if (newComponentNameEl) {
            newComponentNameEl.value = "";
          }
        }
      } catch (error) {
        showJson("builderOut", {
          status: 0,
          data: { ok: false, error: String(error.message || error) },
        });
      }
    });
  }

  if (loadCostBtn) {
    loadCostBtn.addEventListener("click", async () => {
      console.log("load cost overview clicked");
      const costMenuIdEl = document.getElementById("costMenuId");
      const costTargetPortionsEl = document.getElementById("costTargetPortions");
      const menu_id = costMenuIdEl ? String(costMenuIdEl.value || "").trim() : "";
      const target_portions = costTargetPortionsEl
        ? String(costTargetPortionsEl.value || "").trim() || "1"
        : "1";
      showLoading("costOut");
      try {
        const url =
          "/api/builder/menus/" +
          encodeURIComponent(menu_id) +
          "/cost-overview?target_portions=" +
          encodeURIComponent(target_portions);

        console.log("REQUEST:", url, null);

        const result = await callApi(url, { method: "GET" });
        showJson("costOut", result);
      } catch (error) {
        showJson("costOut", {
          status: 0,
          data: { ok: false, error: String(error.message || error) },
        });
      }
    });
  }
}

document.addEventListener("DOMContentLoaded", bindBuilderHandlers);
