document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("#yp-product-app");
  if (!root) {
    return;
  }
  if (root.dataset.page3PrintSelectionInitialized === "true") {
    return;
  }
  root.dataset.page3PrintSelectionInitialized = "true";

  const topTabs = Array.from(root.querySelectorAll("[data-page3-view-link]"));
  const specialTabs = Array.from(root.querySelectorAll("[data-page3-special-view-link]"));
  const panels = new Map(Array.from(root.querySelectorAll("[data-page3-panel]"), (panel) => [panel.getAttribute("data-page3-panel"), panel]));
  const specialPanels = new Map(Array.from(root.querySelectorAll("[data-page3-special-view-panel]"), (panel) => [panel.getAttribute("data-page3-special-view-panel"), panel]));
  const printTitle = root.querySelector("[data-page3-print-title]");
  const normalSelector = root.querySelector("[data-page3-normal-selector]");
  const normalTable = root.querySelector("[data-page3-normal-table]");
  const normalColumnHeaders = Array.from(root.querySelectorAll("[data-page3-normal-table] thead th[data-page3-normal-option]"));
  const normalSingleHeadings = Array.from(root.querySelectorAll("[data-page3-normal-single-heading]"));
  const normalQuantityHeading = root.querySelector("[data-page3-normal-quantity-heading]");
  const addonFamilies = Array.from(root.querySelectorAll("[data-page3-addon-family]"));
  const addonFamilyToggles = Array.from(root.querySelectorAll("[data-page3-addon-family-toggle]"));
  const printSelectionFeedback = root.querySelector("[data-page3-print-selection-feedback]");

  const readStateFromUrl = () => {
    const params = new URLSearchParams(window.location.search);
    const view = ["overview", "normal", "special", "addons"].includes(params.get("view") || "") ? params.get("view") : "overview";
    const specialView = ["production", "department"].includes(params.get("special_view") || "") ? params.get("special_view") : "production";
    return { view, specialView };
  };

  let lastSpecialView = readStateFromUrl().specialView;

  const setActiveLink = (links, predicate) => {
    links.forEach((link) => {
      const active = Boolean(predicate(link));
      link.classList.toggle("is-active", active);
      if (active) {
        link.setAttribute("aria-current", "page");
      } else {
        link.removeAttribute("aria-current");
      }
    });
  };

  const updateUrl = ({ view, specialView }, replace = false) => {
    const url = new URL(window.location.href);
    url.searchParams.set("view", view);
    if (view === "special") {
      url.searchParams.set("special_view", specialView);
    } else {
      url.searchParams.delete("special_view");
    }
    const state = { view, specialView };
    if (replace) {
      window.history.replaceState(state, "", url);
    } else {
      window.history.pushState(state, "", url);
    }
  };

  const applyNormalSelection = () => {
    const selectedOptionId = normalSelector ? normalSelector.value : "";
    const onlyOptionId = normalColumnHeaders.length === 1
      ? normalColumnHeaders[0].getAttribute("data-page3-normal-option") || ""
      : "";
    const displayedOptionId = selectedOptionId || onlyOptionId;
    const isSingleSelection = Boolean(displayedOptionId);
    if (normalTable) {
      normalTable.classList.toggle("is-single-selection", isSingleSelection);
    }
    normalColumnHeaders.forEach((element) => {
      element.hidden = isSingleSelection;
    });
    if (normalQuantityHeading) {
      normalQuantityHeading.hidden = !isSingleSelection;
    }
    root.querySelectorAll("[data-page3-normal-option]").forEach((element) => {
      const optionId = element.getAttribute("data-page3-normal-option") || "";
      if (element.closest("thead")) {
        return;
      }
      element.hidden = Boolean(displayedOptionId && optionId !== displayedOptionId);
    });
    normalSingleHeadings.forEach((element) => {
      const optionId = element.getAttribute("data-page3-normal-single-heading") || "";
      element.hidden = !isSingleSelection || optionId !== displayedOptionId;
    });
    if (printTitle && root.getAttribute("data-page3-active-view") === "normal") {
      const selectedOption = normalSelector && normalSelector.selectedOptions[0];
      const selectedHeading = normalSingleHeadings.find((heading) => (
        heading.getAttribute("data-page3-normal-single-heading") === displayedOptionId
      ));
      const selectedTitle = selectedOptionId && selectedOption
        ? `Normalkost – ${selectedOption.textContent}`
        : selectedHeading && selectedHeading.firstElementChild
          ? selectedHeading.firstElementChild.textContent
          : "";
      printTitle.textContent = selectedTitle ? selectedTitle : "Normalkost";
    }
  };

  const selectedAddonFamilies = () => addonFamilies.filter((family) => !family.classList.contains("is-print-unselected"));
  const setPrintSelectionFeedback = (message) => {
    if (!printSelectionFeedback) {
      return;
    }
    printSelectionFeedback.textContent = message;
    printSelectionFeedback.hidden = !message;
  };
  const syncAddonToggle = (toggle, selected) => {
    const familyName = toggle.getAttribute("data-page3-addon-family-name") || "familjen";
    toggle.setAttribute("aria-pressed", String(selected));
    toggle.setAttribute("title", `${selected ? "Avmarkera" : "Välj"} ${familyName} för utskrift`);
  };
  const resetAddonPrintScope = () => {
    addonFamilies.forEach((family) => family.classList.remove("is-print-inactive"));
  };
  const applyAddonPrintScope = () => {
    const selected = selectedAddonFamilies();
    addonFamilies.forEach((family) => family.classList.toggle("is-print-inactive", !selected.includes(family)));
    return selected.length > 0;
  };
  const toggleAddonFamily = (toggle) => {
    const familyKey = toggle.getAttribute("data-page3-addon-family-toggle") || "";
    const family = addonFamilies.find((item) => item.getAttribute("data-page3-addon-family") === familyKey);
    if (!family) {
      return;
    }
    const selected = family.classList.toggle("is-print-unselected") === false;
    syncAddonToggle(toggle, selected);
    setPrintSelectionFeedback("");
  };

  addonFamilyToggles.forEach((toggle) => {
    const familyKey = toggle.getAttribute("data-page3-addon-family-toggle") || "";
    const family = addonFamilies.find((item) => item.getAttribute("data-page3-addon-family") === familyKey);
    if (family) {
      family.classList.remove("is-print-unselected");
      syncAddonToggle(toggle, true);
    }
    toggle.addEventListener("click", () => toggleAddonFamily(toggle));
  });

  const showState = ({ view, specialView }, options = {}) => {
    const { updateHistory = false, replaceHistory = false } = options;
    const resolvedSpecialView = view === "special" ? specialView : lastSpecialView;

    panels.forEach((panel, panelView) => {
      const active = panelView === view;
      panel.hidden = !active;
      panel.classList.toggle("is-print-active", active);
      panel.classList.toggle("is-print-inactive", !active);
    });

    setActiveLink(topTabs, (link) => link.getAttribute("data-page3-view") === view);

    if (specialPanels.size > 0) {
      specialPanels.forEach((panel, panelView) => {
        const active = view === "special" && panelView === resolvedSpecialView;
        panel.hidden = !active;
        panel.classList.toggle("is-print-active", active);
        panel.classList.toggle("is-print-inactive", !active);
      });
      setActiveLink(specialTabs, (link) => view === "special" && link.getAttribute("data-page3-special-view") === resolvedSpecialView);
    }

    if (view === "special") {
      lastSpecialView = resolvedSpecialView;
    }
    if (view !== "addons") {
      resetAddonPrintScope();
      setPrintSelectionFeedback("");
    }
    root.setAttribute("data-page3-active-view", view);
    root.setAttribute("data-page3-active-special-view", resolvedSpecialView);
    if (printTitle) {
      const title = view === "overview"
        ? "Översikt – Dagens produktion"
        : view === "normal"
          ? "Normalkost"
          : view === "addons"
            ? "Serveringsanpassningar"
          : resolvedSpecialView === "department"
            ? "Specialkost – Packlista"
            : "Specialkost – Produktionslista";
      printTitle.textContent = title;
    }
    applyNormalSelection();

    if (updateHistory) {
      updateUrl({ view, specialView: resolvedSpecialView }, replaceHistory);
    }
  };

  const initial = readStateFromUrl();
  showState(initial, { updateHistory: false });

  if (normalSelector) {
    normalSelector.addEventListener("change", applyNormalSelection);
  }

  window.addEventListener("popstate", () => {
    showState(readStateFromUrl(), { updateHistory: false });
  });

  window.addEventListener("beforeprint", () => {
    const state = readStateFromUrl();
    showState(state, { updateHistory: false });
    if (state.view === "addons") {
      applyAddonPrintScope();
    }
  });
  window.addEventListener("afterprint", resetAddonPrintScope);

  const completionButton = root.querySelector("[data-page3-completion-button]");
  const completionFeedback = root.querySelector("[data-page3-completion-feedback]");
  const completionDepartmentIds = (() => {
    const raw = root.getAttribute("data-page3-completion-target-departments") || "[]";
    try {
      const parsed = JSON.parse(raw);
      if (!Array.isArray(parsed)) {
        return [];
      }
      return Array.from(new Set(parsed.map((value) => String(value || "").trim()).filter(Boolean)));
    } catch (_error) {
      return [];
    }
  })();
  const siteId = (root.getAttribute("data-page3-site-id") || "").trim();
  const serviceDate = (root.getAttribute("data-page3-service-date") || "").trim();
  const meal = (root.getAttribute("data-page3-meal") || "").trim().toLowerCase();
  const optionId = (root.getAttribute("data-page3-option-id") || "").trim();
  const isoYear = Number.parseInt(root.getAttribute("data-page3-year") || "0", 10);
  const isoWeek = Number.parseInt(root.getAttribute("data-page3-week") || "0", 10);

  const printButton = root.querySelector("[data-page3-print]");
  if (printButton) {
    printButton.addEventListener("click", () => {
      if (root.getAttribute("data-page3-active-view") === "addons" && !applyAddonPrintScope()) {
        setPrintSelectionFeedback("Välj minst en familj innan utskrift.");
        return;
      }
      setPrintSelectionFeedback("");
      window.print();
    });
  }

  if (!completionButton || !completionDepartmentIds.length || !siteId || !serviceDate || !meal || !Number.isInteger(isoYear) || !Number.isInteger(isoWeek)) {
    return;
  }

  const csrfToken = (() => {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute("content")) {
      return meta.getAttribute("content");
    }
    try {
      const cookie = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrf_token="));
      return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
    } catch (_error) {
      return "";
    }
  })();

  const originalLabel = completionButton.textContent || "Markera som gjorda i veckolistan";
  const endpoint = "/api/planera/product2/production-completion";
  let inFlight = false;

  const setFeedback = (message, kind) => {
    if (!completionFeedback) {
      return;
    }
    completionFeedback.hidden = !message;
    completionFeedback.textContent = message || "";
    completionFeedback.classList.toggle("is-success", kind === "success");
    completionFeedback.classList.toggle("is-error", kind === "error");
  };

  const resetButtonState = () => {
    completionButton.disabled = false;
    completionButton.classList.remove("is-success");
    completionButton.textContent = originalLabel;
  };

  const parseResponsePayload = async (response) => {
    try {
      return await response.json();
    } catch (_error) {
      return {};
    }
  };

  const requestEtag = async (departmentId) => {
    const params = new URLSearchParams({
      department_id: departmentId,
      year: String(isoYear),
      week: String(isoWeek),
    });
    if (siteId) {
      params.set("site_id", siteId);
    }
    const response = await fetch(`/api/weekview/etag?${params.toString()}`, {
      credentials: "same-origin",
    });
    if (!response.ok) {
      throw new Error("etag_fetch_failed");
    }
    const payload = await parseResponsePayload(response);
    const etag = String(payload.etag || response.headers.get("ETag") || "").trim();
    if (!etag) {
      throw new Error("etag_missing");
    }
    return etag;
  };

  const postCompletion = async (expectedEtags) => {
    return fetch(endpoint, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
      },
      body: JSON.stringify({
        site_id: siteId,
        service_date: serviceDate,
        meal,
        ...(optionId ? { option_id: optionId } : {}),
        marked: true,
        expected_etags: expectedEtags,
      }),
    });
  };

  completionButton.addEventListener("click", async () => {
    if (inFlight || completionButton.disabled) {
      return;
    }
    inFlight = true;
    completionButton.disabled = true;
    setFeedback("Markerar i veckolistan...", null);

    try {
      const expectedEtags = {};
      await Promise.all(
        completionDepartmentIds.map(async (departmentId) => {
          expectedEtags[departmentId] = await requestEtag(departmentId);
        }),
      );

      const response = await postCompletion(expectedEtags);
      const payload = await parseResponsePayload(response);
      if (!response.ok) {
        const message = response.status === 412
          ? "Veckolistan har ändrats. Försök igen."
          : String(payload.detail || payload.message || payload.error || "Kunde inte markera i veckolistan.");
        throw new Error(message);
      }

      completionButton.classList.add("is-success");
      completionButton.textContent = "Markerat i veckolistan ✓";
      completionButton.disabled = true;
      setFeedback("Markerat i veckolistan.", "success");
    } catch (error) {
      resetButtonState();
      setFeedback(error && error.message ? error.message : "Kunde inte markera i veckolistan.", "error");
    } finally {
      inFlight = false;
    }
  });
});