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

    setSubmitting(true);
    setOutput('Skapar...');

    try {
      const requestBody = {
        composition_name: name,
        library_group: libraryGroup,
      };
      if (state.config.includeSeedComponents !== false) {
        requestBody.seed_components = false;
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
    resetFields();
    if (state.title && state.config.title) {
      state.title.textContent = String(state.config.title);
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

  globalThis.BuilderDishCreateModal = api;
})();