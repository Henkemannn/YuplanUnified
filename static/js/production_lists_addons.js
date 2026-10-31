document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("[data-production-lists-addons-root]");
  if (!root) {
    return;
  }

  const families = Array.from(root.querySelectorAll("[data-family-key]"));
  const resetPrintScope = () => {
    families.forEach((family) => family.classList.remove("is-print-inactive"));
  };
  const printAll = () => {
    resetPrintScope();
    window.print();
  };
  const printFamily = (familyKey) => {
    families.forEach((family) => {
      family.classList.toggle("is-print-inactive", family.getAttribute("data-family-key") !== familyKey);
    });
    window.print();
  };

  const printAllButton = root.querySelector("[data-production-lists-print-all]");
  if (printAllButton) {
    printAllButton.addEventListener("click", printAll);
  }
  root.querySelectorAll("[data-production-lists-print-family]").forEach((button) => {
    button.addEventListener("click", () => {
      printFamily(button.getAttribute("data-production-lists-print-family") || "");
    });
  });

  window.addEventListener("afterprint", resetPrintScope);
  root.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      resetPrintScope();
    }
  });
  if (!families.length) {
    resetPrintScope();
  }
});
