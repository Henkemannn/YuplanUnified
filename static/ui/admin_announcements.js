(function () {
  function submitIfReady(input) {
    const form = input && input.closest('form[data-announcement-form="1"]');
    if (!form || form.dataset.submitting === '1') {
      return;
    }

    if (input.name === 'event_time') {
      const val = String(input.value || '').trim();
      if (val && !/^\d{2}:\d{2}$/.test(val)) {
        return;
      }
    }

    form.dataset.submitting = '1';
    form.requestSubmit();
  }

  document.querySelectorAll('form[data-announcement-form="1"]').forEach(function (form) {
    form.querySelectorAll('[data-autosubmit="1"]').forEach(function (input) {
      input.addEventListener('change', function () {
        submitIfReady(input);
      });

      if (input.name === 'event_time') {
        input.addEventListener('input', function () {
          submitIfReady(input);
        });
      }
    });
  });

  document.querySelectorAll('[data-picker-wrap]').forEach(function (wrap) {
    const input = wrap.querySelector('input[type="date"], input[type="time"]');
    if (!input) {
      return;
    }

    wrap.addEventListener('click', function (event) {
      if (event.target === input) {
        return;
      }
      input.focus();
      if (typeof input.showPicker === 'function') {
        try {
          input.showPicker();
        } catch (_err) {
          // Fallback to browser default focus behavior.
        }
      }
    });
  });
})();
