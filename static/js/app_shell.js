document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector(".app-shell");
  if (!root) {
    return;
  }
  requestAnimationFrame(() => {
    root.classList.add("is-ready");
  });
});
