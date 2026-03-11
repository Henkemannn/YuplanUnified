(function () {
  "use strict";

  function readCookie(name) {
    var parts = (document.cookie || "").split(";");
    for (var i = 0; i < parts.length; i += 1) {
      var part = parts[i].trim();
      if (part.indexOf(name + "=") === 0) {
        return decodeURIComponent(part.substring(name.length + 1));
      }
    }
    return "";
  }

  function getCsrfToken() {
    var token = readCookie("csrf_token");
    if (token) {
      return token;
    }
    var meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.content) {
      return meta.content;
    }
    var input = document.querySelector("input[name='csrf_token']");
    return input && input.value ? input.value : "";
  }

  function postJson(url, payload, csrfToken) {
    var headers = {
      "Content-Type": "application/json",
    };
    if (csrfToken) {
      headers["X-CSRF-Token"] = csrfToken;
    }
    return fetch(url, {
      method: "POST",
      headers: headers,
      body: JSON.stringify(payload),
      credentials: "same-origin",
    });
  }

  function handleCheckboxChange(event) {
    var target = event.target;
    if (!target || !target.classList.contains("remember-to-order__checkbox")) {
      return;
    }
    var itemId = target.getAttribute("data-item-id");
    if (!itemId) {
      return;
    }
    var csrfToken = getCsrfToken();

    postJson("/ui/api/remember-to-order/check", {
      id: itemId,
      checked: target.checked,
    }, csrfToken)
      .then(function () {
        window.location.reload();
      })
      .catch(function () {
        window.location.reload();
      });
  }

  function handleAddFormSubmit(event) {
    var form = event.target;
    if (!form || form.id !== "rto-add-form") {
      return;
    }
    event.preventDefault();

    var input = form.querySelector("input[name='text']");
    var textValue = input ? input.value.trim() : "";
    if (!textValue) {
      return;
    }

    var siteId = form.getAttribute("data-site-id") || "";
    var weekKey = form.getAttribute("data-week-key") || "";
    if (input) {
      siteId = siteId || input.getAttribute("data-site-id") || "";
      weekKey = weekKey || input.getAttribute("data-week-key") || "";
    }
    if (!siteId) {
      var siteInput = form.querySelector("input[name='site_id']");
      siteId = siteInput ? siteInput.value : "";
    }
    if (!weekKey) {
      var weekInput = form.querySelector("input[name='week_key']");
      weekKey = weekInput ? weekInput.value : "";
    }

    var csrfToken = getCsrfToken();
    postJson("/ui/api/remember-to-order/add", {
      site_id: siteId,
      week_key: weekKey,
      text: textValue,
    }, csrfToken)
      .then(function () {
        window.location.reload();
      })
      .catch(function () {
        window.location.reload();
      });
  }

  document.addEventListener("change", handleCheckboxChange);
  document.addEventListener("submit", handleAddFormSubmit);
})();
