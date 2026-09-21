document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("#yp-product-app");
  if (!root) {
    return;
  }

  const themeToggle = root.querySelector("[data-theme-toggle]");
  const themeIcon = root.querySelector("[data-theme-icon]");
  const themeKey = "yp_product_theme";

  const applyTheme = (theme) => {
    const isDark = theme === "dark";
    root.setAttribute("data-theme", isDark ? "dark" : "light");
    document.documentElement.style.colorScheme = isDark ? "dark" : "light";
    if (themeToggle) {
      themeToggle.setAttribute("aria-pressed", isDark ? "true" : "false");
      themeToggle.setAttribute("aria-label", isDark ? "Växla till light mode" : "Växla till dark mode");
    }
    if (themeIcon) {
      themeIcon.textContent = isDark ? "☀️" : "🌙";
    }
  };

  applyTheme(localStorage.getItem(themeKey) === "dark" ? "dark" : "light");

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const nextTheme = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      localStorage.setItem(themeKey, nextTheme);
      applyTheme(nextTheme);
    });
  }
});
