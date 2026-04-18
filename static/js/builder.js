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

let currentResolve = null;

function openResolveModal(detail, menuId) {
  const modal = document.getElementById("resolveModal");
  const resolveText = document.getElementById("resolveText");
  if (!modal || !resolveText) {
    return;
  }

  currentResolve = {
    menuId: String(menuId || ""),
    menuDetailId: String(detail.menu_detail_id || ""),
  };
  resolveText.textContent = String(detail.unresolved_text || "");
  modal.classList.remove("hidden");
}

function closeResolveModal() {
  const modal = document.getElementById("resolveModal");
  if (modal) {
    modal.classList.add("hidden");
  }
  currentResolve = null;
}

async function loadCompositionOptions() {
  const select = document.getElementById("resolveCompositionSelect");
  if (!select) {
    return;
  }
  select.innerHTML = "";

  const url = "/api/builder/compositions";
  console.log("REQUEST:", url, null);
  const result = await callApi(url, { method: "GET" });
  const rows = (result.data && result.data.compositions) || [];

  if (!rows.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "No compositions available";
    select.appendChild(opt);
    return;
  }

  for (const composition of rows) {
    const opt = document.createElement("option");
    opt.value = composition.composition_id || "";
    opt.textContent =
      (composition.composition_name || composition.composition_id || "") +
      " (" +
      (composition.composition_id || "") +
      ")";
    select.appendChild(opt);
  }
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
      li.addEventListener("click", async () => {
        await loadCompositionOptions();
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
  const resolveConfirmBtn = document.getElementById("resolveConfirm");
  const resolveCancelBtn = document.getElementById("resolveCancel");

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
      const menu_id = importMenuIdEl ? String(importMenuIdEl.value || "").trim() : "";
      showLoading("importOut");
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
        showJson("importOut", result);
      } catch (error) {
        showJson("importOut", {
          status: 0,
          data: { ok: false, error: String(error.message || error) },
        });
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

  if (resolveConfirmBtn) {
    resolveConfirmBtn.addEventListener("click", async () => {
      if (!currentResolve) {
        showJson("unresolvedOut", {
          status: 0,
          data: { ok: false, error: "no_menu_detail_selected" },
        });
        return;
      }

      const select = document.getElementById("resolveCompositionSelect");
      const composition_id = select ? String(select.value || "").trim() : "";
      if (!composition_id) {
        showJson("unresolvedOut", {
          status: 0,
          data: { ok: false, error: "composition_id is required" },
        });
        return;
      }

      const url =
        "/api/builder/menus/" + encodeURIComponent(currentResolve.menuId) + "/resolve";
      const payload = {
        menu_detail_id: currentResolve.menuDetailId,
        composition_id,
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
        closeResolveModal();
        await loadUnresolvedForMenu(refreshMenuId);
      } catch (error) {
        showJson("unresolvedOut", {
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
