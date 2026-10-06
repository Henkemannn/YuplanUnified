(function () {
  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function $all(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  function text(value) {
    return String(value || '').trim();
  }

  function init() {
    var dialog = document.getElementById('service-addon-modal');
    if (!dialog) return;

    var form = $('[data-service-addon-form]', dialog);
    var modeInput = $('input[name="service_addon_mode"]', dialog);
    var actionInput = $('input[name="service_addon_action"]', dialog);
    var rowIdInput = $('input[name="service_addon_row_id"]', dialog);
    var titleNode = $('[data-service-addon-title]', dialog);
    var subtitleNode = $('[data-service-addon-subtitle]', dialog);
    var addState = $('[data-service-addon-state="add"]', dialog);
    var createState = $('[data-service-addon-state="create"]', dialog);
    var editState = $('[data-service-addon-state="edit"]', dialog);
    var removeState = $('[data-service-addon-state="remove"]', dialog);
    var addSelect = $('[data-service-addon-select]', addState);
    var addSearch = $('[data-service-addon-search]', addState);
    var familySelect = $('[data-service-addon-family-select]', createState);
    var familyWrap = $('[data-service-addon-family-custom]', createState);
    var familyInput = $('input[name="service_addon_family_custom"]', createState);
    var editName = $('[data-service-addon-edit-name]', editState);
    var editFamily = $('[data-service-addon-edit-family]', editState);
    var removeName = $('[data-service-addon-remove-name]', removeState);
    var removeCancel = $('[data-service-addon-remove-cancel]', removeState);
    var removeStart = $('[data-service-addon-remove-start]', editState);
    var removeConfirm = $('[data-service-addon-remove-confirm]', removeState);
    var closeButtons = $all('[data-service-addon-close]', dialog);
    var removeForm = $('[data-service-addon-remove-form]', dialog);

    var fields = {
      add: {
        addonId: $('select[name="service_addon_id"]', addState),
        lunch: $('input[name="service_addon_lunch_count"]', addState),
        dinner: $('input[name="service_addon_dinner_count"]', addState),
        note: $('textarea[name="service_addon_note"]', addState),
      },
      create: {
        name: $('input[name="service_addon_new_name"]', createState),
        family: familySelect,
        familyCustom: familyInput,
        lunch: $('input[name="service_addon_lunch_count"]', createState),
        dinner: $('input[name="service_addon_dinner_count"]', createState),
        note: $('textarea[name="service_addon_note"]', createState),
      },
      edit: {
        lunch: $('input[name="service_addon_lunch_count"]', editState),
        dinner: $('input[name="service_addon_dinner_count"]', editState),
        note: $('textarea[name="service_addon_note"]', editState),
      },
    };

    if (!form || !modeInput || !actionInput || !rowIdInput || !titleNode || !subtitleNode || !addState || !createState || !editState || !removeState) {
      return;
    }

    var states = {
      add: addState,
      create: createState,
      edit: editState,
      remove: removeState,
    };

    function familyLabel(value) {
      var normalized = text(value).toLowerCase();
      if (normalized === 'mos') return 'Mos';
      if (normalized === 'sallad') return 'Sallad';
      if (normalized === 'ovrigt') return 'Övrigt';
      return text(value);
    }

    function showState(nextState) {
      Object.keys(states).forEach(function (key) {
        states[key].hidden = key !== nextState;
      });
      dialog.dataset.serviceAddonState = nextState;
      modeInput.value = nextState;

      Object.keys(states).forEach(function (key) {
        $all('input, select, textarea', states[key]).forEach(function (control) {
          if (control.type === 'hidden') {
            control.disabled = false;
            return;
          }
          control.disabled = key !== nextState;
        });
      });

      if (removeForm) {
        $all('input, select, textarea', removeForm).forEach(function (control) {
          if (control.type === 'hidden') {
            control.disabled = nextState !== 'remove';
          }
        });
      }
    }

    function setShellTitle(state, name, family) {
      if (state === 'create') {
        titleNode.textContent = 'Skapa ny serveringsanpassning';
        subtitleNode.textContent = 'Lägg till en återkommande anpassning för avdelningen.';
        return;
      }
      if (state === 'edit') {
        titleNode.textContent = 'Redigera serveringsanpassning';
        subtitleNode.textContent = name || '';
        return;
      }
      if (state === 'remove') {
        titleNode.textContent = 'Ta bort serveringsanpassning?';
        subtitleNode.textContent = '';
        return;
      }
      titleNode.textContent = 'Lägg till serveringsanpassning';
      subtitleNode.textContent = 'Välj en aktiv serveringsanpassning för den här siten.';
    }

    function filterAddSelect(query) {
      if (!addSelect) return;
      var normalized = text(query).toLowerCase();
      var firstVisible = null;
      $all('option', addSelect).forEach(function (option) {
        if (!option.value) {
          option.hidden = false;
          return;
        }
        var match = !normalized || text(option.textContent).toLowerCase().indexOf(normalized) !== -1;
        option.hidden = !match;
        if (match && !firstVisible) {
          firstVisible = option;
        }
      });
      if (firstVisible && (!addSelect.value || addSelect.selectedOptions.length && addSelect.selectedOptions[0].hidden)) {
        addSelect.value = firstVisible.value;
      }
    }

    function resetFamilyMode() {
      if (familyWrap) familyWrap.hidden = true;
      if (familySelect) familySelect.hidden = false;
      if (familyInput) familyInput.value = '';
      if (familySelect && !familySelect.value) {
        familySelect.value = 'ovrigt';
      }
    }

    function switchToCustomFamily() {
      if (familyWrap) familyWrap.hidden = false;
      if (familySelect) familySelect.hidden = true;
      if (familyInput && typeof familyInput.focus === 'function') {
        familyInput.focus();
      }
    }

    function resetFields() {
      if (typeof form.reset === 'function') {
        form.reset();
      }
      actionInput.value = '';
      rowIdInput.value = '';
      if (addSearch) addSearch.value = '';
      if (addSelect) addSelect.selectedIndex = 0;
      if (fields.add.addonId) fields.add.addonId.value = '';
      if (fields.add.lunch) fields.add.lunch.value = '';
      if (fields.add.dinner) fields.add.dinner.value = '';
      if (fields.add.note) fields.add.note.value = '';
      if (fields.create.name) fields.create.name.value = '';
      if (fields.create.lunch) fields.create.lunch.value = '';
      if (fields.create.dinner) fields.create.dinner.value = '';
      if (fields.create.note) fields.create.note.value = '';
      if (fields.edit.lunch) fields.edit.lunch.value = '';
      if (fields.edit.dinner) fields.edit.dinner.value = '';
      if (fields.edit.note) fields.edit.note.value = '';
      if (editName) editName.textContent = '';
      if (editFamily) editFamily.textContent = '';
      if (removeName) removeName.textContent = '';
      resetFamilyMode();
      showState('add');
      setShellTitle('add');
      filterAddSelect('');
    }

    function openDialog() {
      if (typeof dialog.showModal === 'function') {
        dialog.showModal();
      } else {
        dialog.setAttribute('open', 'open');
      }
      dialog.classList.add('ua-modal-open');
      document.body.classList.add('ua-modal-lock');
    }

    function closeDialog() {
      if (dialog.open) {
        dialog.close();
      } else {
        dialog.removeAttribute('open');
      }
      dialog.classList.remove('ua-modal-open');
      document.body.classList.remove('ua-modal-lock');
      resetFields();
    }

    function openAddState() {
      resetFields();
      setShellTitle('add');
      showState('add');
      openDialog();
      if (addSelect && typeof addSelect.focus === 'function') {
        addSelect.focus();
      }
    }

    function openCreateState() {
      showState('create');
      setShellTitle('create');
      openDialog();
      if (fields.create.name && typeof fields.create.name.focus === 'function') {
        fields.create.name.focus();
      }
    }

    function openEditState(trigger) {
      resetFamilyMode();
      setShellTitle('edit', text(trigger.getAttribute('data-service-addon-addon-name')));
      showState('edit');
      rowIdInput.value = text(trigger.getAttribute('data-service-addon-row-id'));
      actionInput.value = '';
      if (fields.edit.lunch) fields.edit.lunch.value = text(trigger.getAttribute('data-service-addon-lunch'));
      if (fields.edit.dinner) fields.edit.dinner.value = text(trigger.getAttribute('data-service-addon-dinner'));
      if (fields.edit.note) fields.edit.note.value = text(trigger.getAttribute('data-service-addon-note'));
      if (editName) editName.textContent = text(trigger.getAttribute('data-service-addon-addon-name'));
      if (editFamily) editFamily.textContent = familyLabel(trigger.getAttribute('data-service-addon-addon-family'));
      if (removeName) removeName.textContent = text(trigger.getAttribute('data-service-addon-addon-name'));
      openDialog();
      if (fields.edit.lunch && typeof fields.edit.lunch.focus === 'function') {
        fields.edit.lunch.focus();
      }
    }

    function openRemoveState() {
      actionInput.value = 'remove';
      setShellTitle('remove');
      showState('remove');
      openDialog();
      if (removeConfirm && typeof removeConfirm.focus === 'function') {
        removeConfirm.focus();
      }
    }

    document.addEventListener('click', function (event) {
      var trigger = event.target.closest('[data-modal-target="#service-addon-modal"]');
      if (trigger) {
        event.preventDefault();
        var triggerMode = text(trigger.getAttribute('data-service-addon-mode') || 'add').toLowerCase();
        if (triggerMode === 'edit') {
          openEditState(trigger);
          return;
        }
        if (triggerMode === 'create') {
          openCreateState();
          return;
        }
        openAddState();
        return;
      }

      if (event.target.closest('[data-service-addon-switch-create]')) {
        event.preventDefault();
        showState('create');
        setShellTitle('create');
        if (fields.create.name && typeof fields.create.name.focus === 'function') {
          fields.create.name.focus();
        }
        return;
      }

      if (event.target.closest('[data-service-addon-remove-start]')) {
        event.preventDefault();
        if (removeForm) {
          removeForm.hidden = false;
          var removeRowId = text(rowIdInput.value || event.target.closest('[data-service-addon-remove-start]').getAttribute('data-service-addon-row-id'));
          var triggerName = text(editName ? editName.textContent : '');
          removeForm.querySelector('input[name="service_addon_row_id"]').value = removeRowId;
          removeName.textContent = triggerName;
        }
        openRemoveState();
        return;
      }

      if (event.target.closest('[data-service-addon-remove-cancel]')) {
        event.preventDefault();
        if (removeForm) removeForm.hidden = true;
        showState('edit');
        setShellTitle('edit', editName ? editName.textContent : '');
        if (removeName && editName) {
          removeName.textContent = editName.textContent;
        }
        if (fields.edit.lunch && typeof fields.edit.lunch.focus === 'function') {
          fields.edit.lunch.focus();
        }
        return;
      }

      if (event.target.closest('[data-service-addon-close]')) {
        event.preventDefault();
        if (removeForm) removeForm.hidden = true;
        closeDialog();
      }
    });

    document.addEventListener('input', function (event) {
      if (event.target === addSearch) {
        filterAddSelect(addSearch.value);
      }
    });

    document.addEventListener('change', function (event) {
      if (event.target === familySelect) {
        if (familySelect && familySelect.value === '__custom__') {
          switchToCustomFamily();
        } else {
          if (familyWrap) familyWrap.hidden = true;
          if (familySelect) familySelect.hidden = false;
          if (familyInput) familyInput.value = '';
        }
        return;
      }
      if (event.target === addSelect) {
        filterAddSelect(addSearch ? addSearch.value : '');
      }
    });

    dialog.addEventListener('close', function () {
      if (removeForm) removeForm.hidden = true;
      resetFields();
    });

    resetFields();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
