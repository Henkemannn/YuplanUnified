document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-production-lists-addons-root]");
  if (!root) {
    return;
  }
  if (root.dataset.productionListsAddonsPrintInitialized === "true") {
    return;
  }
  root.dataset.productionListsAddonsPrintInitialized = "true";

  const families = Array.from(root.querySelectorAll("[data-family-key]"));
  const legacyFamilyPrintAttribute = "data-production-lists-print-family";
  const familyToggles = Array.from(root.querySelectorAll(`[data-production-lists-family-toggle], [${legacyFamilyPrintAttribute}]`));
  const feedback = root.querySelector("[data-production-lists-print-feedback]");
  const selectedFamilies = () => families.filter((family) => !family.classList.contains("is-print-unselected"));
  const resetPrintScope = () => {
    families.forEach((family) => family.classList.remove("is-print-inactive"));
  };
  const setFeedback = (message) => {
    if (!feedback) {
      return;
    }
    feedback.textContent = message;
    feedback.hidden = !message;
  };
  const syncToggle = (toggle, selected) => {
    toggle.setAttribute("aria-pressed", String(selected));
    const familyName = toggle.getAttribute("data-family-name") || "familjen";
    toggle.setAttribute("title", `${selected ? "Avmarkera" : "Välj"} ${familyName} för utskrift`);
  };
  const toggleFamily = (toggle) => {
    const familyKey = toggle.getAttribute("data-production-lists-family-toggle") || "";
    const family = families.find((item) => item.getAttribute("data-family-key") === familyKey);
    if (!family) {
      return;
    }
    const selected = family.classList.toggle("is-print-unselected") === false;
    syncToggle(toggle, selected);
    setFeedback("");
  };
  const printAll = () => {
    const selected = selectedFamilies();
    if (!selected.length) {
      setFeedback("Välj minst en familj innan utskrift.");
      return;
    }
    families.forEach((family) => family.classList.toggle("is-print-inactive", !selected.includes(family)));
    setFeedback("");
    window.print();
  };

  const printAllButton = root.querySelector("[data-production-lists-print-all]");
  if (printAllButton) {
    printAllButton.addEventListener("click", printAll);
  }
  familyToggles.forEach((toggle) => {
    const familyKey = toggle.getAttribute("data-production-lists-family-toggle") || "";
    const family = families.find((item) => item.getAttribute("data-family-key") === familyKey);
    if (family) {
      family.classList.remove("is-print-unselected");
      syncToggle(toggle, true);
    }
    toggle.addEventListener("click", () => toggleFamily(toggle));
  });

  window.addEventListener("afterprint", resetPrintScope);
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      resetPrintScope();
    }
  });
  window.addEventListener("beforeprint", () => {
    const selected = selectedFamilies();
    families.forEach((family) => family.classList.toggle("is-print-inactive", !selected.includes(family)));
  });
  if (!families.length) {
    resetPrintScope();
  }
});
