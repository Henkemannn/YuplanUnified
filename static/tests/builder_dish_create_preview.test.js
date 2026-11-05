import { afterEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(`${code}\n//# sourceURL=${relativePath}`);
}

function previewResponse(suggestions) {
  return {
    status: 200,
    json: async () => ({ ok: true, suggestions }),
  };
}

describe('BuilderDishCreateModal component preview', () => {
  afterEach(() => {
    vi.useRealTimers();
    delete window.BuilderDishCreateModal;
    delete window.fetch;
    document.body.innerHTML = '';
  });

  function renderModal() {
    document.body.innerHTML = `
      <div id="quickCreateModal" hidden>
        <h3 id="quickCreateModalTitle"></h3>
        <input id="freeDishName">
        <select id="freeDishCategory"><option value="ovrigt">Övrigt</option></select>
        <button id="btnCreateDish">Skapa rätt</button>
        <button id="quickCreateModalClose">Avbryt</button>
        <div id="createDishOut"></div>
        <div id="createDishPreview" hidden></div>
      </div>
    `;
    loadScript('../../static/js/builder_dish_create.js');
  }

  it('ignores stale preview responses and renders match states', async () => {
    vi.useFakeTimers();
    renderModal();
    const pending = {};
    window.fetch = vi.fn((url, options) => {
      const name = JSON.parse(options.body).dish_name;
      return new Promise((resolve) => {
        pending[name] = resolve;
      });
    });

    window.BuilderDishCreateModal.open({
      previewEndpoint: '/api/builder/components/preview',
      initialName: 'Old dish',
    });
    await vi.advanceTimersByTimeAsync(250);

    const input = document.getElementById('freeDishName');
    input.value = 'New dish';
    input.dispatchEvent(new Event('input'));
    await vi.advanceTimersByTimeAsync(250);

    pending['Old dish'](previewResponse([
      { suggested_name: 'Old component', resolution: 'new', reusable: false, match: { status: 'no_match' } },
    ]));
    pending['New dish'](previewResponse([
      {
        suggested_name: 'New component',
        resolution: 'reusable',
        reusable: true,
        match: { status: 'alias_match', component_name: 'Existing component' },
      },
      {
        suggested_name: 'Maybe component',
        resolution: 'ambiguous',
        reusable: false,
        match: { status: 'possible_match', possible_matches: [{ component_name: 'Candidate' }] },
      },
    ]));
    await vi.runAllTimersAsync();

    const preview = document.getElementById('createDishPreview');
    expect(preview.textContent).toContain('New component');
    expect(preview.textContent).toContain('aliasmatchning');
    expect(preview.textContent).toContain('Tvetydig');
    expect(preview.textContent).not.toContain('Old component');
  });

  it('keeps creation available when preview fails', async () => {
    renderModal();
    const onSuccess = vi.fn();
    window.fetch = vi.fn(async (url, options) => {
      if (String(url).includes('/preview')) {
        throw new Error('preview unavailable');
      }
      expect(JSON.parse(options.body)).toEqual({
        composition_name: 'Dish name',
        library_group: 'ovrigt',
        seed_components: false,
      });
      return {
        status: 201,
        json: async () => ({ ok: true, composition: { composition_id: 'dish-1' } }),
      };
    });

    window.BuilderDishCreateModal.open({
      previewEndpoint: '/api/builder/components/preview',
      createEndpoint: '/api/builder/compositions/site',
      initialName: 'Dish name',
      onSuccess,
    });
    await new Promise((resolve) => setTimeout(resolve, 300));

    document.getElementById('btnCreateDish').click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(onSuccess).toHaveBeenCalledWith({ composition_id: 'dish-1' }, expect.any(Object));
    expect(document.getElementById('createDishPreview').textContent).toContain('kunde inte laddas');
  });

  it('submits reviewed component choices to the atomic endpoint', async () => {
    renderModal();
    let savedBody = null;
    window.fetch = vi.fn(async (url, options) => {
      if (String(url).includes('/preview')) {
        return previewResponse([
          {
            suggested_name: 'Edited component',
            resolution: 'new',
            reusable: false,
            match: { status: 'no_match' },
          },
          {
            suggested_name: 'Ambiguous component',
            resolution: 'ambiguous',
            reusable: false,
            match: {
              status: 'possible_match',
              possible_matches: [
                { component_id: 'component-1', component_name: 'Existing component' },
              ],
            },
          },
        ]);
      }
      savedBody = JSON.parse(options.body);
      return {
        status: 201,
        json: async () => ({
          ok: true,
          composition: { composition_id: 'dish-1' },
        }),
      };
    });

    const onSuccess = vi.fn();
    window.BuilderDishCreateModal.open({
      createEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      reviewEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      menuDetailId: 'detail-1',
      previewEndpoint: '/api/builder/components/preview',
      initialName: 'Dish name',
      onSuccess,
    });
    await new Promise((resolve) => setTimeout(resolve, 300));

    const preview = document.getElementById('createDishPreview');
    const ambiguousSelect = preview.querySelectorAll('select')[1];
    ambiguousSelect.value = 'component-1';
    ambiguousSelect.dispatchEvent(new Event('change'));
    const firstInput = preview.querySelector('li input');
    firstInput.value = 'Edited component name';
    firstInput.dispatchEvent(new Event('input'));
    preview.querySelector('li button').click();

    document.getElementById('btnCreateDish').click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(savedBody.menu_detail_id).toBe('detail-1');
    expect(savedBody.idempotency_key).toEqual(expect.any(String));
    expect(savedBody.components).toEqual([
      { name: 'Ambiguous component', component_id: 'component-1' },
    ]);
    expect(onSuccess).toHaveBeenCalled();
  });

  it('does not fall back to an empty atomic dish when preview fails', async () => {
    renderModal();
    const onSuccess = vi.fn();
    window.fetch = vi.fn(async (url) => {
      if (String(url).includes('/preview')) {
        throw new Error('preview unavailable');
      }
      throw new Error('atomic endpoint must not be called');
    });

    window.BuilderDishCreateModal.open({
      createEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      reviewEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      menuDetailId: 'detail-1',
      previewEndpoint: '/api/builder/components/preview',
      initialName: 'Dish name',
      onSuccess,
    });
    await new Promise((resolve) => setTimeout(resolve, 300));
    document.getElementById('btnCreateDish').click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(onSuccess).not.toHaveBeenCalled();
    expect(document.getElementById('createDishOut').textContent).toContain('kunde inte laddas');
  });
});
