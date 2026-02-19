(function () {
  "use strict";

  function postJson(url, payload) {
    return fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
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

    postJson("/ui/api/remember-to-order/check", {
      id: itemId,
      checked: target.checked,
    })
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

    postJson("/ui/api/remember-to-order/add", {
      site_id: siteId,
      week_key: weekKey,
      text: textValue,
    })
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
