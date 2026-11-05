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
        const request = JSON.parse(options.body);
        if (request.component_name) {
          return previewResponse([
            {
              suggested_name: request.component_name,
              resolution: 'new',
              reusable: false,
              match: { status: 'no_match' },
            },
          ]);
        }
        return previewResponse([
          {
            suggested_name: 'Edited component',
            resolution: 'reusable',
            reusable: true,
            match: { status: 'exact_match', component_id: 'component-original', component_name: 'Existing component' },
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
    expect(preview.textContent).toContain('Finns i komponentbiblioteket');
    expect(preview.textContent).toContain('Flera möjliga matchningar');

    const firstMenu = preview.querySelectorAll('details')[0];
    firstMenu.querySelector('summary').click();
    [...firstMenu.querySelectorAll('button')]
      .find((button) => button.textContent === 'Ändra')
      .click();
    const firstInput = preview.querySelector('.create-dish-component-inline-editor input');
    firstInput.value = 'Edited component name';
    firstInput.parentElement.querySelector('button').click();

    const firstVariantMenu = preview.querySelectorAll('details')[0];
    firstVariantMenu.querySelector('summary').click();
    [...firstVariantMenu.querySelectorAll('button')]
      .find((button) => button.textContent === 'Skapa ny variant')
      .click();
    preview.querySelector('.create-dish-component-inline-editor input').value = 'Edited component name';
    preview.querySelector('.create-dish-component-inline-editor button').click();

    const ambiguousMenu = preview.querySelectorAll('details')[1];
    ambiguousMenu.querySelector('summary').click();
    [...ambiguousMenu.querySelectorAll('button')]
      .find((button) => button.textContent === 'Byt / välj befintlig')
      .click();
    const ambiguousSelect = preview.querySelector('select');
    ambiguousSelect.value = 'component-1';
    ambiguousSelect.dispatchEvent(new Event('change'));

    document.getElementById('btnCreateDish').click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(savedBody.menu_detail_id).toBe('detail-1');
    expect(savedBody.idempotency_key).toEqual(expect.any(String));
    expect(savedBody.components).toEqual([
      { name: 'Edited component name', selection: 'new' },
      { name: 'Existing component', selection: 'reuse', component_id: 'component-1' },
    ]);
    expect(onSuccess).toHaveBeenCalled();
  });

  it('submits an edited unmatched component as a new component', async () => {
    renderModal();
    let savedBody = null;
    window.fetch = vi.fn(async (url, options) => {
      if (String(url).includes('/preview')) {
        const request = JSON.parse(options.body);
        if (request.component_name) {
          return previewResponse([{
            suggested_name: request.component_name,
            resolution: 'new',
            reusable: false,
            match: { status: 'no_match' },
          }]);
        }
        return previewResponse([
          {
            suggested_name: 'Existing component',
            resolution: 'reusable',
            reusable: true,
            match: {
              status: 'exact_match',
              component_id: 'component-1',
              component_name: 'Existing component',
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

    window.BuilderDishCreateModal.open({
      createEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      reviewEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      menuDetailId: 'detail-1',
      previewEndpoint: '/api/builder/components/preview',
      initialName: 'Dish name',
    });
    await new Promise((resolve) => setTimeout(resolve, 300));

    const preview = document.getElementById('createDishPreview');
    const menu = preview.querySelector('details');
    menu.querySelector('summary').click();
    [...menu.querySelectorAll('button')]
      .find((button) => button.textContent === 'Ändra')
      .click();
    const input = preview.querySelector('.create-dish-component-inline-editor input');
    input.value = 'New component variant';
    input.parentElement.querySelector('button').click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(preview.textContent).toContain('Ny komponent');
    document.getElementById('btnCreateDish').click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(savedBody.components).toEqual([
      { name: 'New component variant', selection: 'new' },
    ]);
  });

  it('re-matches edited names for aliases and ambiguous results', async () => {
    renderModal();
    let savedBody = null;
    window.fetch = vi.fn(async (url, options) => {
      const request = JSON.parse(options.body);
      if (request.component_name === 'Alias name') {
        return previewResponse([{
          suggested_name: 'Alias name',
          resolution: 'reusable',
          match: {
            status: 'alias_match',
            component_id: 'component-alias',
            component_name: 'Canonical component',
          },
        }]);
      }
      if (request.component_name === 'Ambiguous name') {
        return previewResponse([{
          suggested_name: 'Ambiguous name',
          resolution: 'ambiguous',
          match: {
            status: 'possible_match',
            possible_matches: [
              { component_id: 'component-1', component_name: 'Candidate 1' },
              { component_id: 'component-2', component_name: 'Candidate 2' },
            ],
          },
        }]);
      }
      if (String(url).includes('/preview')) {
        return previewResponse([{
          suggested_name: 'Original component',
          resolution: 'reusable',
          match: {
            status: 'exact_match',
            component_id: 'component-original',
            component_name: 'Original component',
          },
        }]);
      }
      savedBody = JSON.parse(options.body);
      return {
        status: 201,
        json: async () => ({ ok: true, composition: { composition_id: 'dish-1' } }),
      };
    });

    window.BuilderDishCreateModal.open({
      createEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      reviewEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      menuDetailId: 'detail-1',
      previewEndpoint: '/api/builder/components/preview',
      initialName: 'Dish name',
    });
    await new Promise((resolve) => setTimeout(resolve, 300));

    const preview = document.getElementById('createDishPreview');
    const openEditor = async (value) => {
      const menu = preview.querySelector('details');
      menu.querySelector('summary').click();
      [...menu.querySelectorAll('button')]
        .find((button) => button.textContent === 'Ändra')
        .click();
      const input = preview.querySelector('.create-dish-component-inline-editor input');
      input.value = value;
      input.parentElement.querySelector('button').click();
      await new Promise((resolve) => setTimeout(resolve, 0));
    };

    await openEditor('Alias name');
    expect(preview.textContent).toContain('Finns i komponentbiblioteket');

    await openEditor('Ambiguous name');
    expect(preview.textContent).toContain('Flera möjliga matchningar');
    document.getElementById('btnCreateDish').click();
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(savedBody).toBeNull();
    expect(document.getElementById('createDishOut').textContent)
      .toContain('Välj befintlig komponent eller skapa ny variant');
  });

  it('ignores stale rematch results and preserves an explicit new variant', async () => {
    renderModal();
    const pending = {};
    window.fetch = vi.fn((url, options) => {
      const request = JSON.parse(options.body);
      if (request.component_name) {
        return new Promise((resolve) => {
          pending[request.component_name] = resolve;
        });
      }
      return Promise.resolve(previewResponse([{
        suggested_name: 'Original component',
        resolution: 'reusable',
        match: {
          status: 'exact_match',
          component_id: 'component-original',
          component_name: 'Original component',
        },
      }]));
    });

    let savedBody = null;
    window.BuilderDishCreateModal.open({
      createEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      reviewEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      menuDetailId: 'detail-1',
      previewEndpoint: '/api/builder/components/preview',
      initialName: 'Dish name',
    });
    await new Promise((resolve) => setTimeout(resolve, 300));

    const preview = document.getElementById('createDishPreview');
    const menu = preview.querySelector('details');
    menu.querySelector('summary').click();
    [...menu.querySelectorAll('button')]
      .find((button) => button.textContent === 'Ändra')
      .click();
    const input = preview.querySelector('.create-dish-component-inline-editor input');
    input.value = 'Older name';
    input.parentElement.querySelector('button').click();
    await Promise.resolve();

    const updatedMenu = preview.querySelector('details');
    updatedMenu.querySelector('summary').click();
    [...updatedMenu.querySelectorAll('button')]
      .find((button) => button.textContent === 'Ändra')
      .click();
    const updatedInput = preview.querySelector('.create-dish-component-inline-editor input');
    updatedInput.value = 'New variant';
    updatedInput.parentElement.querySelector('button').click();
    const variantMenu = preview.querySelector('details');
    variantMenu.querySelector('summary').click();
    [...variantMenu.querySelectorAll('button')]
      .find((button) => button.textContent === 'Skapa ny variant')
      .click();
    preview.querySelector('.create-dish-component-inline-editor input').value = 'New variant';
    preview.querySelector('.create-dish-component-inline-editor button').click();

    pending['Older name'](previewResponse([{
      suggested_name: 'Older name',
      resolution: 'reusable',
      match: { status: 'exact_match', component_id: 'stale-id' },
    }]));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(preview.textContent).toContain('Ny komponent');
    expect(savedBody).toBeNull();
  });

  it('removes a component through the overflow menu and resets rows on reopen', async () => {
    renderModal();
    window.fetch = vi.fn(async (url) => {
      if (String(url).includes('/preview')) {
        return previewResponse([
          {
            suggested_name: 'Existing component',
            resolution: 'reusable',
            reusable: true,
            match: { status: 'exact_match', component_id: 'component-1', component_name: 'Existing component' },
          },
          {
            suggested_name: 'New component',
            resolution: 'new',
            reusable: false,
            match: { status: 'no_match' },
          },
        ]);
      }
      return {
        status: 201,
        json: async () => ({ ok: true, composition: { composition_id: 'dish-1' } }),
      };
    });

    window.BuilderDishCreateModal.open({
      createEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      reviewEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      menuDetailId: 'detail-1',
      previewEndpoint: '/api/builder/components/preview',
      initialName: 'Dish name',
    });
    await new Promise((resolve) => setTimeout(resolve, 300));

    const preview = document.getElementById('createDishPreview');
    const firstMenu = preview.querySelectorAll('details')[0];
    firstMenu.querySelector('summary').click();
    [...firstMenu.querySelectorAll('button')]
      .find((button) => button.textContent === 'Ta bort från rätten')
      .click();
    expect(preview.textContent).not.toContain('Existing component');
    expect(preview.textContent).toContain('New component');

    window.BuilderDishCreateModal.close();
    window.BuilderDishCreateModal.open({
      createEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      reviewEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      menuDetailId: 'detail-1',
      previewEndpoint: '/api/builder/components/preview',
      initialName: 'Dish name',
    });
    await new Promise((resolve) => setTimeout(resolve, 300));
    expect(document.querySelectorAll('.create-dish-component-row')).toHaveLength(2);
  });

  it('closes the overflow menu on outside click and Escape', async () => {
    renderModal();
    window.fetch = vi.fn(async () => previewResponse([
      {
        suggested_name: 'Long component name that remains readable',
        resolution: 'new',
        reusable: false,
        match: { status: 'no_match' },
      },
    ]));

    window.BuilderDishCreateModal.open({
      createEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      reviewEndpoint: '/api/builder/menus/menu-1/create-reviewed-composition',
      menuDetailId: 'detail-1',
      previewEndpoint: '/api/builder/components/preview',
      initialName: 'Dish name',
    });
    await new Promise((resolve) => setTimeout(resolve, 300));

    const details = document.querySelector('.create-dish-component-overflow');
    details.querySelector('summary').click();
    expect(details.open).toBe(true);
    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(details.open).toBe(false);

    details.querySelector('summary').click();
    expect(details.open).toBe(true);
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(details.open).toBe(false);
  });

  it('creates a custom dish category inline and selects it', async () => {
    renderModal();
    window.fetch = vi.fn(async (url, options = {}) => {
      if (String(url).includes('/dish-categories')) {
        if (options.method === 'POST') {
          return {
            status: 201,
            json: async () => ({
              ok: true,
              category: { key: 'dishcat_theme', label: 'Temavecka' },
            }),
          };
        }
        return {
          status: 200,
          json: async () => ({
            ok: true,
            categories: [
              { key: 'ovrigt', label: 'Övrigt' },
              { key: 'fisk', label: 'Fisk' },
            ],
          }),
        };
      }
      return previewResponse([]);
    });

    window.BuilderDishCreateModal.open({
      categoryEndpoint: '/api/builder/dish-categories',
      previewEndpoint: '/api/builder/components/preview',
      initialName: 'Dish name',
    });
    await new Promise((resolve) => setTimeout(resolve, 300));

    const category = document.getElementById('freeDishCategory');
    category.value = '__new_dish_category__';
    category.dispatchEvent(new Event('change'));
    const editor = document.querySelector('.create-dish-category-inline-editor');
    editor.querySelector('input').value = 'Temavecka';
    editor.querySelector('button').click();
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(category.value).toBe('dishcat_theme');
    expect(category.options[category.selectedIndex].textContent).toBe('Temavecka');
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
