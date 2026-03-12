(function () {
  "use strict";

  var formSelector = 'form[data-specialkost-delete-form="1"]';
  var buttonSelector = '[data-specialkost-delete-trigger="1"]';
  var defaultMessage = "Varning: Om kosttypen har kopplingar till avdelningar tas de bort. Vill du fortsätta?";

  function resolveForm(fromElement) {
    if (!fromElement) {
      return null;
    }
    if (fromElement.form) {
      return fromElement.form;
    }
    return fromElement.closest(formSelector);
  }

  function shouldContinue(form) {
    if (!form || form.dataset.specialkostConfirmed === "1") {
      return true;
    }
    var message = form.getAttribute("data-confirm-message") || defaultMessage;
    var accepted = window.confirm(message);
    if (accepted) {
      form.dataset.specialkostConfirmed = "1";
    }
    return accepted;
  }

  document.addEventListener("click", function (event) {
    var target = event.target;
    if (!(target instanceof Element)) {
      return;
    }
    var button = target.closest(buttonSelector);
    if (!button) {
      return;
    }
    var form = resolveForm(button);
    if (form && !shouldContinue(form)) {
      event.preventDefault();
      event.stopPropagation();
    }
  });

  document.addEventListener("submit", function (event) {
    var target = event.target;
    if (!(target instanceof HTMLFormElement)) {
      return;
    }
    if (!target.matches(formSelector)) {
      return;
    }
    if (!shouldContinue(target)) {
      event.preventDefault();
      event.stopPropagation();
    }
  });
})();
