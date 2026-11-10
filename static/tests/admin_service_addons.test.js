import { describe, expect, it, beforeEach } from 'vitest';
import fs from 'node:fs';

function readStatic(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  return fs.readFileSync(url, 'utf8');
}

function buildFixture() {
  document.body.innerHTML = `
    <dialog id="service-addon-modal">
      <form data-service-addon-form>
        <input name="service_addon_mode">
        <input name="service_addon_action">
        <input name="service_addon_row_id">
        <span data-service-addon-title></span>
        <span data-service-addon-subtitle></span>
        <section data-service-addon-state="add">
          <div data-service-addon-picker>
            <select data-service-addon-family-filter>
              <option value="" selected disabled>Alla kategorier</option>
                <option value="ovrigt">Övrigt</option>
            </select>
            <input data-service-addon-search>
            <div data-service-addon-option-list role="listbox"></div>
          </div>
          <div data-service-addon-selected hidden>
            <strong data-service-addon-selected-name></strong>
            <span data-service-addon-selected-family></span>
            <button type="button" data-service-addon-change-selection>Ändra</button>
          </div>
          <select name="service_addon_id" data-service-addon-select>
            <option value="" selected disabled>Välj serveringsanpassning</option>
            <option value="addon-1" data-service-addon-family="ovrigt">Extra sås</option>
            <option value="addon-2" data-service-addon-family="mos">Mos istället för potatis</option>
          </select>
          <input type="radio" name="service_scope" value="all_services" checked>
          <input type="radio" name="service_scope" value="lunch">
          <input type="radio" name="service_scope" value="dinner">
          <input type="radio" name="quantity_mode" value="whole_department" checked>
          <input type="radio" name="quantity_mode" value="custom">
          <div data-service-addon-whole-department-help></div>
          <div data-service-addon-quantity-panel>
            <div data-service-addon-count-field="lunch"><input name="service_addon_lunch_count"></div>
            <div data-service-addon-count-field="dinner"><input name="service_addon_dinner_count"></div>
          </div>
          <textarea name="service_addon_note"></textarea>
          <button type="button" data-service-addon-switch-create>+ Skapa ny serveringsanpassning</button>
        </section>
        <section data-service-addon-state="create" hidden>
          <input name="service_addon_new_name">
          <p data-service-addon-duplicate-status hidden></p>
          <button type="button" data-service-addon-use-existing hidden></button>
          <select name="service_addon_family" data-service-addon-family-select>
            <option value="ovrigt" selected>Övrigt</option>
            <option value="__custom__">+ Skapa ny familj…</option>
          </select>
          <div data-service-addon-family-custom hidden>
            <input name="service_addon_family_custom">
          </div>
          <input type="radio" name="service_scope" value="all_services" checked>
          <input type="radio" name="service_scope" value="lunch">
          <input type="radio" name="service_scope" value="dinner">
          <input type="radio" name="quantity_mode" value="whole_department" checked>
          <input type="radio" name="quantity_mode" value="custom">
          <div data-service-addon-whole-department-help></div>
          <div data-service-addon-quantity-panel>
            <div data-service-addon-count-field="lunch"><input name="service_addon_lunch_count"></div>
            <div data-service-addon-count-field="dinner"><input name="service_addon_dinner_count"></div>
          </div>
          <textarea name="service_addon_note"></textarea>
        </section>
        <section data-service-addon-state="edit" hidden>
          <input type="radio" name="service_scope" value="all_services" checked>
          <input type="radio" name="service_scope" value="lunch">
          <input type="radio" name="service_scope" value="dinner">
          <input type="radio" name="quantity_mode" value="whole_department" checked>
          <input type="radio" name="quantity_mode" value="custom">
          <div data-service-addon-whole-department-help></div>
          <div data-service-addon-quantity-panel>
            <div data-service-addon-count-field="lunch"><input name="service_addon_lunch_count"></div>
            <div data-service-addon-count-field="dinner"><input name="service_addon_dinner_count"></div>
          </div>
          <textarea name="service_addon_note"></textarea>
        </section>
        <section data-service-addon-state="remove" hidden></section>
      </form>
    </dialog>
  `;
}

function dispatchClick(element) {
  element.dispatchEvent(new MouseEvent('click', { bubbles: true }));
}

function dispatchChange(element) {
  element.dispatchEvent(new Event('change', { bubbles: true }));
}

function dispatchInput(element) {
  element.dispatchEvent(new Event('input', { bubbles: true }));
}

describe('admin service addon modal lifecycle', () => {
  beforeEach(() => {
    buildFixture();
    window.eval(readStatic('../js/admin_service_addons.js'));
  });

  it('initializes without ReferenceError and opens the create state', () => {
    const dialog = document.querySelector('#service-addon-modal');
    const addState = document.querySelector('section[data-service-addon-state="add"]');
    const createState = document.querySelector('section[data-service-addon-state="create"]');

    expect(dialog.dataset.serviceAddonState).toBe('add');
    expect(addState.hidden).toBe(false);
    expect(createState.hidden).toBe(true);

    dispatchClick(document.querySelector('[data-service-addon-switch-create]'));

    expect(dialog.dataset.serviceAddonState).toBe('create');
    expect(addState).toHaveAttribute('hidden');
    expect(createState).not.toHaveAttribute('hidden');
  });

  it('supports custom families and quantity scope controls', () => {
    const familySelect = document.querySelector('section[data-service-addon-state="create"] [data-service-addon-family-select]');
    const familyCustom = document.querySelector('section[data-service-addon-state="create"] [data-service-addon-family-custom]');
    const quantityCustom = document.querySelector('section[data-service-addon-state="create"] input[name="quantity_mode"][value="custom"]');
    const lunchScope = document.querySelector('section[data-service-addon-state="create"] input[name="service_scope"][value="lunch"]');
    const quantityPanel = document.querySelector('section[data-service-addon-state="create"] [data-service-addon-quantity-panel]');
    const dinnerField = document.querySelector('section[data-service-addon-state="create"] [data-service-addon-count-field="dinner"]');

    dispatchClick(document.querySelector('[data-service-addon-switch-create]'));
    familySelect.value = '__custom__';
    dispatchChange(familySelect);
    expect(familySelect.hidden).toBe(true);
    expect(familyCustom.hidden).toBe(false);

    quantityCustom.checked = true;
    dispatchChange(quantityCustom);
    expect(quantityPanel.hidden).toBe(false);

    lunchScope.checked = true;
    dispatchChange(lunchScope);
    expect(dinnerField.hidden).toBe(true);
    expect(dinnerField.querySelector('input').disabled).toBe(true);
  });

  it('shows duplicate warning and can select the existing catalog item', () => {
    const createName = document.querySelector('section[data-service-addon-state="create"] input[name="service_addon_new_name"]');
    const warning = document.querySelector('[data-service-addon-duplicate-status]');
    const useExisting = document.querySelector('[data-service-addon-use-existing]');
    const addSelect = document.querySelector('[data-service-addon-select]');

    dispatchClick(document.querySelector('[data-service-addon-switch-create]'));
    createName.value = 'Extra sås';
    dispatchInput(createName);

    expect(warning.hidden).toBe(false);
    expect(useExisting.hidden).toBe(false);
    expect(useExisting.dataset.serviceAddonExistingId).toBe('addon-1');

    dispatchClick(useExisting);

    expect(document.querySelector('section[data-service-addon-state="add"]').hidden).toBe(false);
    expect(addSelect.value).toBe('addon-1');
    expect(document.querySelector('[data-service-addon-selected]').hidden).toBe(false);
    expect(document.querySelector('[data-service-addon-selected-name]').textContent).toBe('Extra sås');
  });

  it('opens the existing-option chooser directly from create state without a match', () => {
    const addState = document.querySelector('section[data-service-addon-state="add"]');
    const createState = document.querySelector('section[data-service-addon-state="create"]');
    const useExisting = document.querySelector('[data-service-addon-use-existing]');
    const optionRows = document.querySelectorAll('[data-service-addon-option-row]');

    dispatchClick(document.querySelector('[data-service-addon-switch-create]'));
    expect(useExisting.hidden).toBe(false);
    dispatchClick(useExisting);

    expect(createState.hidden).toBe(true);
    expect(addState.hidden).toBe(false);
    expect(optionRows.length).toBe(2);
    expect(document.querySelector('[data-service-addon-option-row="addon-1"]')).not.toBeNull();
  });

  it('shows all existing options directly and supports search, family filter, and row selection', () => {
    const optionList = document.querySelector('[data-service-addon-option-list]');
    const search = document.querySelector('[data-service-addon-search]');
    const familyFilter = document.querySelector('[data-service-addon-family-filter]');
    const addSelect = document.querySelector('[data-service-addon-select]');

    expect(optionList.querySelectorAll('[data-service-addon-option-row]').length).toBe(2);

    search.value = 'mos';
    dispatchInput(search);
    expect(optionList.querySelectorAll('[data-service-addon-option-row]').length).toBe(1);
    expect(optionList.textContent).toContain('Mos istället för potatis');

    search.value = '';
    familyFilter.value = 'ovrigt';
    dispatchChange(familyFilter);
    expect(optionList.querySelectorAll('[data-service-addon-option-row]').length).toBe(1);

    dispatchClick(optionList.querySelector('[data-service-addon-option-row="addon-1"]'));
    expect(addSelect.value).toBe('addon-1');
    expect(optionList.querySelector('[data-service-addon-option-row="addon-1"]').getAttribute('aria-selected')).toBe('true');
  });

  it('collapses the picker into a selected summary and can reopen it', () => {
    const picker = document.querySelector('[data-service-addon-picker]');
    const selected = document.querySelector('[data-service-addon-selected]');
    const selectedName = document.querySelector('[data-service-addon-selected-name]');
    const selectedFamily = document.querySelector('[data-service-addon-selected-family]');
    const optionRow = document.querySelector('[data-service-addon-option-row="addon-1"]');

    dispatchClick(optionRow);

    expect(picker.hidden).toBe(true);
    expect(selected.hidden).toBe(false);
    expect(selectedName.textContent).toBe('Extra sås');
    expect(selectedFamily.textContent).toBe('Övrigt');
    expect(document.querySelector('[data-service-addon-select]').value).toBe('addon-1');

    dispatchClick(document.querySelector('[data-service-addon-change-selection]'));
    expect(picker.hidden).toBe(false);
    expect(selected.hidden).toBe(true);
    expect(document.querySelector('[data-service-addon-option-row="addon-1"]').getAttribute('aria-selected')).toBe('true');
  });
});
