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
      state.reviewedComponents = suggestions.map((suggestion) => {
        const match = suggestion && suggestion.match ? suggestion.match : {};
        return {
          name: String(suggestion && suggestion.suggested_name || '').trim(),
          component_id: String(match.component_id || '').trim(),
          resolution: String(suggestion && suggestion.resolution || 'new').trim(),
          match,
        };
      }).filter((item) => item.name);
    }

    const list = document.createElement('ul');
    for (const [index, suggestion] of suggestions.entries()) {
      const item = document.createElement('li');
      const name = String(suggestion && suggestion.suggested_name || '').trim();
      const resolution = String(suggestion && suggestion.resolution || 'new').trim();
      const match = suggestion && suggestion.match ? suggestion.match : {};
      if (reviewEnabled()) {
        item.replaceChildren();
        const nameInput = document.createElement('input');
        nameInput.type = 'text';
        nameInput.value = name;
        nameInput.setAttribute('aria-label', 'Komponentnamn');
        nameInput.addEventListener('input', () => {
          if (state.reviewedComponents[index]) {
            state.reviewedComponents[index].name = nameInput.value.trim();
          }
        });
        item.appendChild(nameInput);

        const select = document.createElement('select');
        select.setAttribute('aria-label', 'Komponentmatchning');
        if (resolution === 'ambiguous') {
          const placeholder = document.createElement('option');
          placeholder.value = '';
          placeholder.textContent = 'Välj befintlig komponent…';
          select.appendChild(placeholder);
          const possibleMatches = Array.isArray(match.possible_matches) ? match.possible_matches : [];
          for (const candidate of possibleMatches) {
            const option = document.createElement('option');
            option.value = String(candidate && candidate.component_id || '').trim();
            option.textContent = String(candidate && candidate.component_name || '').trim();
            select.appendChild(option);
          }
        } else {
          const option = document.createElement('option');
          option.value = String(match.component_id || '').trim();
          option.textContent = option.value
            ? 'Återanvänd: ' + String(match.component_name || name).trim()
            : 'Ny komponent';
          select.appendChild(option);
        }
        select.value = String(state.reviewedComponents[index] && state.reviewedComponents[index].component_id || '');
        select.addEventListener('change', () => {
          if (state.reviewedComponents[index]) {
            state.reviewedComponents[index].component_id = select.value;
          }
        });
        item.appendChild(select);

        const remove = document.createElement('button');
        remove.type = 'button';
        remove.textContent = 'Ta bort';
        remove.addEventListener('click', () => {
          state.reviewedComponents.splice(index, 1);
          renderPreview({ suggestions: state.reviewedComponents.map((entry) => ({
            suggested_name: entry.name,
            resolution: entry.resolution,
            match: { ...(entry.match || {}), component_id: entry.component_id },
          })) });
        });
        item.appendChild(remove);
        list.appendChild(item);
        continue;
      }
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
    state.reviewedComponents = [];
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
        entry.resolution === 'ambiguous' && !String(entry.component_id || '').trim()
      ))) {
        setOutput('Välj en befintlig komponent för varje tvetydig matchning.', true);
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
          close('cancel');
        }
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