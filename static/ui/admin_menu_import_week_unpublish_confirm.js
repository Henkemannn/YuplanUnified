(function () {
  'use strict';

  function init() {
    var form = document.querySelector('form[action$="/unpublish"]');
    var dialog = document.querySelector('[data-unpublish-confirmation-dialog]');
    var confirmation = form && form.querySelector('[data-unpublish-confirmation]');
    var confirmButton = dialog && dialog.querySelector('[data-unpublish-confirmation-confirm]');

    if (!form || !dialog || !confirmation || !confirmButton) {
      return;
    }

    form.addEventListener('submit', function (event) {
      if (confirmation.value === '1') {
        return;
      }
      if (typeof dialog.showModal !== 'function') {
        return;
      }
      event.preventDefault();
      dialog.showModal();
      confirmButton.focus();
    });

    confirmButton.addEventListener('click', function () {
      confirmation.value = '1';
      dialog.close('confirm');
      if (typeof form.requestSubmit === 'function') {
        form.requestSubmit();
      } else {
        form.submit();
      }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
