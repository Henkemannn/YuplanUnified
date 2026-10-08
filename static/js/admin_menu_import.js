(function () {
  function $(id) {
    return document.getElementById(id);
  }

  function readJson(elementId, fallback) {
    var node = $(elementId);
    if (!node || !node.textContent) {
      return fallback;
    }
    try {
      return JSON.parse(node.textContent);
    } catch (error) {
      return fallback;
    }
  }

  function isoWeekFromDate(value) {
    var date = new Date(value.getFullYear(), value.getMonth(), value.getDate());
    var day = date.getDay() || 7;
    date.setDate(date.getDate() + 4 - day);
    var yearStart = new Date(date.getFullYear(), 0, 1);
    var week = Math.ceil((((date - yearStart) / 86400000) + 1) / 7);
    return { year: date.getFullYear(), week: week };
  }

  function currentWeekDefaults() {
    return isoWeekFromDate(new Date());
  }

  var newMenuModalRetryHandle = null;
  var liveSyncHandle = null;
  var liveSyncSnapshot = '';
  var previewDebounceHandle = null;
  window.__adminMenuImportDebug = window.__adminMenuImportDebug || {
    initAttempts: 0,
    attached: false,
    previewCalls: 0,
    rowRenderCalls: 0,
    openCalls: 0,
  };

  function initMenuImportUpload() {
    var input = $('menu_file');
    var label = $('menu-file-name');
    var submit = $('menu-import-submit');
    if (!input || !label || !submit) {
      return;
    }

    function syncUploadState() {
      var hasFile = !!(input.files && input.files[0]);
      label.textContent = hasFile ? input.files[0].name : 'Ingen fil vald';
      submit.disabled = !hasFile;
    }

    syncUploadState();
    input.addEventListener('change', syncUploadState);
  }

  function initNewMenuModal() {
    window.__adminMenuImportDebug.initAttempts += 1;
    var root = document.querySelector('[data-admin-menu-new-host]');
    var openTrigger = document.querySelector('[data-admin-menu-new-toggle]');
    if (!root || !openTrigger || !window.YuplanModalHost || !window.fetch) {
      if (!newMenuModalRetryHandle) {
        newMenuModalRetryHandle = window.setTimeout(function () {
          newMenuModalRetryHandle = null;
          initNewMenuModal();
        }, 50);
      }
      return;
    }

    var endpoint = String(root.getAttribute('data-admin-menu-new-endpoint') || '').trim();
    if (!endpoint) {
      return;
    }

    var modalHost = window.YuplanModalHost.create(root, {
      backdropSelector: '[data-admin-menu-new-close]',
      panelSelector: '[data-admin-menu-new-panel]',
      closeOnEscape: true,
      closeOnBackdrop: true,
      listenForMessages: false,
      resetFrameSrc: false,
    });

    var context = document.querySelector('[data-admin-menu-new-context]');
    var datePreview = document.querySelector('[data-admin-menu-new-date-preview]');
    var status = document.querySelector('[data-admin-menu-new-status]');
    var nameInput = document.querySelector('[data-admin-menu-new-name]');
    var yearInput = document.querySelector('[data-admin-menu-new-year]');
    var weekInput = document.querySelector('[data-admin-menu-new-week]');
    var rowCountInput = document.querySelector('[data-admin-menu-new-row-count]');
    var rowLabelsWrap = document.querySelector('[data-admin-menu-new-row-labels]');
    var pillsWrap = document.querySelector('[data-admin-menu-new-weekday-pills]');
    var daySummary = document.querySelector('[data-admin-menu-new-day-summary]');
    var createButton = document.querySelector('[data-admin-menu-new-create]');
    var csrfInput = root.querySelector('input[name="csrf_token"]');
    var closeButtons = root.querySelectorAll('[data-admin-menu-new-close]');
    var current = readJson('js-admin-menu-import-context', null) || {};
    var previewState = {
      conflict: false,
      openUrl: '',
      dateLabel: '',
      menuName: '',
    };

    function setStatus(message, state) {
      if (!status) {
        return;
      }
      status.textContent = message;
      status.dataset.state = state || 'neutral';
    }

    function selectedDayButtons() {
      if (!pillsWrap) {
        return [];
      }
      return Array.prototype.slice.call(pillsWrap.querySelectorAll('[data-admin-menu-new-day-toggle]')).filter(function (button) {
        return !!button.checked;
      });
    }

    function updateDaySummary() {
      if (!daySummary) {
        return;
      }
      var count = selectedDayButtons().length;
      var suffix = count === 1 ? 'dag' : 'dagar';
      daySummary.textContent = String(count) + ' ' + suffix + 's meny';
      if (count === 1) {
        daySummary.textContent = '1 dags meny';
      }
    }

    function hasSelectedDays() {
      return selectedDayButtons().length > 0;
    }

    function setDayButtonState(button, selected) {
      if (!button) {
        return;
      }
      button.checked = selected;
      var pill = button.closest ? button.closest('.admin-menu-import__weekday-pill') : null;
      if (pill) {
        pill.classList.toggle('is-selected', selected);
      }
      updateDaySummary();
    }

    function syncActionState() {
      if (createButton) {
        createButton.disabled = previewState.conflict || !hasSelectedDays();
      }
      if (!hasSelectedDays() && !previewState.conflict) {
        setStatus('Välj minst en veckodag innan du skapar menyn.', 'error');
      }
    }

    function snapshotState() {
      return [
        String(yearInput ? yearInput.value || '' : ''),
        String(weekInput ? weekInput.value || '' : ''),
        getMenuName(),
        String(rowCountInput ? rowCountInput.value || '0' : '0'),
        getSelectedDays().join(','),
        getRowLabels().join('\u001f'),
      ].join('|');
    }

    function schedulePreview() {
      if (previewDebounceHandle) {
        window.clearTimeout(previewDebounceHandle);
      }
      previewDebounceHandle = window.setTimeout(function () {
        previewDebounceHandle = null;
        previewMenu();
      }, 120);
    }

    function stopLiveSync() {
      if (liveSyncHandle) {
        window.clearInterval(liveSyncHandle);
        liveSyncHandle = null;
      }
      liveSyncSnapshot = '';
    }

    function stopDelegatedMenuImportEvents() {
      document.removeEventListener('input', handleDelegatedMenuImportEvent);
      document.removeEventListener('change', handleDelegatedMenuImportEvent);
    }

    function startLiveSync() {
      stopLiveSync();
      liveSyncSnapshot = snapshotState();
      liveSyncHandle = window.setInterval(function () {
        var nextSnapshot = snapshotState();
        if (nextSnapshot === liveSyncSnapshot) {
          return;
        }
        var previousParts = liveSyncSnapshot.split('|');
        var currentParts = nextSnapshot.split('|');
        var countChanged = previousParts[3] !== currentParts[3];
        liveSyncSnapshot = nextSnapshot;
        if (countChanged) {
          renderRowLabelInputs();
        }
        schedulePreview();
      }, 120);
    }

    function handleDelegatedMenuImportEvent(event) {
      var target = event.target;
      if (!target || !target.matches) {
        return;
      }
      if (target.matches('[data-admin-menu-new-year], [data-admin-menu-new-week], [data-admin-menu-new-name], [data-admin-menu-new-row-count], [data-admin-menu-new-row-label-input]')) {
        if (target.matches('[data-admin-menu-new-row-count]')) {
          renderRowLabelInputs();
        }
        schedulePreview();
        return;
      }
      if (target.matches('[data-admin-menu-new-day-toggle]')) {
        setDayButtonState(target, !!target.checked);
        schedulePreview();
      }
    }

    function appendCsrfToken(formData) {
      var token = '';
      if (csrfInput) {
        token = String(csrfInput.value || '').trim();
      }
      if (!token) {
        var fallback = document.querySelector('input[name="csrf_token"]');
        if (fallback) {
          token = String(fallback.value || '').trim();
        }
      }
      if (token) {
        formData.append('csrf_token', token);
      }
    }

    function renderRowLabelInputs() {
      window.__adminMenuImportDebug.rowRenderCalls += 1;
      if (!rowLabelsWrap || !rowCountInput) {
        return;
      }

      var rowCount = Math.max(0, parseInt(rowCountInput.value || '0', 10) || 0);
      var existingValues = [];
      var existingInputs = rowLabelsWrap.querySelectorAll('[data-admin-menu-new-row-label-input]');
      Array.prototype.forEach.call(existingInputs, function (input) {
        existingValues.push(String(input.value || ''));
      });

      rowLabelsWrap.innerHTML = '';
      if (rowCount <= 0) {
        rowLabelsWrap.hidden = true;
        return;
      }

      rowLabelsWrap.hidden = false;
      for (var index = 0; index < rowCount; index += 1) {
        var labelNumber = index + 1;
        var currentValue = existingValues[index] || '';
        var field = document.createElement('label');
        field.className = 'yp-modal-host__inline-search-label';
        field.setAttribute('for', 'adminMenuNewRowLabel' + labelNumber);
        field.textContent = 'Menyrad ' + labelNumber;

        var input = document.createElement('input');
        input.type = 'text';
        input.id = 'adminMenuNewRowLabel' + labelNumber;
        input.className = 'yp-input yp-modal-host__inline-search';
        input.placeholder = 'Menyrad ' + labelNumber;
        input.autocomplete = 'off';
        input.value = currentValue;
        input.setAttribute('data-admin-menu-new-row-label-input', '1');

        var wrap = document.createElement('div');
        wrap.className = 'admin-menu-import__row-label-field';
        wrap.appendChild(field);
        wrap.appendChild(input);
        rowLabelsWrap.appendChild(wrap);
      }
    }

    function getSelectedDays() {
      return selectedDayButtons().map(function (button) {
        return String(button.getAttribute('data-day') || '').trim();
      }).filter(function (value) {
        return !!value;
      });
    }

    function getRowLabels() {
      if (!rowLabelsWrap) {
        return [];
      }
      return Array.prototype.slice.call(rowLabelsWrap.querySelectorAll('[data-admin-menu-new-row-label-input]')).map(function (input) {
        return String(input.value || '').trim();
      });
    }

    function getMenuName() {
      return nameInput ? String(nameInput.value || '').trim() : '';
    }

    function fillDefaults() {
      var defaults = currentWeekDefaults();
      if (current.year && current.week) {
        defaults.year = Number(current.year);
        defaults.week = Number(current.week);
      }
      if (yearInput && !yearInput.value) {
        yearInput.value = String(defaults.year);
      }
      if (weekInput && !weekInput.value) {
        weekInput.value = String(defaults.week);
      }
      if (nameInput) {
        nameInput.value = '';
      }
      if (rowCountInput) {
        rowCountInput.value = '0';
      }
      if (pillsWrap) {
        Array.prototype.forEach.call(pillsWrap.querySelectorAll('[data-admin-menu-new-day-toggle]'), function (button) {
          setDayButtonState(button, true);
        });
      }
      updateDaySummary();
      renderRowLabelInputs();
      previewState = {
        conflict: false,
        openUrl: '',
        dateLabel: '',
        menuName: '',
      };
      setStatus('Välj år och vecka för att fortsätta.', 'neutral');
      if (context) {
        context.textContent = 'Skapar meny för vald vecka.';
      }
      if (datePreview) {
        datePreview.textContent = 'Välj år och vecka för att fortsätta.';
      }
      if (createButton) {
        createButton.hidden = false;
        createButton.disabled = false;
      }
      syncActionState();
    }

    function applyPreview(payload) {
      previewState.conflict = Boolean(payload && payload.status === 'conflict');
      previewState.openUrl = String((payload && payload.open_url) || '');
      previewState.dateLabel = String((payload && payload.week_range && payload.week_range.label) || '');
      previewState.menuName = String((payload && payload.menu_name) || getMenuName() || '').trim();

      if (datePreview) {
        datePreview.textContent = previewState.dateLabel || 'Välj år och vecka för att fortsätta.';
      }
      if (context) {
        context.textContent = previewState.menuName ? ('Meny: ' + previewState.menuName) : 'Skapar meny för vald vecka.';
      }
      if (previewState.conflict) {
        setStatus('Det finns redan en meny för vecka ' + String(weekInput ? weekInput.value || '' : '') + ' / ' + String(yearInput ? yearInput.value || '' : '') + '. Välj en annan vecka.', 'warning');
      } else {
        setStatus('Veckan är ledig. Du kan skapa en ny meny.', 'success');
      }
      syncActionState();
    }

    async function previewMenu() {
      window.__adminMenuImportDebug.previewCalls += 1;
      if (!yearInput || !weekInput) {
        return;
      }
      var formData = new FormData();
      appendCsrfToken(formData);
      formData.append('action', 'preview');
      formData.append('year', yearInput.value || '');
      formData.append('week', weekInput.value || '');
      formData.append('menu_name', getMenuName());
      formData.append('row_count', rowCountInput ? rowCountInput.value || '0' : '0');
      getSelectedDays().forEach(function (day) {
        formData.append('selected_days', day);
      });
      getRowLabels().forEach(function (label) {
        formData.append('row_labels', label);
      });

      setStatus('Kontrollerar menyveckan…', 'busy');
      try {
        var response = await window.fetch(endpoint, {
          method: 'POST',
          headers: {
            'X-Requested-With': 'XMLHttpRequest',
            'Accept': 'application/json',
          },
          body: formData,
          credentials: 'same-origin',
        });
        var payload = {};
        try {
          payload = await response.json();
        } catch (error) {
          payload = { ok: false, message: 'Kunde inte läsa serverns svar.' };
        }
        if (!response.ok || payload.ok === false) {
          throw new Error(payload.message || 'Förhandsgranskning misslyckades.');
        }
        applyPreview(payload);
      } catch (error) {
        setStatus(error && error.message ? error.message : 'Något gick fel.', 'error');
      }
    }

    async function submitMenu(action) {
      var selectedDays = getSelectedDays();
      if (action === 'create' && selectedDays.length === 0) {
        setStatus('Välj minst en veckodag innan du skapar menyn.', 'error');
        return;
      }
      var formData = new FormData();
      appendCsrfToken(formData);
      formData.append('action', action);
      formData.append('year', yearInput ? yearInput.value || '' : '');
      formData.append('week', weekInput ? weekInput.value || '' : '');
      formData.append('menu_name', getMenuName());
      formData.append('row_count', rowCountInput ? rowCountInput.value || '0' : '0');
      selectedDays.forEach(function (day) {
        formData.append('selected_days', day);
      });
      getRowLabels().forEach(function (label) {
        formData.append('row_labels', label);
      });

      setStatus(action === 'replace' ? 'Byter ut befintlig meny…' : 'Skapar meny…', 'busy');
      var response = await window.fetch(endpoint, {
        method: 'POST',
        headers: {
          'X-Requested-With': 'XMLHttpRequest',
          'Accept': 'application/json',
        },
        body: formData,
        credentials: 'same-origin',
      });

      var payload = {};
      try {
        payload = await response.json();
      } catch (error) {
        payload = { ok: false, message: 'Kunde inte läsa serverns svar.' };
      }
      if (!response.ok || payload.ok === false) {
        throw new Error(payload.message || 'Skapandet misslyckades.');
      }
      if (payload.open_url) {
        window.location.assign(payload.open_url);
        return;
      }
      throw new Error('Saknar mål-URL.');
    }

    function openModal() {
      window.__adminMenuImportDebug.openCalls += 1;
      fillDefaults();
      modalHost.open({ trigger: openTrigger, focusPanel: true });
      startLiveSync();
      schedulePreview();
    }

    openTrigger.addEventListener('click', openModal);

    if (yearInput) {
      yearInput.addEventListener('input', schedulePreview);
      yearInput.addEventListener('change', schedulePreview);
      yearInput.addEventListener('blur', schedulePreview);
    }
    if (weekInput) {
      weekInput.addEventListener('input', schedulePreview);
      weekInput.addEventListener('change', schedulePreview);
      weekInput.addEventListener('blur', schedulePreview);
    }
    if (nameInput) {
      nameInput.addEventListener('input', schedulePreview);
      nameInput.addEventListener('blur', schedulePreview);
    }
    if (rowCountInput) {
      rowCountInput.addEventListener('input', function () {
        renderRowLabelInputs();
        schedulePreview();
      });
      rowCountInput.addEventListener('change', function () {
        renderRowLabelInputs();
        schedulePreview();
      });
    }
    if (rowLabelsWrap) {
      rowLabelsWrap.addEventListener('input', function () {
        schedulePreview();
      });
    }
    if (pillsWrap) {
      pillsWrap.addEventListener('change', function (event) {
        var button = event.target && event.target.closest ? event.target.closest('[data-admin-menu-new-day-toggle]') : null;
        if (!button) {
          return;
        }
        setDayButtonState(button, !!button.checked);
        schedulePreview();
      });
    }
    document.addEventListener('input', handleDelegatedMenuImportEvent);
    document.addEventListener('change', handleDelegatedMenuImportEvent);

    if (createButton) {
      createButton.addEventListener('click', function () {
        submitMenu('create').catch(function (error) {
          setStatus(error && error.message ? error.message : 'Något gick fel.', 'error');
        });
      });
    }
    Array.prototype.forEach.call(closeButtons, function (button) {
      button.addEventListener('click', function () {
        stopLiveSync();
        stopDelegatedMenuImportEvents();
        modalHost.close();
      });
    });

    window.__adminMenuImportDebug.attached = true;
    return true;
  }

  function init() {
    initMenuImportUpload();
    initNewMenuModal();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
