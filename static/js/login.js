document.addEventListener("DOMContentLoaded", () => {
  const toggle = document.querySelector("[data-password-toggle]");
  const password = document.getElementById("password");
  if (!toggle || !password) {
    return;
  }

  toggle.addEventListener("click", () => {
    const isVisible = password.type === "text";
    password.type = isVisible ? "password" : "text";
    toggle.setAttribute("aria-pressed", isVisible ? "false" : "true");
    toggle.setAttribute("aria-label", isVisible ? "Visa lösenord" : "Dölj lösenord");
    toggle.textContent = isVisible ? "Visa" : "Dölj";
  });
});
