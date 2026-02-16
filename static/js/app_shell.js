document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".app-shell");
  if (!root) {
    return;
  }
  const themeToggle = root.querySelector("[data-theme-toggle]");
  const themeIcon = root.querySelector("[data-theme-icon]");
  const themeKey = "yp_theme";

  const applyTheme = (theme) => {
    const isDark = theme === "dark";
    root.classList.toggle("app-shell--dark", isDark);
    if (themeToggle) {
      themeToggle.setAttribute("aria-pressed", isDark ? "true" : "false");
    }
    if (themeIcon) {
      themeIcon.textContent = isDark ? "☀️" : "🌙";
    }
  };

  const storedTheme = localStorage.getItem(themeKey);
  applyTheme(storedTheme === "dark" ? "dark" : "light");
  requestAnimationFrame(() => {
    root.classList.add("is-ready");
  });

  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const isDark = root.classList.contains("app-shell--dark");
      const nextTheme = isDark ? "light" : "dark";
      localStorage.setItem(themeKey, nextTheme);
      applyTheme(nextTheme);
    });
  }

  const menu = root.querySelector("[data-user-menu]");
  const trigger = root.querySelector("[data-user-menu-trigger]");
  if (!menu || !trigger) {
    return;
  }

  const closeMenu = () => {
    menu.classList.remove("is-open");
    trigger.setAttribute("aria-expanded", "false");
  };

  const openMenu = () => {
    menu.classList.add("is-open");
    trigger.setAttribute("aria-expanded", "true");
  };

  trigger.addEventListener("click", (event) => {
    event.preventDefault();
    const isOpen = menu.classList.contains("is-open");
    if (isOpen) {
      closeMenu();
      return;
    }
    openMenu();
  });

  document.addEventListener("click", (event) => {
    if (!menu.classList.contains("is-open")) {
      return;
    }
    const target = event.target;
    if (target instanceof Node && menu.contains(target)) {
      if (target.closest(".app-shell__user-item")) {
        closeMenu();
      }
      return;
    }
    closeMenu();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") {
      return;
    }
    closeMenu();
  });

  menu.addEventListener("focusout", (event) => {
    if (!menu.classList.contains("is-open")) {
      return;
    }
    const nextFocus = event.relatedTarget;
    if (nextFocus instanceof Node && menu.contains(nextFocus)) {
      return;
    }
    closeMenu();
  });
});
