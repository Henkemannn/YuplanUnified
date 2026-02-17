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
  if (menu && trigger) {
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
  }

  const getIsoWeek = (date) => {
    const d = new Date(Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate()));
    const dayNum = d.getUTCDay() || 7;
    d.setUTCDate(d.getUTCDate() + 4 - dayNum);
    const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
    return Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  };

  const getIsoWeeksInYear = (year) => {
    const date = new Date(Date.UTC(year, 11, 28));
    return getIsoWeek(date);
  };

  const shiftWeek = (year, week, delta) => {
    let y = year;
    let w = week + delta;
    let weeksInYear = getIsoWeeksInYear(y);
    while (w < 1) {
      y -= 1;
      weeksInYear = getIsoWeeksInYear(y);
      w += weeksInYear;
    }
    while (w > weeksInYear) {
      w -= weeksInYear;
      y += 1;
      weeksInYear = getIsoWeeksInYear(y);
    }
    return { year: y, week: w };
  };

  const buildOptions = (select, baseYear, baseWeek) => {
    const range = 6;
    const options = [];
    for (let i = -range; i <= range; i += 1) {
      const next = shiftWeek(baseYear, baseWeek, i);
      const value = `${next.year}-${String(next.week).padStart(2, "0")}`;
      const label = `v${next.week} ${next.year}`;
      options.push({ value, label, year: next.year, week: next.week });
    }
    select.innerHTML = "";
    options.forEach((opt) => {
      const el = document.createElement("option");
      el.value = opt.value;
      el.textContent = opt.label;
      if (opt.year === baseYear && opt.week === baseWeek) {
        el.selected = true;
      }
      select.appendChild(el);
    });
  };

  const initWeekPicker = () => {
    root.querySelectorAll("[data-weekpicker]").forEach((picker) => {
      const select = picker.querySelector("[data-weekpicker-select]");
      const prevBtn = picker.querySelector("[data-weekpicker-prev]");
      const nextBtn = picker.querySelector("[data-weekpicker-next]");
      if (!select) {
        return;
      }
      const basePath = picker.getAttribute("data-base-path") || "";
      const siteId = picker.getAttribute("data-site-id");
      const baseYear = parseInt(picker.getAttribute("data-year") || "0", 10);
      const baseWeek = parseInt(picker.getAttribute("data-week") || "0", 10);
      if (!baseYear || !baseWeek || !basePath) {
        return;
      }
      buildOptions(select, baseYear, baseWeek);

      const navigate = (year, week) => {
        const params = new URLSearchParams();
        params.set("year", String(year));
        params.set("week", String(week));
        if (siteId) {
          params.set("site_id", siteId);
        }
        window.location = `${basePath}?${params.toString()}`;
      };

      select.addEventListener("change", (event) => {
        const value = event.target.value || "";
        const parts = value.split("-");
        if (parts.length < 2) {
          return;
        }
        const year = parseInt(parts[0], 10);
        const week = parseInt(parts[1], 10);
        if (!year || !week) {
          return;
        }
        navigate(year, week);
      });

      const readCurrent = () => {
        const value = select.value || "";
        const parts = value.split("-");
        if (parts.length >= 2) {
          const year = parseInt(parts[0], 10);
          const week = parseInt(parts[1], 10);
          if (year && week) {
            return { year, week };
          }
        }
        return { year: baseYear, week: baseWeek };
      };

      if (prevBtn) {
        prevBtn.addEventListener("click", () => {
          const current = readCurrent();
          const next = shiftWeek(current.year, current.week, -1);
          navigate(next.year, next.week);
        });
      }

      if (nextBtn) {
        nextBtn.addEventListener("click", () => {
          const current = readCurrent();
          const next = shiftWeek(current.year, current.week, 1);
          navigate(next.year, next.week);
        });
      }
    });
  };

  initWeekPicker();
});
