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
});