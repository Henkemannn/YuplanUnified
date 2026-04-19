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
    "Imported: " +
    String(summary.imported_count || 0) +
    " | Created: " +
    String(summary.created_count || 0) +
    " | Reused: " +
    String(summary.reused_count || 0);
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
    badge.textContent = via === "created" ? "Created" : "Reused";

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

let pendingFileImportLines = [];

function setFileImportStatus(message, isError) {
  const status = document.getElementById("importFileStatus");
  if (!status) {
    return;
  }
  status.textContent = String(message || "");
  status.className = isError ? "import-warning-block" : "";
}

function renderFileImportPreview(result) {
  const list = document.getElementById("importFilePreviewList");
  const ignoredList = document.getElementById("importFileIgnoredList");
  const confirmBtn = document.getElementById("btnImportFileConfirm");
  if (list) {
    list.innerHTML = "";
  }
  if (ignoredList) {
    ignoredList.innerHTML = "";
  }

  pendingFileImportLines = [];
  if (confirmBtn) {
    confirmBtn.disabled = true;
  }

  const data = (result && result.data) || {};
  const preview = data.preview || {};
  const lines = Array.isArray(preview.importable_lines)
    ? preview.importable_lines
    : (Array.isArray(preview.lines) ? preview.lines : []);
  const ignored = Array.isArray(preview.ignored_lines) ? preview.ignored_lines : [];
  if (!result || result.status >= 400 || lines.length === 0) {
    setFileImportStatus(String(data.message || data.error || "Unable to preview file"), true);
    return;
  }

  pendingFileImportLines = lines;
  if (confirmBtn) {
    confirmBtn.disabled = false;
  }

  if (list) {
    for (const line of lines) {
      const item = document.createElement("li");
      item.textContent = String(line || "");
      list.appendChild(item);
    }
  }

  if (ignoredList) {
    for (const itemData of ignored) {
      const item = document.createElement("li");
      const text = String(itemData.normalized_text || itemData.raw_text || "");
      const reason = String(itemData.reason || "ignored_noise");
      item.textContent = text + " (" + reason + ")";
      ignoredList.appendChild(item);
    }
  }

  setFileImportStatus(
    "Preview ready: " +
      String(preview.line_count || lines.length) +
      " importable lines, " +
      String(ignored.length) +
      " ignored from " +
      String(preview.file_type || "file"),
    false,
  );
}

async function loadAllCompositions() {
  return callApi("/api/builder/compositions", { method: "GET" });
}

function renderLibrary(result) {
  const componentsList = document.getElementById("libraryComponentsList");
  const compositionsList = document.getElementById("libraryCompositionsList");
  if (!componentsList || !compositionsList) {
    return;
  }

  componentsList.innerHTML = "";
  compositionsList.innerHTML = "";

  const data = (result && result.data) || {};
  const components = Array.isArray(data.components) ? data.components : [];
  const compositions = Array.isArray(data.compositions) ? data.compositions : [];

  if (components.length === 0) {
    const li = document.createElement("li");
    li.className = "library-empty";
    li.textContent = "No components yet";
    componentsList.appendChild(li);
  } else {
    for (const item of components) {
      const li = document.createElement("li");
      li.className = "library-item";
      li.textContent = String(item.component_name || item.component_id || "");
      componentsList.appendChild(li);
    }
  }

  if (compositions.length === 0) {
    const li = document.createElement("li");
    li.className = "library-empty";
    li.textContent = "No dishes yet";
    compositionsList.appendChild(li);
  } else {
    for (const item of compositions) {
      const li = document.createElement("li");
      li.className = "library-item";

      const name = document.createElement("span");
      name.textContent = String(item.composition_name || item.composition_id || "");

      const open = document.createElement("button");
      open.className = "library-open-btn";
      open.type = "button";
      open.textContent = "Open";
      open.addEventListener("click", async () => {
        const all = await loadAllCompositions();
        const list = (all.data && all.data.compositions) || [];
        const full = list.find(
          (candidate) =>
            String(candidate.composition_id || "") === String(item.composition_id || ""),
        );
        if (full) {
          openBuilderModalForComposition(full);
        }
      });

      li.appendChild(name);
      li.appendChild(open);
      compositionsList.appendChild(li);
    }
  }
}

async function loadLibrary() {
  showLoading("libraryOut");
  const result = await callApi("/api/builder/library", { method: "GET" });
  renderLibrary(result);
  showJson("libraryOut", result);
}

let currentBuilderComposition = null;
let reusableComponentsCache = [];

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
}

function renderBuilderPanel(composition) {
  const title = document.getElementById("builderCompositionTitle");
  const list = document.getElementById("builderComponentsList");

  if (!title || !list || !composition) {
    return;
  }

  currentBuilderComposition = composition;
  title.textContent = "Dish: " + String(composition.composition_name || "");
  list.innerHTML = "";

  const components = Array.isArray(composition.components) ? composition.components : [];
  if (components.length === 0) {
    const li = document.createElement("li");
    li.textContent = "No parts added yet";
    list.appendChild(li);
    return;
  }

  for (const component of components) {
    const li = document.createElement("li");
    const row = document.createElement("div");
    row.className = "component-row";

    const name = document.createElement("span");
    name.textContent = String(component.component_name || component.component_id || "");

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
    right.appendChild(rename);
    right.appendChild(remove);

    row.appendChild(name);
    row.appendChild(right);
    li.appendChild(row);
    list.appendChild(li);
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
  const newComponentInput = document.getElementById("newComponentName");
  const importFilePreviewBtn = document.getElementById("btnImportFilePreview");
  const importFileConfirmBtn = document.getElementById("btnImportFileConfirm");

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
        setFileImportStatus("Choose a .txt or .csv file first", true);
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
      if (!Array.isArray(pendingFileImportLines) || pendingFileImportLines.length === 0) {
        setFileImportStatus("No preview lines available. Run preview first.", true);
        return;
      }

      showLoading("importOut");
      setFileImportStatus("Importing previewed lines...", false);
      try {
        const result = await callApi("/api/builder/import/file/confirm", {
          method: "POST",
          body: { lines: pendingFileImportLines },
        });
        renderImportSummary(result);
        showJson("importOut", result);
        if (result && result.status < 400) {
          pendingFileImportLines = [];
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

  if (resolveCancelBtn) {
    resolveCancelBtn.addEventListener("click", () => {
      closeResolveModal();
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

  if (addComponentBtn) {
    addComponentBtn.addEventListener("click", async () => {
      if (!currentBuilderComposition || !currentBuilderComposition.composition_id) {
        showJson("builderOut", { status: 0, data: { ok: false, error: "no_composition_selected" } });
        return;
      }

      const newComponentNameEl = document.getElementById("newComponentName");
      const component_name = newComponentNameEl ? String(newComponentNameEl.value || "").trim() : "";
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
            body: { component_name },
          },
        );
        showJson("builderOut", result);
        if (result && result.data && result.data.ok && result.data.composition) {
          renderBuilderPanel(result.data.composition);
          if (newComponentNameEl) {
            newComponentNameEl.value = "";
          }
        }
      } catch (error) {
        showJson("builderOut", { status: 0, data: { ok: false, error: String(error.message || error) } });
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
