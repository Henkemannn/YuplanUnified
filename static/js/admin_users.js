(function () {
  "use strict";

  function closeMenu(trigger, menu, restoreFocus) {
    if (!trigger || !menu) {
      return;
    }
    menu.hidden = true;
    menu.style.top = "";
    menu.style.left = "";
    trigger.setAttribute("aria-expanded", "false");
    if (restoreFocus) {
      trigger.focus();
    }
  }

  function closeAllMenus(exceptTrigger) {
    document.querySelectorAll("[data-user-menu-trigger]").forEach(function (trigger) {
      if (trigger === exceptTrigger) {
        return;
      }
      closeMenu(trigger, document.getElementById(trigger.getAttribute("data-menu-id")), false);
    });
  }

  function positionMenu(trigger, menu) {
    var triggerRect = trigger.getBoundingClientRect();
    var menuRect = menu.getBoundingClientRect();
    var margin = 8;
    var left = Math.min(triggerRect.left, window.innerWidth - menuRect.width - margin);
    var top = triggerRect.bottom + margin;

    if (top + menuRect.height > window.innerHeight - margin && triggerRect.top - menuRect.height - margin >= margin) {
      top = triggerRect.top - menuRect.height - margin;
    }
    menu.style.left = Math.max(margin, Math.round(left)) + "px";
    menu.style.top = Math.max(margin, Math.round(top)) + "px";
  }

  function openMenu(trigger, menu) {
    closeAllMenus(trigger);
    menu.hidden = false;
    trigger.setAttribute("aria-expanded", "true");
    positionMenu(trigger, menu);
    var firstAction = menu.querySelector("button:not([disabled])");
    if (firstAction) {
      firstAction.focus();
    }
  }

  function syncMenuHostTheme(menuHost) {
    var shell = document.querySelector(".app-shell");
    if (!shell) {
      return;
    }
    var shellStyles = window.getComputedStyle(shell);
    [
      "--surface",
      "--surface-elevated",
      "--border",
      "--border-subtle",
      "--muted",
      "--accent",
      "--r-md",
      "--sh-2"
    ].forEach(function (token) {
      var value = shellStyles.getPropertyValue(token).trim();
      if (value) {
        menuHost.style.setProperty(token, value);
      }
    });
    menuHost.classList.toggle("app-shell--dark", shell.classList.contains("app-shell--dark"));
  }

  function initializeProtectedForm(form) {
    var button = form.querySelector("button[type='submit']");
    if (!button) {
      return;
    }
    button.disabled = false;
    form.addEventListener("submit", function (event) {
      var message = form.getAttribute("data-confirm-message") || "Vill du fortsätta?";
      if (!window.confirm(message)) {
        event.preventDefault();
      }
    });
  }

  function initialize() {
    var menuHost = document.createElement("div");
    menuHost.className = "admin-users user-menu-host";
    document.body.appendChild(menuHost);
    syncMenuHostTheme(menuHost);
    var shell = document.querySelector(".app-shell");
    if (shell) {
      new MutationObserver(function () {
        syncMenuHostTheme(menuHost);
      }).observe(shell, { attributes: true, attributeFilter: ["class", "data-theme"] });
    }

    document.querySelectorAll(".admin-users [data-user-menu-trigger]").forEach(function (trigger) {
      var menu = document.getElementById(trigger.getAttribute("data-menu-id"));
      if (!menu) {
        return;
      }
      menuHost.appendChild(menu);
      trigger.addEventListener("click", function () {
        if (menu.hidden) {
          openMenu(trigger, menu);
        } else {
          closeMenu(trigger, menu, false);
        }
      });
      menu.querySelectorAll(".user-protected-form").forEach(initializeProtectedForm);
    });

    document.addEventListener("click", function (event) {
      document.querySelectorAll("[data-user-menu-trigger]").forEach(function (trigger) {
        var menu = document.getElementById(trigger.getAttribute("data-menu-id"));
        if (!menu || menu.hidden || trigger.contains(event.target) || menu.contains(event.target)) {
          return;
        }
        closeMenu(trigger, menu, false);
      });
    });

    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") {
        return;
      }
      var openTrigger = document.querySelector("[data-user-menu-trigger][aria-expanded='true']");
      if (!openTrigger) {
        return;
      }
      closeMenu(openTrigger, document.getElementById(openTrigger.getAttribute("data-menu-id")), true);
    });

    function repositionOpenMenu() {
      var openTrigger = document.querySelector("[data-user-menu-trigger][aria-expanded='true']");
      if (openTrigger) {
        positionMenu(openTrigger, document.getElementById(openTrigger.getAttribute("data-menu-id")));
      }
    }

    window.addEventListener("resize", repositionOpenMenu);
    window.addEventListener("scroll", repositionOpenMenu, true);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initialize);
  } else {
    initialize();
  }
}());
