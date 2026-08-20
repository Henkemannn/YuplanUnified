import { beforeEach, describe, expect, it } from 'vitest';
import fs from 'node:fs';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(code + '\n//# sourceURL=' + relativePath);
}

function loadTemplate(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

function createOpenCloseHelpers() {
  return {
    openSimpleModal(modalId) {
      const modal = document.getElementById(String(modalId || ''));
      if (!modal) {
        return;
      }
      modal.classList.remove('hidden');
      modal.removeAttribute('hidden');
      modal.setAttribute('aria-hidden', 'false');
      modal.style.display = '';
      modal.inert = false;
    },
    closeModalById(modalId) {
      const modal = document.getElementById(String(modalId || ''));
      if (!modal) {
        return;
      }
      modal.classList.add('hidden');
      modal.setAttribute('aria-hidden', 'true');
      modal.style.display = '';
      modal.inert = false;
    },
  };
}

async function waitForTextContent(getValue, expectedText, timeoutMs = 1000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const value = String(getValue() || '');
    if (value.includes(expectedText)) {
      return value;
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  return String(getValue() || '');
}

async function waitForCondition(check, timeoutMs = 1000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    if (check()) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  return check();
}

describe('standalone canonical builder runtime', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    delete window.openBuilderModalForComposition;
    delete window.closeResolveModal;
    delete window.renderBuilderPanel;
  });

  it('boots and runs the canonical Dish + Component flow without builder.js', async () => {
    const compositionHtml = loadTemplate('../../templates/builder/_composition_modal.html');
    const componentHtml = loadTemplate('../../templates/builder/_component_detail_modal.html');

    document.body.innerHTML = [
      '<div id="builderOut"></div>',
      '<div id="componentDetailOut"></div>',
      compositionHtml,
      componentHtml,
    ].join('\n');

    loadScript('../../static/js/builder_component_editor.js');
    loadScript('../../static/js/builder_dish_editor.js');
    loadScript('../../static/js/builder_modal_controller.js');

    expect(typeof window.openBuilderModalForComposition).toBe('undefined');
    expect(document.querySelector('script[src*="builder.js"]')).toBeNull();

    const componentStore = new Map([
      ['linked_component', {
        component_id: 'linked_component',
        component_name: 'Linked Component',
        category: 'main',
        primary_recipe_id: 'recipe-1',
      }],
      ['new_component', {
        component_id: 'new_component',
        component_name: 'New Component',
        category: 'main',
        primary_recipe_id: 'recipe-2',
      }],
    ]);
    const componentDetailsStore = new Map([
      ['linked_component', {
        tags: ['gluten'],
        long_description: 'Standalone linked component',
        recipe_ingredient_rows: [],
        recipe_ingredients_text: '',
        method_text: 'Mix and serve',
        method_notes: '',
        calculation_yield: '4',
        calculation_cost: '12.50',
        calculation_notes: 'Standalone note',
        calculation_rows: [
          {
            ingredient_name: 'Ingredient A',
            amount_value: '2',
            amount_unit: 'g',
            price_value: '3.50',
            price_unit: 'kr/kg',
            calculated_cost: '7.00',
          },
        ],
        allergens: ['milk'],
        allergen_notes: 'Contains milk',
      }],
      ['new_component', {
        tags: ['gluten'],
        long_description: 'New standalone component',
        recipe_ingredient_rows: [],
        recipe_ingredients_text: '',
        method_text: 'Serve chilled',
        method_notes: '',
        calculation_yield: '2',
        calculation_cost: '9.25',
        calculation_notes: 'New component note',
        calculation_rows: [],
        allergens: ['egg'],
        allergen_notes: 'Contains egg',
      }],
    ]);
    const compositionStore = {
      dish_1: {
        composition_id: 'dish_1',
        composition_name: 'Standalone Dish',
        library_group: 'ovrigt',
        components: [
          {
            component_id: 'linked_component',
            component_name: 'Linked Component',
            sort_order: 1,
            role: 'main',
          },
        ],
      },
    };
    const apiCalls = [];
    const attachCalls = [];
    let loadLibraryCalls = 0;
    let refreshCurrentCompositionCalls = 0;
    let forceComponentOverviewSaveFailure = false;

    let controller;

    const callApi = async (url, options = {}) => {
      const method = String(options.method || 'GET').toUpperCase();
      apiCalls.push({ url, method, body: options.body || null });

      if (method === 'GET' && /\/components\/[^/]+\/details$/.test(url)) {
        const componentId = decodeURIComponent(url.split('/components/')[1].split('/details')[0]);
        const details = componentDetailsStore.get(componentId);
        return details
          ? { status: 200, data: { ok: true, component_id: componentId, details } }
          : { status: 404, data: { ok: false, error: 'component not found' } };
      }

      if (method === 'PATCH' && /\/components\/[^/]+\/details$/.test(url)) {
        const componentId = decodeURIComponent(url.split('/components/')[1].split('/details')[0]);
        const nextDetails = { ...(componentDetailsStore.get(componentId) || {}), ...(options.body || {}) };
        componentDetailsStore.set(componentId, nextDetails);
        return { status: 200, data: { ok: true, component_id: componentId, details: nextDetails } };
      }

      if (method === 'PATCH' && /\/components\/[^/]+$/.test(url)) {
        const componentId = decodeURIComponent(url.split('/components/')[1]);
        if (forceComponentOverviewSaveFailure && componentId === 'linked_component') {
          return { status: 500, data: { ok: false, error: 'forced overview failure' } };
        }
        const existing = componentStore.get(componentId) || { component_id: componentId };
        const nextComponent = { ...existing, ...(options.body || {}) };
        componentStore.set(componentId, nextComponent);
        return { status: 200, data: { ok: true, component: nextComponent } };
      }

      if (method === 'PATCH' && /\/compositions\/[^/]+$/.test(url)) {
        const compositionId = decodeURIComponent(url.split('/compositions/')[1]);
        const existing = compositionStore[compositionId];
        if (!existing) {
          return { status: 404, data: { ok: false, error: 'composition not found' } };
        }
        compositionStore[compositionId] = { ...existing, ...(options.body || {}) };
        return { status: 200, data: { ok: true, composition: compositionStore[compositionId] } };
      }

      if (method === 'POST' && /\/compositions\/[^/]+\/components\/attach$/.test(url)) {
        const compositionId = decodeURIComponent(url.split('/compositions/')[1].split('/components/attach')[0]);
        const existing = compositionStore[compositionId];
        const componentId = String(options.body?.component_id || '').trim();
        const component = componentStore.get(componentId);
        if (!existing || !component || !componentId) {
          return { status: 400, data: { ok: false, error: 'attach failed' } };
        }
        attachCalls.push(componentId);
        const nextComponents = Array.isArray(existing.components) ? existing.components.slice() : [];
        if (!nextComponents.some((item) => String(item.component_id || '') === componentId)) {
          nextComponents.push({
            component_id: componentId,
            component_name: component.component_name || componentId,
            sort_order: nextComponents.length + 1,
            role: String(options.body?.role || 'main') || 'main',
          });
        }
        compositionStore[compositionId] = { ...existing, components: nextComponents };
        return { status: 200, data: { ok: true, composition: compositionStore[compositionId] } };
      }

      return { status: 200, data: { ok: true } };
    };

    controller = window.createBuilderModalController({
      compositionRoot: document.getElementById('resolveModal'),
      componentRoot: document.getElementById('componentDetailEditorModal'),
      callApi,
      state: {
        get(key) {
          return this[key];
        },
        set(key, value) {
          this[key] = value;
          return value;
        },
      },
      resolveComponentById(componentId) {
        return componentStore.get(String(componentId || '').trim()) || null;
      },
      attachExistingComponentToCurrentComposition(componentId, compositionId) {
        const currentComposition = controller?.getCurrentComposition();
        const explicitCompositionId = String(compositionId || '').trim();
        const resolvedCompositionId = explicitCompositionId || String(currentComposition?.composition_id || 'dish_1');
        expect(resolvedCompositionId).toBe('dish_1');
        return callApi(
          '/api/builder/compositions/' + encodeURIComponent(resolvedCompositionId) + '/components/attach',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: {
              component_id: String(componentId || ''),
              role: 'main',
            },
          },
        );
      },
      showLoading() {},
      showJson() {},
      openSimpleModal: createOpenCloseHelpers().openSimpleModal,
      closeModalById: createOpenCloseHelpers().closeModalById,
      renderComponentPalette() {},
      dishAllergenLabel(value) {
        return String(value || '').toUpperCase();
      },
      loadLibrary: async () => {
        loadLibraryCalls += 1;
      },
      refreshCurrentCompositionView: async () => {
        refreshCurrentCompositionCalls += 1;
        throw new Error('refresh failed');
      },
      loadCompositionTextPreviewForCurrentComposition: async () => {},
    });

    expect(controller.getCurrentComposition()).toBeNull();

    controller.openComposition(compositionStore.dish_1, 'overview');
    expect(controller.getCurrentComposition()?.composition_id).toBe('dish_1');
    expect(document.getElementById('resolveModal')?.classList.contains('hidden')).toBe(false);
    expect(document.getElementById('resolveModalTitle')?.textContent).toBe('Standalone Dish');

    controller.setDishBuilderTab('allergens');
    await waitForTextContent(() => document.getElementById('dishAllergensSummary')?.textContent, 'Contains milk');
    expect(document.getElementById('dishAllergensSummary')?.textContent).toContain('Contains milk');

    controller.setDishBuilderTab('calculation');
    await waitForTextContent(() => document.getElementById('dishCalculationSummary')?.textContent, 'Standalone note');
    expect(document.getElementById('dishCalculationSummary')?.textContent).toContain('Standalone note');
    expect(document.getElementById('dishCalculationSummary')?.textContent).toContain('12.50 kr');

    const linkedComponentCard = document.querySelector('#builderComponentsList .dish-linked-component-card');
    expect(linkedComponentCard).not.toBeNull();
    const linkedComponentSurface = linkedComponentCard?.querySelector('.builder-component-card-surface');
    expect(linkedComponentSurface).not.toBeNull();
    linkedComponentSurface?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await waitForCondition(() => !document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    expect(document.getElementById('componentDetailEditorModal')?.classList.contains('hidden')).toBe(false);
    expect(document.getElementById('componentDetailEditorTitle')?.textContent).toContain('Linked Component');
    expect(typeof window.openBuilderModalForComposition).toBe('undefined');

    const nameInput = document.getElementById('componentDetailOverviewName');
    const categoryInput = document.getElementById('componentDetailOverviewCategory');
    expect(nameInput).not.toBeNull();
    expect(categoryInput).not.toBeNull();
    nameInput.value = 'Linked Component Edited';
    categoryInput.value = 'sauce';
    document.getElementById('componentDetailSaveChanges')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await Promise.resolve();
    await Promise.resolve();

    expect(apiCalls.some((call) => call.method === 'PATCH' && /\/components\/linked_component$/.test(call.url))).toBe(true);
    expect(apiCalls.some((call) => call.method === 'PATCH' && /\/components\/linked_component\/details$/.test(call.url))).toBe(true);
    expect(loadLibraryCalls).toBe(0);
    expect(refreshCurrentCompositionCalls).toBe(1);
    expect(controller.getState('_componentDetailDirty')).toBe(false);
    expect(controller.getCurrentComposition()?.composition_id).toBe('dish_1');
    expect(controller.getCurrentComposition()?.components?.[0]?.component_id).toBe('linked_component');
    expect(controller.getCurrentComposition()?.components?.[0]?.component_name).toBe('Linked Component Edited');
    expect(controller.getCurrentComposition()?.components?.[0]?.category).toBe('sauce');
    expect(document.querySelector('#builderComponentsList .dish-linked-component-card[data-component-id="linked_component"] .component-library-card-name')?.textContent).toBe('Linked Component Edited');
    expect(document.querySelector('#builderComponentsList .dish-linked-component-card[data-component-id="linked_component"]')?.classList.contains('builder-component-card-theme-sauce')).toBe(true);
    expect(compositionStore.dish_1.components?.[0]?.component_name).toBe('Linked Component');
    expect(document.querySelector('#builderComponentsList .dish-linked-component-card .component-library-card-name')?.textContent).toBe('Linked Component Edited');
    expect(document.querySelector('#builderComponentsList .dish-linked-component-card')?.classList.contains('builder-component-card-theme-sauce')).toBe(true);
    expect(componentStore.size).toBe(2);
    expect(document.getElementById('resolveModal')?.classList.contains('hidden')).toBe(false);

    document.getElementById('componentDetailEditorClose')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await Promise.resolve();
    expect(document.getElementById('componentDetailEditorModal')?.classList.contains('hidden')).toBe(true);
    expect(attachCalls).toHaveLength(0);
    expect(document.getElementById('resolveModal')?.classList.contains('hidden')).toBe(false);

    forceComponentOverviewSaveFailure = true;
    controller.openComponentDetailEditor('linked_component', 'overview');
    await waitForCondition(() => !document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    const failingNameInput = document.getElementById('componentDetailOverviewName');
    expect(failingNameInput).not.toBeNull();
    failingNameInput.value = 'Linked Component Broken Save';
    document.getElementById('componentDetailSaveChanges')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await waitForTextContent(() => document.getElementById('componentDetailOut')?.textContent, 'Could not save changes.');
    expect(document.getElementById('componentDetailOut')?.textContent).toContain('Could not save changes.');
    forceComponentOverviewSaveFailure = false;

    controller.openComponentDetailEditor('new_component', 'overview');
    await waitForCondition(() => !document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    expect(document.getElementById('componentDetailOut')?.textContent).not.toContain('Could not save changes.');
    document.getElementById('componentDetailEditorClose')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await waitForCondition(() => document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    expect(document.getElementById('componentDetailOut')?.textContent || '').toBe('');

    controller.setPendingComponentCreate();
    expect(controller.getState('pendingComponentCreateForCompositionId')).toBe('dish_1');
    controller.openComponentDetailEditor('new_component', 'overview');
    await waitForCondition(() => !document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    expect(document.getElementById('componentDetailReturnToDishBtn')?.classList.contains('hidden')).toBe(true);
    controller.setState('pendingComponentCreateComponentId', 'new_component');
    expect(document.getElementById('componentDetailReturnToDishBtn')?.textContent).toContain('Standalone Dish');
    expect(document.getElementById('componentDetailReturnToDishBtn')?.classList.contains('hidden')).toBe(false);

    document.getElementById('componentDetailEditorClose')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await waitForCondition(() => document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    expect(controller.getState('pendingComponentCreateForCompositionId')).toBeNull();
    expect(controller.getState('pendingComponentCreateComponentId')).toBeNull();
    expect(attachCalls).toHaveLength(0);

    controller.setPendingComponentCreate();
    controller.openComponentDetailEditor('new_component', 'overview');
    await waitForCondition(() => !document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    controller.setState('pendingComponentCreateComponentId', 'new_component');
    expect(document.getElementById('componentDetailReturnToDishBtn')?.classList.contains('hidden')).toBe(false);

    const newComponentName = document.getElementById('componentDetailOverviewName');
    expect(newComponentName).not.toBeNull();
    newComponentName.value = 'New Component Edited';
    document.getElementById('componentDetailSaveChanges')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await waitForCondition(() => controller.getState('_componentDetailDirty') === false);
    await waitForTextContent(() => document.getElementById('componentDetailOut')?.textContent, 'Komponentdetaljer sparade.');

    document.getElementById('componentDetailReturnToDishBtn')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await waitForCondition(() => document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    await waitForCondition(() => document.getElementById('resolveModal')?.classList.contains('hidden') === false);
    expect(attachCalls).toContain('new_component');
    expect(attachCalls).toHaveLength(1);
    expect(controller.getState('pendingComponentCreateForCompositionId')).toBeNull();
    expect(controller.getCurrentComposition()?.components?.some((item) => String(item.component_id || '') === 'new_component')).toBe(true);
    expect(controller.getCurrentComposition()?.composition_id).toBe('dish_1');
    expect(controller.getState('currentBuilderDishTab')).toBe('components');
    expect(compositionStore.dish_1.components.some((item) => String(item.component_id || '') === 'new_component')).toBe(true);
    expect(document.querySelector('#builderComponentsList .dish-linked-component-card[data-component-id="new_component"]')).not.toBeNull();
    expect(controller.getState('pendingComponentCreateForCompositionId')).toBeNull();
    expect(controller.getState('pendingComponentCreateComponentId')).toBeNull();

    const attachCountAfterFirstReturn = attachCalls.length;
    expect(attachCountAfterFirstReturn).toBe(1);

    controller.openComponentDetailEditor('linked_component', 'overview');
    await waitForCondition(() => !document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    expect(document.getElementById('componentDetailReturnToDishBtn')?.classList.contains('hidden')).toBe(true);
    document.getElementById('componentDetailEditorClose')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await waitForCondition(() => document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    expect(attachCalls).toHaveLength(attachCountAfterFirstReturn);

    controller.setPendingComponentCreate();
    expect(controller.getState('pendingComponentCreateForCompositionId')).toBe('dish_1');
    controller.openComponentDetailEditor('new_component', 'overview');
    await waitForCondition(() => !document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    controller.setState('pendingComponentCreateComponentId', 'new_component');
    expect(document.getElementById('componentDetailReturnToDishBtn')?.textContent).toContain('Standalone Dish');

    document.getElementById('componentDetailReturnToDishBtn')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await waitForCondition(() => document.getElementById('componentDetailEditorModal')?.classList.contains('hidden'));
    await waitForCondition(() => document.getElementById('resolveModal')?.classList.contains('hidden') === false);
    expect(attachCalls).toHaveLength(attachCountAfterFirstReturn);
    expect(controller.getState('pendingComponentCreateForCompositionId')).toBeNull();
    expect(controller.getCurrentComposition()?.composition_id).toBe('dish_1');
    expect(controller.getCurrentComposition()?.components?.filter((item) => String(item.component_id || '') === 'new_component')).toHaveLength(1);
    expect(document.querySelector('#builderComponentsList .dish-linked-component-card[data-component-id="new_component"]')).not.toBeNull();

    controller.closeComposition();
    controller.openComposition(compositionStore.dish_1, 'components');
    expect(document.querySelector('#builderComponentsList .dish-linked-component-card[data-component-id="new_component"]')).not.toBeNull();

    document.getElementById('resolveCancel')?.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    await Promise.resolve();
    expect(document.getElementById('resolveModal')?.classList.contains('hidden')).toBe(true);
    expect(controller.getCurrentComposition()).toBeNull();
  });
});
