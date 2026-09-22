document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("#yp-product-app");
  if (!root) {
    return;
  }

  const tabs = Array.from(root.querySelectorAll("[data-page2-option-tab]"));
  const panels = new Map(
    Array.from(root.querySelectorAll("[data-page2-option-panel]")).map((panel) => [panel.id, panel]),
  );

  if (!tabs.length || !panels.size) {
    return;
  }

  const activateTab = (tab, { focus = false } = {}) => {
    const panelId = tab.getAttribute("aria-controls");
    if (!panelId) {
      return;
    }

    tabs.forEach((candidate) => {
      const isActive = candidate === tab;
      candidate.classList.toggle("is-active", isActive);
      candidate.setAttribute("aria-selected", isActive ? "true" : "false");
      candidate.tabIndex = isActive ? 0 : -1;
    });

    panels.forEach((panel, id) => {
      const isActive = id === panelId;
      panel.hidden = !isActive;
      panel.classList.toggle("is-active", isActive);
    });

    if (focus) {
      tab.focus();
    }
  };

  const focusRelative = (currentIndex, step) => {
    const nextIndex = (currentIndex + step + tabs.length) % tabs.length;
    const nextTab = tabs[nextIndex];
    if (nextTab) {
      activateTab(nextTab, { focus: true });
    }
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab));
    tab.addEventListener("keydown", (event) => {
      switch (event.key) {
        case "ArrowLeft":
        case "ArrowUp":
          event.preventDefault();
          focusRelative(index, -1);
          break;
        case "ArrowRight":
        case "ArrowDown":
          event.preventDefault();
          focusRelative(index, 1);
          break;
        case "Home":
          event.preventDefault();
          activateTab(tabs[0], { focus: true });
          break;
        case "End":
          event.preventDefault();
          activateTab(tabs[tabs.length - 1], { focus: true });
          break;
        default:
          break;
      }
    });
  });

  const initialTab = tabs.find((tab) => tab.getAttribute("aria-selected") === "true") || tabs[0];
  if (initialTab) {
    activateTab(initialTab);
  }
});
