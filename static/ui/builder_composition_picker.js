(function () {
  'use strict';

  function normalize(value) {
    return String(value || '').trim();
  }

  function init() {
    const searchInput = document.querySelector('[data-composition-picker-search]') || document.getElementById('compositionPickerSearch');
    const resultsRoot = document.querySelector('[data-composition-picker-results]');
    const statusRoot = document.querySelector('[data-composition-picker-status]');
    const createButton = document.querySelector('[data-composition-picker-create]');
    const closeButtons = document.querySelectorAll('[data-composition-picker-close]');
    if (!searchInput || !resultsRoot || !statusRoot) {
      throw new Error('Composition picker controls are missing.');
    }

    const initialName = normalize(new URL(window.location.href).searchParams.get('initial_name'));
    const url = new URL(window.location.href);
    const createOnly = url.searchParams.get('create') === '1';
    const editAfterCreate = url.searchParams.get('edit_after_create') === '1';
    const state = {
      compositions: [],
      query: initialName,
    };

    function setStatus(message, isError) {
      statusRoot.textContent = String(message || '');
      statusRoot.dataset.state = isError ? 'error' : 'idle';
    }

    function sendToParent(type, detail) {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ type, detail }, window.location.origin);
      }
    }

    function closePicker() {
      sendToParent('menu-picker-close', {});
    }

    function selectComposition(compositionId) {
      const id = normalize(compositionId);
      if (!id) {
        return;
      }
      sendToParent('menu-picker-selected', { composition_id: id });
    }

    function renderResults() {
      resultsRoot.replaceChildren();
      const query = normalize(state.query);
      if (!query) {
        setStatus('Sök efter en rätt.');
        return;
      }

      const filtered = globalThis.BuilderCompositionSearchRuntime.filterCompositionsBySearch(
        state.compositions,
        query,
      );
      if (!filtered.length) {
        const empty = document.createElement('div');
        empty.className = 'builder-composition-picker__empty';
        empty.textContent = 'Inga rätter matchar sökningen.';
        resultsRoot.appendChild(empty);
        setStatus('Prova en bredare sökning.');
        return;
      }

      const fragment = document.createDocumentFragment();
      for (const composition of filtered.slice(0, 80)) {
        const compositionId = normalize(composition && composition.composition_id);
        if (!compositionId) {
          continue;
        }
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'builder-composition-picker__result';
        button.textContent = normalize(composition.composition_name) || compositionId;
        button.addEventListener('click', () => selectComposition(compositionId));
        fragment.appendChild(button);
      }
      resultsRoot.appendChild(fragment);
      setStatus(filtered.length > 80
        ? 'Visar 80 av ' + String(filtered.length) + ' rätter.'
        : 'Välj en rätt eller skapa en ny.');
    }

    async function loadCompositions() {
      setStatus('Laddar rättbiblioteket…');
      const response = await fetch('/api/builder/compositions', {
        method: 'GET',
        credentials: 'same-origin',
      });
      let data;
      try {
        data = await response.json();
      } catch (error) {
        throw new Error('Rättbiblioteket svarade med ogiltig data.');
      }
      if (!(response.ok && data && data.ok && Array.isArray(data.compositions))) {
        throw new Error(String(data && (data.message || data.error) || 'Kunde inte läsa rättbiblioteket.'));
      }
      state.compositions = data.compositions;
      renderResults();
    }

    searchInput.value = state.query;
    searchInput.addEventListener('input', () => {
      state.query = searchInput.value;
      renderResults();
    });
    closeButtons.forEach((button) => button.addEventListener('click', closePicker));
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closePicker();
      }
    });

    function openCreateFlow() {
      if (!globalThis.BuilderDishCreateModal || typeof globalThis.BuilderDishCreateModal.open !== 'function') {
        setStatus('Skapa rätt-flödet är inte tillgängligt.', true);
        return;
      }
      globalThis.BuilderDishCreateModal.open({
        title: 'Skapa rätt',
        createEndpoint: '/api/builder/compositions/private',
        includeSeedComponents: false,
        initialName: state.query,
        onSuccess(composition) {
          const id = normalize(composition && composition.composition_id);
          selectComposition(id);
          if (editAfterCreate && id) {
            window.location.replace('/builder-editor-host?composition_id=' + encodeURIComponent(id));
          }
        },
        onCancel() {
          if (createOnly) {
            closePicker();
          }
        },
      });
    }

    if (createButton) {
      createButton.addEventListener('click', openCreateFlow);
    }

    if (createOnly) {
      openCreateFlow();
    } else {
      loadCompositions().catch((error) => setStatus(error.message, true));
      searchInput.focus();
    }
  }

  document.addEventListener('DOMContentLoaded', init);
})();
