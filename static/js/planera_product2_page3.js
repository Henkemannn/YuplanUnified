document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("#yp-product-app");
  if (!root) {
    return;
  }

  const topTabs = Array.from(root.querySelectorAll("[data-page3-view-link]"));
  const specialTabs = Array.from(root.querySelectorAll("[data-page3-special-view-link]"));
  const panels = new Map(Array.from(root.querySelectorAll("[data-page3-panel]"), (panel) => [panel.getAttribute("data-page3-panel"), panel]));
  const specialPanels = new Map(Array.from(root.querySelectorAll("[data-page3-special-view-panel]"), (panel) => [panel.getAttribute("data-page3-special-view-panel"), panel]));

  const readStateFromUrl = () => {
    const params = new URLSearchParams(window.location.search);
    const view = ["overview", "normal", "special"].includes(params.get("view") || "") ? params.get("view") : "overview";
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

  const showState = ({ view, specialView }, options = {}) => {
    const { updateHistory = false, replaceHistory = false } = options;
    const resolvedSpecialView = view === "special" ? specialView : lastSpecialView;

    panels.forEach((panel, panelView) => {
      panel.hidden = panelView !== view;
    });

    setActiveLink(topTabs, (link) => link.getAttribute("data-page3-view") === view);

    if (specialPanels.size > 0) {
      specialPanels.forEach((panel, panelView) => {
        panel.hidden = view !== "special" || panelView !== resolvedSpecialView;
      });
      setActiveLink(specialTabs, (link) => view === "special" && link.getAttribute("data-page3-special-view") === resolvedSpecialView);
    }

    if (view === "special") {
      lastSpecialView = resolvedSpecialView;
    }

    if (updateHistory) {
      updateUrl({ view, specialView: resolvedSpecialView }, replaceHistory);
    }
  };

  const initial = readStateFromUrl();
  showState(initial, { updateHistory: false });

  topTabs.forEach((link) => {
    link.addEventListener("click", (event) => {
      const view = link.getAttribute("data-page3-view");
      if (!view) {
        return;
      }
      event.preventDefault();
      const specialView = view === "special" ? lastSpecialView : lastSpecialView;
      showState({ view, specialView }, { updateHistory: true });
    });
  });

  specialTabs.forEach((link) => {
    link.addEventListener("click", (event) => {
      const specialView = link.getAttribute("data-page3-special-view");
      if (!specialView) {
        return;
      }
      event.preventDefault();
      showState({ view: "special", specialView }, { updateHistory: true });
    });
  });

  window.addEventListener("popstate", () => {
    showState(readStateFromUrl(), { updateHistory: false });
  });

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
  const isoYear = Number.parseInt(root.getAttribute("data-page3-year") || "0", 10);
  const isoWeek = Number.parseInt(root.getAttribute("data-page3-week") || "0", 10);

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