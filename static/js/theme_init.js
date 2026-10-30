(function () {
  try {
    var storedTheme = window.localStorage.getItem("yp_theme");
    var theme = storedTheme === "dark" ? "dark" : "light";
    var root = document.documentElement;
    root.setAttribute("data-theme", theme);
    root.classList.toggle("yp-theme-dark", theme === "dark");
    root.style.colorScheme = theme;
  } catch (error) {
    document.documentElement.setAttribute("data-theme", "light");
    document.documentElement.classList.remove("yp-theme-dark");
    document.documentElement.style.colorScheme = "light";
  }
}());
