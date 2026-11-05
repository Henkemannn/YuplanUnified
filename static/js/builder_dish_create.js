(function () {
  'use strict';

  const state = {
    bound: false,
    modal: null,
    title: null,
    nameInput: null,
    categoryInput: null,
    submitButton: null,
    closeButton: null,
    output: null,
    previewOutput: null,
    config: null,
    submitting: false,
    previewTimer: null,
    previewRequestId: 0,
    reviewedComponents: [],
    rowSequence: 0,
    editingRowId: null,
    editingMode: null,
    pickerRowId: null,
    pickerOptions: [],
    categoryEditor: null,
    idempotencyKey: null,
    previewReady: false,
  };

  function getElement(id) {
    return document.getElementById(String(id || ''));
  }

  function setOutput(message, isError = false) {
    if (!state.output) {
      return;
    }
    state.output.textContent = String(message || '');
    state.output.dataset.state = isError ? 'error' : 'idle';
  }

  function previewEnabled() {
    return Boolean(
      state.config
      && String(state.config.previewEndpoint || '').trim()
      && state.previewOutput,
    );
  }

  function reviewEnabled() {
    return Boolean(
      state.config
      && String(state.config.reviewEndpoint || '').trim()
      && String(state.config.menuDetailId || '').trim(),
    );
  }

  function clearPreview() {
    if (state.previewTimer) {
      window.clearTimeout(state.previewTimer);
      state.previewTimer = null;
    }
    state.previewRequestId += 1;
    state.previewReady = false;
    if (state.previewOutput) {
      state.previewOutput.replaceChildren();
      state.previewOutput.hidden = true;
      state.previewOutput.dataset.state = 'idle';
    }
  }

  function setPreviewMessage(message, stateName = 'idle') {
    if (!state.previewOutput) {
      return;
    }
    state.previewOutput.replaceChildren();
    state.previewOutput.hidden = false;
    state.previewOutput.dataset.state = stateName;
    state.previewOutput.textContent = String(message || '');
  }

  function closeCategoryEditor() {
    if (state.categoryEditor) {
      state.categoryEditor.remove();
      state.categoryEditor = null;
    }
  }

  function renderCategoryOptions(categories, selectedValue = 'ovrigt') {
    if (!state.categoryInput) {
      return;
    }
    const selected = String(selectedValue || 'ovrigt');
    state.categoryInput.replaceChildren();
    for (const category of Array.isArray(categories) ? categories : []) {
      const option = document.createElement('option');
      option.value = String(category && category.key || '').trim();
      option.textContent = String(category && category.label || option.value).trim();
      if (option.value) {
        option.selected = option.value === selected;
        state.categoryInput.appendChild(option);
      }
    }
    const createOption = document.createElement('option');
    createOption.value = '__new_dish_category__';
    createOption.textContent = '+ Ny kategori';
    state.categoryInput.appendChild(createOption);
    if ([...state.categoryInput.options].some((option) => option.value === selected)) {
      state.categoryInput.value = selected;
    }
  }

  async function loadDishCategories() {
    const endpoint = String(state.config && state.config.categoryEndpoint || '').trim();
    if (!endpoint || !state.categoryInput) {
      return;
    }
    try {
      const response = await fetch(endpoint, { method: 'GET', credentials: 'same-origin' });
      const data = await response.json().catch(() => ({ ok: false }));
      if (!(response.status < 400 && data && data.ok && Array.isArray(data.categories))) {
        throw new Error('Kategorier kunde inte laddas.');
      }
      renderCategoryOptions(data.categories, state.categoryInput.value || 'ovrigt');
    } catch (error) {
      setOutput(String(error && error.message || error), true);
    }
  }

  function openCategoryEditor() {
    closeCategoryEditor();
    const editor = document.createElement('div');
    editor.className = 'create-dish-category-inline-editor';
    const input = document.createElement('input');
    input.type = 'text';
    input.placeholder = 'Ny kategoris namn';
    input.setAttribute('aria-label', 'Ny kategoris namn');
    const save = document.createElement('button');
    save.type = 'button';
    save.textContent = 'Lägg till';
    const cancel = document.createElement('button');
    cancel.type = 'button';
    cancel.textContent = 'Avbryt';
    editor.append(input, save, cancel);
    state.categoryInput.insertAdjacentElement('afterend', editor);
    state.categoryEditor = editor;
    input.focus();

    cancel.addEventListener('click', () => {
      state.categoryInput.value = 'ovrigt';
      closeCategoryEditor();
    });
    save.addEventListener('click', async () => {
      const name = input.value.trim();
      const endpoint = String(state.config && state.config.categoryEndpoint || '').trim();
      if (!name || !endpoint) {
        setOutput('Kategorinamn måste anges.', true);
        input.focus();
        return;
      }
      save.disabled = true;
      try {
        const response = await fetch(endpoint, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ name }),
        });
        const data = await response.json().catch(() => ({ ok: false }));
        if (!(response.status < 400 && data && data.ok && data.category)) {
          throw new Error(String(data && (data.message || data.error) || 'Kategorin kunde inte skapas.'));
        }
        const option = document.createElement('option');
        option.value = String(data.category.key);
        option.textContent = String(data.category.label || name);
        state.categoryInput.insertBefore(option, state.categoryInput.lastElementChild);
        state.categoryInput.value = option.value;
        closeCategoryEditor();
        setOutput('', false);
      } catch (error) {
        setOutput(String(error && error.message || error), true);
        save.disabled = false;
      }
    });
  }

  function nextRowId() {
    state.rowSequence += 1;
    return 'component-row-' + state.rowSequence.toString(36);
  }

  function normalizeReviewedComponent(suggestion) {
    const match = suggestion && suggestion.match ? suggestion.match : {};
    const resolution = String(suggestion && suggestion.resolution || 'new').trim();
    const componentId = String(match.component_id || '').trim();
    return {
      rowId: nextRowId(),
      name: String(suggestion && suggestion.suggested_name || '').trim(),
      component_id: componentId,
      resolution,
      selection: resolution === 'reusable' && componentId
        ? 'reuse'
        : resolution === 'new'
          ? 'new'
          : null,
      match,
      matchRequestId: 0,
      matchPending: false,
    };
  }

  function reviewedStatus(entry) {
    if (entry.matchPending) {
      return 'Söker i komponentbiblioteket...';
    }
    if (entry.resolution === 'ambiguous') {
      return 'Flera möjliga matchningar';
    }
    if (entry.selection === 'reuse' && entry.component_id) {
      return 'Finns i komponentbiblioteket';
    }
    return 'Ny komponent';
  }

  function currentReviewedComponent(rowId) {
    return state.reviewedComponents.find((entry) => entry.rowId === rowId) || null;
  }

  function closeOpenComponentMenus() {
    if (!state.previewOutput) {
      return false;
    }
    const openMenus = state.previewOutput.querySelectorAll('.create-dish-component-overflow[open]');
    for (const menu of openMenus) {
      menu.removeAttribute('open');
    }
    return openMenus.length > 0;
  }

  function invalidateReviewedMatch(entry) {
    entry.component_id = '';
    entry.selection = 'new';
    entry.resolution = 'new';
    entry.match = { status: 'no_match', possible_matches: [] };
    entry.matchRequestId = (entry.matchRequestId || 0) + 1;
    entry.matchPending = false;
  }

  async function rematchReviewedComponent(entry) {
    if (!previewEnabled() || !entry || !String(entry.name || '').trim()) {
      return;
    }
    const requestId = (entry.matchRequestId || 0) + 1;
    entry.matchRequestId = requestId;
    entry.matchPending = true;
    renderPreviewRows();
    try {
      const response = await fetch(String(state.config.previewEndpoint), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ component_name: entry.name }),
      });
      const data = await response.json().catch(() => ({ ok: false }));
      const current = currentReviewedComponent(entry.rowId);
      if (!current || current.matchRequestId !== requestId) {
        return;
      }
      if (!(response.status < 400 && data && data.ok && Array.isArray(data.suggestions))) {
        throw new Error(String(data && (data.message || data.error) || 'Komponentmatchningen kunde inte laddas.'));
      }
      const suggestion = data.suggestions[0] || {};
      const match = suggestion.match || {};
      const resolution = String(suggestion.resolution || 'new').trim();
      const componentId = String(match.component_id || '').trim();
      current.match = match;
      current.resolution = resolution;
      current.component_id = componentId;
      current.selection = resolution === 'reusable' && componentId
        ? 'reuse'
        : resolution === 'ambiguous'
          ? null
          : 'new';
      current.matchPending = false;
      renderPreviewRows();
    } catch (error) {
      const current = currentReviewedComponent(entry.rowId);
      if (current && current.matchRequestId === requestId) {
        current.matchPending = false;
        current.selection = 'new';
        current.resolution = 'new';
        current.component_id = '';
        current.match = { status: 'no_match', possible_matches: [] };
        renderPreviewRows();
        setOutput(String(error && error.message || error), true);
      }
    }
  }

  function appendActionButton(menu, label, handler) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.addEventListener('click', () => {
      menu.closest('details').removeAttribute('open');
      handler();
    });
    menu.appendChild(button);
  }

  function renderReviewedComponents(list) {
    for (const entry of state.reviewedComponents) {
      const item = document.createElement('li');
      item.className = 'create-dish-component-row';
      item.dataset.rowId = entry.rowId;

      const editing = state.editingRowId === entry.rowId;
      const picking = state.pickerRowId === entry.rowId;
      if (editing) {
        const editor = document.createElement('div');
        editor.className = 'create-dish-component-inline-editor';
        const input = document.createElement('input');
        input.type = 'text';
        input.value = entry.name;
        input.setAttribute('aria-label', 'Komponentnamn');
        editor.appendChild(input);

        const save = document.createElement('button');
        save.type = 'button';
        save.textContent = state.editingMode === 'new' ? 'Skapa variant' : 'Klar';
        save.addEventListener('click', () => {
          const value = input.value.trim();
          if (!value) {
            setOutput('Komponentnamn måste anges.', true);
            input.focus();
            return;
          }
          entry.name = value;
          if (state.editingMode === 'new') {
            invalidateReviewedMatch(entry);
            entry.selection = 'new';
          } else {
            invalidateReviewedMatch(entry);
            void rematchReviewedComponent(entry);
          }
          state.editingRowId = null;
          state.editingMode = null;
          renderPreviewRows();
        });
        editor.appendChild(save);

        const cancel = document.createElement('button');
        cancel.type = 'button';
        cancel.textContent = 'Avbryt';
        cancel.addEventListener('click', () => {
          state.editingRowId = null;
          state.editingMode = null;
          renderPreviewRows();
        });
        editor.appendChild(cancel);
        item.appendChild(editor);
        list.appendChild(item);
        continue;
      }

      const main = document.createElement('div');
      main.className = 'create-dish-component-row-main';
      const copy = document.createElement('div');
      copy.className = 'create-dish-component-row-copy';
      const name = document.createElement('strong');
      name.className = 'create-dish-component-name';
      name.textContent = entry.name;
      copy.appendChild(name);
      const status = document.createElement('span');
      status.className = 'create-dish-component-status';
      status.dataset.state = entry.selection === 'reuse' ? 'reusable' : entry.resolution;
      status.textContent = reviewedStatus(entry);
      copy.appendChild(status);
      main.appendChild(copy);

      const overflow = document.createElement('details');
      overflow.className = 'component-overflow create-dish-component-overflow';
      const summary = document.createElement('summary');
      summary.textContent = '...';
      summary.setAttribute('aria-label', 'Komponentåtgärder');
      summary.addEventListener('click', (event) => {
        event.stopPropagation();
      });
      overflow.appendChild(summary);
      const menu = document.createElement('div');
      menu.className = 'component-overflow-menu';
      menu.addEventListener('click', (event) => {
        event.stopPropagation();
      });

      appendActionButton(menu, 'Ändra', () => {
        state.editingRowId = entry.rowId;
        state.editingMode = 'edit';
        state.pickerRowId = null;
        renderPreviewRows();
      });
      appendActionButton(menu, 'Byt / välj befintlig', () => {
        chooseExistingComponent(entry);
      });
      appendActionButton(menu, 'Skapa ny variant', () => {
        state.editingRowId = entry.rowId;
        state.editingMode = 'new';
        state.pickerRowId = null;
        renderPreviewRows();
      });
      appendActionButton(menu, 'Ta bort från rätten', () => {
        state.reviewedComponents = state.reviewedComponents.filter((item) => item.rowId !== entry.rowId);
        state.editingRowId = null;
        state.pickerRowId = null;
        renderPreviewRows();
      });
      overflow.appendChild(menu);
      main.appendChild(overflow);
      item.appendChild(main);

      if (picking) {
        const picker = document.createElement('div');
        picker.className = 'create-dish-component-picker';
        const select = document.createElement('select');
        select.setAttribute('aria-label', 'Välj befintlig komponent');
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = 'Välj befintlig komponent…';
        select.appendChild(placeholder);
        for (const candidate of state.pickerOptions) {
          const option = document.createElement('option');
          option.value = String(candidate.component_id || '').trim();
          option.textContent = String(candidate.component_name || candidate.canonical_name || '').trim();
          select.appendChild(option);
        }
        select.addEventListener('change', () => {
          const candidate = state.pickerOptions.find(
            (item) => String(item.component_id || '').trim() === select.value,
          );
          if (!candidate) {
            return;
          }
          entry.name = String(candidate.component_name || candidate.canonical_name || entry.name).trim();
          entry.component_id = String(candidate.component_id || '').trim();
          entry.selection = 'reuse';
          entry.resolution = 'reusable';
          entry.match = { status: 'exact_match', component_id: entry.component_id };
          entry.matchRequestId = (entry.matchRequestId || 0) + 1;
          entry.matchPending = false;
          state.pickerRowId = null;
          state.pickerOptions = [];
          renderPreviewRows();
        });
        picker.appendChild(select);
        if (!state.pickerOptions.length) {
          const message = document.createElement('span');
          message.textContent = 'Inga synliga komponenter hittades.';
          picker.appendChild(message);
        }
        item.appendChild(picker);
      }

      list.appendChild(item);
    }
  }

  function renderPreviewRows() {
    if (!state.previewOutput) {
      return;
    }
    const list = state.previewOutput.querySelector('.create-dish-component-list');
    if (!list) {
      return;
    }
    list.replaceChildren();
    renderReviewedComponents(list);
  }

  async function chooseExistingComponent(entry) {
    state.editingRowId = null;
    state.editingMode = null;
    const candidates = Array.isArray(entry.match && entry.match.possible_matches)
      ? entry.match.possible_matches.slice()
      : [];
    if (entry.component_id && entry.match && entry.match.component_name) {
      candidates.unshift({
        component_id: entry.component_id,
        component_name: entry.match.component_name,
      });
    }
    state.pickerRowId = entry.rowId;
    state.pickerOptions = candidates.filter((candidate, index, items) => (
      candidate
      && String(candidate.component_id || '').trim()
      && items.findIndex((item) => String(item.component_id || '').trim() === String(candidate.component_id || '').trim()) === index
    ));
    renderPreviewRows();
    if (state.pickerOptions.length || !state.config || !state.config.componentLibraryEndpoint) {
      return;
    }
    try {
      const query = encodeURIComponent(String(entry.name || '').trim());
      const response = await fetch(
        String(state.config.componentLibraryEndpoint) + '?q=' + query,
        { method: 'GET', credentials: 'same-origin' },
      );
      const data = await response.json().catch(() => ({ ok: false }));
      if (!(response.status < 400 && data && data.ok && Array.isArray(data.components))) {
        throw new Error('Komponentbiblioteket kunde inte laddas.');
      }
      if (state.pickerRowId === entry.rowId) {
        state.pickerOptions = data.components;
        renderPreviewRows();
      }
    } catch (error) {
      if (state.pickerRowId === entry.rowId) {
        setOutput(String(error && error.message || error), true);
      }
    }
  }

  function renderPreview(data) {
    if (!state.previewOutput) {
      return;
    }
    const suggestions = Array.isArray(data && data.suggestions) ? data.suggestions : [];
    state.previewReady = true;
    state.previewOutput.replaceChildren();
    state.previewOutput.hidden = false;
    state.previewOutput.dataset.state = 'idle';

    const notice = document.createElement('p');
    notice.textContent = reviewEnabled()
      ? 'Granska komponenterna – sparas när du skapar.'
      : 'Förhandsvisning – inget sparas ännu.';
    state.previewOutput.appendChild(notice);

    if (!suggestions.length) {
      const empty = document.createElement('p');
      empty.textContent = 'Inga komponentförslag hittades.';
      state.previewOutput.appendChild(empty);
      return;
    }

    if (reviewEnabled()) {
      state.reviewedComponents = suggestions
        .map(normalizeReviewedComponent)
        .filter((item) => item.name);
      state.editingRowId = null;
      state.editingMode = null;
      state.pickerRowId = null;
      state.pickerOptions = [];
    }

    const list = document.createElement('ul');
    list.className = 'create-dish-component-list';
    if (reviewEnabled()) {
      renderReviewedComponents(list);
      state.previewOutput.appendChild(list);
      return;
    }
    for (const suggestion of suggestions) {
      const item = document.createElement('li');
      const name = String(suggestion && suggestion.suggested_name || '').trim();
      const resolution = String(suggestion && suggestion.resolution || 'new').trim();
      const match = suggestion && suggestion.match ? suggestion.match : {};
      let status = 'Ny komponentförslag';
      if (resolution === 'reusable') {
        const matchedName = String(match.component_name || name).trim();
        const matchStatus = String(match.status || 'exact_match').trim() === 'alias_match'
          ? 'aliasmatchning'
          : 'exakt matchning';
        status = 'Återanvändbar – ' + matchStatus + ': ' + matchedName;
      } else if (resolution === 'ambiguous') {
        const possibleMatches = Array.isArray(match.possible_matches) ? match.possible_matches : [];
        const names = possibleMatches
          .map((candidate) => String(candidate && candidate.component_name || '').trim())
          .filter(Boolean);
        status = names.length
          ? 'Tvetydig – möjliga matchningar: ' + names.join(', ')
          : 'Tvetydig – välj senare';
      }
      item.textContent = name ? name + ' – ' + status : status;
      list.appendChild(item);
    }
    state.previewOutput.appendChild(list);
  }

  function schedulePreview() {
    if (!previewEnabled()) {
      return;
    }
    if (state.previewTimer) {
      window.clearTimeout(state.previewTimer);
    }
    const requestId = state.previewRequestId + 1;
    state.previewRequestId = requestId;
    const name = String(state.nameInput ? state.nameInput.value : '').trim();
    if (!name) {
      clearPreview();
      return;
    }
    if (reviewEnabled()) {
      state.reviewedComponents = [];
      state.previewReady = false;
    }
    setPreviewMessage('Laddar komponentförslag…');
    state.previewTimer = window.setTimeout(async () => {
      state.previewTimer = null;
      try {
        const response = await fetch(String(state.config.previewEndpoint), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'same-origin',
          body: JSON.stringify({ dish_name: name }),
        });
        const data = await response
          .json()
          .catch(() => ({ ok: false, error: 'invalid_json_response' }));
        if (requestId !== state.previewRequestId) {
          return;
        }
        if (!(response.status < 400 && data && data.ok)) {
          throw new Error(String(data && (data.message || data.error) || 'Förhandsvisningen kunde inte laddas.'));
        }
        renderPreview(data);
      } catch (error) {
        if (requestId === state.previewRequestId) {
          setPreviewMessage('Förhandsvisningen kunde inte laddas. Skapa rätt fungerar ändå.', 'error');
        }
      }
    }, 250);
  }

  function setSubmitting(isSubmitting) {
    state.submitting = Boolean(isSubmitting);
    if (state.submitButton) {
      state.submitButton.disabled = Boolean(isSubmitting);
      state.submitButton.textContent = isSubmitting ? 'Skapar…' : 'Skapa rätt';
    }
  }

  function resetFields() {
    if (state.nameInput) {
      state.nameInput.value = '';
    }
    if (state.categoryInput) {
      state.categoryInput.value = 'ovrigt';
    }
    closeCategoryEditor();
    state.reviewedComponents = [];
    state.editingRowId = null;
    state.editingMode = null;
    state.pickerRowId = null;
    state.pickerOptions = [];
    state.idempotencyKey = null;
  }

  function hideModal() {
    if (!state.modal) {
      return;
    }
    state.modal.classList.add('hidden');
    state.modal.hidden = true;
    state.modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
  }

  function showModal() {
    if (!state.modal) {
      return;
    }
    state.modal.classList.remove('hidden');
    state.modal.hidden = false;
    state.modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
    if (state.nameInput) {
      state.nameInput.focus();
    }
  }

  async function submit() {
    if (state.submitting || !state.config) {
      return;
    }

    const name = String(state.nameInput ? state.nameInput.value : '').trim();
    const libraryGroup = String(state.categoryInput ? state.categoryInput.value : 'ovrigt').trim() || 'ovrigt';
    if (!name) {
      setOutput('Rättnamn måste anges.', true);
      if (state.nameInput) {
        state.nameInput.focus();
      }
      return;
    }

    const endpoint = String(state.config.createEndpoint || state.config.endpoint || '').trim();
    if (!endpoint) {
      setOutput('Create endpoint saknas.', true);
      return;
    }
    if (reviewEnabled() && !state.previewReady) {
      setOutput('Komponentförslagen kunde inte laddas. Försök igen innan du sparar.', true);
      return;
    }

    setSubmitting(true);
    setOutput('Skapar...');

    try {
      const requestBody = reviewEnabled()
        ? {
          menu_detail_id: String(state.config.menuDetailId),
          composition_name: name,
          library_group: libraryGroup,
          idempotency_key: state.idempotencyKey,
          components: state.reviewedComponents
            .filter((entry) => String(entry.name || '').trim())
            .map((entry) => ({
              name: String(entry.name).trim(),
              ...(String(entry.selection || '').trim()
                ? { selection: String(entry.selection).trim() }
                : {}),
              ...(String(entry.component_id || '').trim()
                ? { component_id: String(entry.component_id).trim() }
                : {}),
            })),
        }
        : {
          composition_name: name,
          library_group: libraryGroup,
        };
      if (!reviewEnabled() && state.config.includeSeedComponents !== false) {
        requestBody.seed_components = false;
      }
      if (reviewEnabled() && state.reviewedComponents.some((entry) => (
        !String(entry.selection || '').trim() || entry.matchPending
      ))) {
        setOutput('Välj befintlig komponent eller skapa ny variant för varje rad.', true);
        return;
      }

      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(requestBody),
      });
      const data = await response
        .json()
        .catch(() => ({ ok: false, error: 'invalid_json_response', message: 'Response was not valid JSON' }));
      const result = { status: response.status, data };
      if (!(response.status < 400 && data && data.ok && data.composition)) {
        setOutput(String(data && data.message || data && data.error || 'Kunde inte skapa rätt.'), true);
        return;
      }

      hideModal();
      resetFields();
      setOutput('', false);
      if (typeof state.config.onSuccess === 'function') {
        await state.config.onSuccess(data.composition, result);
      }
    } catch (error) {
      setOutput(String(error && error.message || error), true);
    } finally {
      setSubmitting(false);
    }
  }

  function close(reason = 'cancel') {
    hideModal();
    if (reason === 'cancel' && state.config && typeof state.config.onCancel === 'function') {
      state.config.onCancel();
    }
  }

  function bind(config) {
    state.config = { ...(config || {}) };
    state.modal = getElement(state.config.modalId || 'quickCreateModal');
    state.title = getElement(state.config.titleId || 'quickCreateModalTitle');
    state.nameInput = getElement(state.config.nameInputId || 'freeDishName');
    state.categoryInput = getElement(state.config.categoryInputId || 'freeDishCategory');
    state.submitButton = getElement(state.config.submitButtonId || 'btnCreateDish');
    state.closeButton = getElement(state.config.closeButtonId || 'quickCreateModalClose');
    state.output = getElement(state.config.outputId || 'createDishOut');
    state.previewOutput = getElement(state.config.previewOutputId || 'createDishPreview');

    if (!state.bound) {
      if (state.submitButton) {
        state.submitButton.addEventListener('click', (event) => {
          event.preventDefault();
          submit();
        });
      }
      if (state.categoryInput) {
        state.categoryInput.addEventListener('change', () => {
          if (state.categoryInput.value === '__new_dish_category__') {
            openCategoryEditor();
          } else {
            closeCategoryEditor();
          }
        });
      }
      if (state.closeButton) {
        state.closeButton.addEventListener('click', (event) => {
          event.preventDefault();
          close('cancel');
        });
      }
      if (state.nameInput) {
        state.nameInput.addEventListener('input', () => {
          schedulePreview();
        });
      }
      if (state.modal) {
        state.modal.addEventListener('click', (event) => {
          if (event.target === state.modal) {
            close('cancel');
          }
        });
      }
      document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && state.modal && !state.modal.hidden) {
          if (closeOpenComponentMenus()) {
            event.preventDefault();
            return;
          }
          close('cancel');
        }
      });
      document.addEventListener('click', (event) => {
        if (!state.previewOutput || event.target instanceof Node && state.previewOutput.contains(event.target)) {
          return;
        }
        closeOpenComponentMenus();
      });
      state.bound = true;
    }

    return api;
  }

  function open(config) {
    state.config = { ...(state.config || {}), ...(config || {}) };
    if (!state.modal) {
      bind(state.config);
    }
    resetFields();
    if (state.nameInput && state.config.initialName) {
      state.nameInput.value = String(state.config.initialName);
    }
    if (state.config.idempotencyKey) {
      state.idempotencyKey = String(state.config.idempotencyKey);
    } else if (globalThis.crypto && typeof globalThis.crypto.randomUUID === 'function') {
      state.idempotencyKey = globalThis.crypto.randomUUID();
    } else {
      state.idempotencyKey = 'review-' + Date.now().toString(36) + '-' + Math.random().toString(36).slice(2);
    }
    if (state.title && state.config.title) {
      state.title.textContent = String(state.config.title);
    }
    setOutput('', false);
    clearPreview();
    void loadDishCategories();
    schedulePreview();
    setSubmitting(false);
    showModal();
    return api;
  }

  const api = {
    bind,
    open,
    close,
    setOutput,
    isOpen() {
      return Boolean(state.modal && !state.modal.hidden);
    },
  };

  globalThis.BuilderDishCreateModal = api;
})();