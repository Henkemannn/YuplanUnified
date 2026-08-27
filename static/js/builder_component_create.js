(function () {
  'use strict';

  const state = {
    bound: false,
    modal: null,
    title: null,
    nameInput: null,
    submitButton: null,
    closeButton: null,
    output: null,
    config: null,
    submitting: false,
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

  function setSubmitting(isSubmitting) {
    state.submitting = Boolean(isSubmitting);
    if (state.submitButton) {
      state.submitButton.disabled = Boolean(isSubmitting);
      state.submitButton.textContent = isSubmitting ? 'Skapar…' : 'Skapa komponent';
    }
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

    const componentName = String(state.nameInput ? state.nameInput.value : '').trim();
    if (!componentName) {
      setOutput('Komponentnamn måste anges.', true);
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

    const payload = { component_name: componentName };
    if (state.config.category !== undefined && state.config.category !== null && String(state.config.category).trim()) {
      payload.category = String(state.config.category).trim();
    }

    setSubmitting(true);
    setOutput('Skapar...');

    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify(payload),
      });
      const data = await response
        .json()
        .catch(() => ({ ok: false, error: 'invalid_json_response', message: 'Response was not valid JSON' }));
      const result = { status: response.status, data };
      if (!(response.status < 400 && data && data.ok && data.component)) {
        setOutput(String(data && data.message || data && data.error || 'Kunde inte skapa komponent.'), true);
        return;
      }

      hideModal();
      setOutput('', false);
      if (typeof state.config.onSuccess === 'function') {
        await state.config.onSuccess(data.component, result);
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
    state.modal = getElement(state.config.modalId || 'componentCreateModal');
    state.title = getElement(state.config.titleId || 'componentCreateModalTitle');
    state.nameInput = getElement(state.config.nameInputId || 'freeComponentName');
    state.submitButton = getElement(state.config.submitButtonId || 'btnCreateComponent');
    state.closeButton = getElement(state.config.closeButtonId || 'componentCreateModalClose');
    state.output = getElement(state.config.outputId || 'createComponentOut');

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
    if (state.title && state.config.title) {
      state.title.textContent = String(state.config.title);
    }
    if (state.nameInput) {
      state.nameInput.value = '';
    }
    setOutput('', false);
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

  globalThis.BuilderComponentCreateModal = api;
})();