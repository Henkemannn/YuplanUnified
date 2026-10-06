import fs from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(code + '\n//# sourceURL=' + relativePath);
}

function renderNeedModalDom() {
  document.body.innerHTML = `
    <dialog id="need-modal" class="ua-modal admin-need-modal">
      <div class="ua-modal-inner">
        <form method="POST" action="/ui/admin/departments/demo/requirement-groups" class="admin-need-modal__form admin-need-modal__edit-form">
          <input type="hidden" name="csrf_token" value="csrf-token">
          <input type="hidden" name="group_id" value="">
          <header class="ua-modal-header admin-need-modal__header">
            <div>
              <h2 class="admin-need-modal__title" data-need-modal-title>Lägg till behov</h2>
              <p class="admin-need-modal__subtitle" data-need-modal-subtitle>Vilket behov gäller på den här avdelningen?</p>
            </div>
            <button type="button" class="ua-modal-close" data-modal-close aria-label="Stäng">×</button>
          </header>

          <div class="ua-modal-body admin-need-modal__body">
            <div class="admin-need-modal__row">
              <label class="admin-need-modal__label" for="need-modal-primary-requirement-id">Vilket behov gäller?</label>
              <div class="admin-need-modal__control">
                <select id="need-modal-primary-requirement-id" name="primary_requirement_id" class="yp-input">
                  <option value="">Välj behov...</option>
                  <option value="1">Timbal</option>
                  <option value="2">Glutenfri</option>
                  <option value="3">Laktosfri</option>
                </select>
              </div>
            </div>

            <div class="admin-need-modal__row">
              <label class="admin-need-modal__label" for="need-modal-modifier-requirement-ids">Finns ytterligare behov för samma personer?</label>
              <div class="admin-need-modal__control">
                <div class="admin-need-modal__secondary-picker" data-need-picker-wrap>
                  <div class="admin-need-modal__secondary-caption">Ytterligare kostbehov (valfritt)</div>
                  <div class="admin-need-modal__chips" data-need-selected-modifiers></div>
                  <button type="button" class="yp-button yp-button-secondary admin-need-modal__add-modifier" data-need-picker-toggle aria-expanded="false">+ Lägg till kostbehov</button>
                  <select id="need-modal-modifier-requirement-ids" name="modifier_requirement_ids" class="admin-need-modal__multi" multiple size="6" aria-hidden="true" tabindex="-1">
                    <option value="1">Timbal</option>
                    <option value="2">Glutenfri</option>
                    <option value="3">Laktosfri</option>
                    <option value="4">Vegan</option>
                    <option value="5">Grovpaté</option>
                  </select>
                </div>
              </div>
            </div>

            <div class="admin-need-modal__row">
              <label class="admin-need-modal__label" for="need-modal-default-quantity">Hur många personer gäller det?</label>
              <div class="admin-need-modal__control">
                <input type="number" id="need-modal-default-quantity" name="default_quantity" class="yp-input sk-input" min="0" value="1">
              </div>
            </div>
          </div>

          <footer class="ua-modal-footer admin-need-modal__footer">
            <button type="button" class="yp-button yp-button-secondary" data-modal-close>Avbryt</button>
            <button type="button" class="yp-button yp-button-secondary admin-need-modal__remove-trigger" data-need-remove-start hidden>Ta bort kostbehov</button>
            <button type="submit" class="yp-button yp-button-primary">Spara behov</button>
          </footer>
        </form>
        <form class="admin-need-modal__remove-form" data-need-remove-form method="POST" action="/ui/admin/departments/demo/requirement-groups" hidden>
          <input type="hidden" name="csrf_token" value="csrf-token">
          <input type="hidden" name="group_id" value="group-1">
          <input type="hidden" name="remove_request" value="1">
          <div class="admin-need-modal__remove-state" data-need-remove-state>
            <div class="admin-need-modal__remove-card">
              <h3 class="admin-need-modal__remove-title">Ta bort <span data-need-remove-label></span>?</h3>
              <p class="admin-need-modal__remove-copy">Kostbehovet tas bort från avdelningen.</p>
              <div class="admin-need-modal__remove-actions">
                <button type="button" class="yp-button yp-button-secondary" data-need-remove-cancel>Avbryt</button>
                <button type="submit" class="yp-button yp-button-danger" data-need-remove-confirm>Ta bort kostbehov</button>
              </div>
            </div>
          </div>
        </form>
      </div>
      <div class="admin-need-modal__picker" data-need-picker hidden aria-hidden="true">
        <div class="admin-need-modal__picker-panel" data-need-picker-panel>
          <div class="admin-need-modal__picker-heading">Lägg till kostbehov</div>
          <input type="search" class="yp-input admin-need-modal__search" placeholder="Sök kostbehov..." aria-label="Sök kostbehov" data-need-picker-search>
          <div class="admin-need-modal__picker-list" data-need-picker-list></div>
          <p class="yp-form-help admin-need-modal__picker-empty" data-need-picker-empty hidden>Inga träffar.</p>
          <div class="admin-need-modal__picker-actions">
            <span class="admin-need-modal__picker-count" data-need-picker-count>0 valda</span>
            <button type="button" class="yp-button yp-button-primary" data-need-picker-close>Klar</button>
          </div>
        </div>
      </div>
    </dialog>

    <button type="button" id="open-need-modal" data-modal-target="#need-modal" data-need-mode="create">+ Lägg till behov</button>
    <button type="button" id="edit-need-modal" data-modal-target="#need-modal" data-need-mode="edit" data-need-group-id="group-1" data-need-label="Timbal + Glutenfri" data-need-primary-id="1" data-need-default-quantity="2" data-need-modifier-ids="2,3">Redigera behov</button>
  `;

  const dialog = document.getElementById('need-modal');
  if (dialog) {
    dialog.showModal = function showModal() {
      this.setAttribute('open', 'open');
    };
    dialog.close = function close() {
      this.removeAttribute('open');
    };
  }

  const toggle = document.querySelector('[data-need-picker-toggle]');
  if (toggle) {
    toggle.getBoundingClientRect = () => ({
      left: 120,
      top: 180,
      bottom: 220,
      right: 360,
      width: 240,
      height: 40,
    });
  }

  if (document.readyState === 'loading') {
    document.dispatchEvent(new Event('DOMContentLoaded'));
  }
}

function openNeedModalAndPicker() {
  document.getElementById('open-need-modal')?.click();
  document.querySelector('[data-need-picker-toggle]')?.click();
}

function openNeedModalOnly() {
  document.getElementById('open-need-modal')?.click();
}

function getNeedPicker() {
  return document.querySelector('[data-need-picker]');
}

function getNeedModalPanel() {
  return document.querySelector('#need-modal > .ua-modal-inner');
}

function getNeedModal() {
  return document.getElementById('need-modal');
}

function getSelectedValues() {
  return Array.from(document.querySelectorAll('#need-modal-modifier-requirement-ids option'))
    .filter((option) => option.selected)
    .map((option) => option.value);
}

function getFormDataValues() {
  const form = document.querySelector('#need-modal form');
  return Array.from(new FormData(form).getAll('modifier_requirement_ids')).map(String);
}

loadScript('../../static/js/unified_admin.js');

describe('Unified admin Kostbehov picker', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.unstubAllGlobals();
    vi.stubGlobal('requestAnimationFrame', (callback) => {
      callback();
      return 0;
    });
    renderNeedModalDom();
  });

  it('opens the parent modal without the picker and keeps the picker closed until the secondary trigger is used', () => {
    const triggerCount = document.body.querySelectorAll('[data-need-picker-toggle]').length;
    expect(triggerCount).toBe(1);

    const initialPicker = getNeedPicker();
    expect(initialPicker?.hidden).toBe(true);
    expect(initialPicker?.getAttribute('aria-hidden')).toBe('true');
    expect(getNeedModal()?.classList.contains('is-need-picker-open')).toBe(false);

    openNeedModalOnly();

    const picker = getNeedPicker();
    const dialog = getNeedModal();
    expect(dialog?.hasAttribute('open')).toBe(true);
    expect(dialog?.classList.contains('is-need-picker-open')).toBe(false);
    expect(picker?.hidden).toBe(true);
    expect(getNeedModalPanel()?.style.visibility).toBe('');

    document.querySelector('[data-need-picker-toggle]')?.click();

    expect(picker?.hidden).toBe(false);
    expect(dialog?.classList.contains('is-need-picker-open')).toBe(true);
    expect(getNeedModalPanel()?.style.visibility).toBe('hidden');

    expect(picker?.style.position).toBe('fixed');
    expect(picker?.style.placeItems).toBe('center');
    expect(picker?.style.zIndex).toBe('1060');
    expect(picker?.querySelector('[data-need-picker-panel]')?.dataset.needPickerPlacement).toBe('center');
    expect(picker?.querySelector('[data-need-picker-panel]')?.style.left).toBe('');
    expect(picker?.querySelector('[data-need-picker-panel]')?.style.top).toBe('');

    const search = document.querySelector('[data-need-picker-search]');
    expect(search).not.toBeNull();
    if (search) {
      search.value = 'glo';
      search.dispatchEvent(new Event('input', { bubbles: true }));
    }

    const visibleOptionLabels = Array.from(document.querySelectorAll('[data-need-picker-option]'))
      .filter((option) => !option.hidden)
      .map((option) => option.textContent?.trim());
    expect(visibleOptionLabels).toEqual(['Glutenfri']);
    expect(document.querySelector('[data-need-picker-empty]')?.hidden).toBe(true);

    const pickerClose = document.querySelector('[data-need-picker-close]');
    pickerClose?.click();
    expect(getNeedPicker()?.hidden).toBe(true);
    expect(getNeedPicker()?.getAttribute('aria-hidden')).toBe('true');
    expect(getNeedModal()?.hasAttribute('open')).toBe(true);
    expect(getNeedModal()?.classList.contains('is-need-picker-open')).toBe(false);
    expect(getNeedModalPanel()?.style.visibility).toBe('');
  });

  it('supports multi-select, keeps the modal open on Klar, and preserves selections on reopen', () => {
    openNeedModalAndPicker();

    const glutenfri = document.querySelector('[data-need-picker-option="2"]');
    const laktosfri = document.querySelector('[data-need-picker-option="3"]');
    expect(glutenfri).not.toBeNull();
    expect(laktosfri).not.toBeNull();
    glutenfri?.click();
    laktosfri?.click();

    expect(document.querySelector('[data-need-picker-count]')?.textContent).toBe('2 valda');
    expect(document.querySelectorAll('[data-need-selected-modifiers] .admin-need-modal__chip')).toHaveLength(2);
    expect(getSelectedValues()).toEqual(['2', '3']);
    expect(getFormDataValues()).toEqual(['2', '3']);

    const chipRemove = document.querySelector('[data-need-chip-remove="2"]');
    chipRemove?.click();
    expect(document.querySelectorAll('[data-need-selected-modifiers] .admin-need-modal__chip')).toHaveLength(1);
    expect(getSelectedValues()).toEqual(['3']);

    const pickerClose = document.querySelector('[data-need-picker-close]');
    pickerClose?.click();
    expect(getNeedPicker()?.hidden).toBe(true);
    expect(getNeedPicker()?.getAttribute('aria-hidden')).toBe('true');
    expect(getNeedModal()?.hasAttribute('open')).toBe(true);
    expect(getNeedModal()?.classList.contains('is-need-picker-open')).toBe(false);
    expect(getNeedModalPanel()?.style.visibility).toBe('');
    expect(document.activeElement).toBe(document.querySelector('[data-need-picker-toggle]'));

    document.querySelector('[data-need-picker-toggle]')?.click();
    expect(getNeedPicker()?.hidden).toBe(false);
    expect(document.querySelector('[data-need-picker-option="3"]')?.classList.contains('is-selected')).toBe(true);
    expect(document.querySelector('[data-need-picker-count]')?.textContent).toBe('1 valda');

    const search = document.querySelector('[data-need-picker-search]');
    search?.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    expect(getNeedPicker()?.hidden).toBe(true);
    expect(getNeedModal()?.hasAttribute('open')).toBe(true);
    expect(getNeedModal()?.classList.contains('is-need-picker-open')).toBe(false);
    expect(getNeedModalPanel()?.style.visibility).toBe('');

    document.querySelector('[data-need-picker-toggle]')?.click();
    expect(getNeedPicker()?.hidden).toBe(false);
    document.body.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(getNeedPicker()?.hidden).toBe(true);
    expect(getNeedModal()?.hasAttribute('open')).toBe(true);
  });

  it('clears transient picker state when the parent modal closes and reopens', () => {
    openNeedModalAndPicker();
    expect(getNeedModal()?.classList.contains('is-need-picker-open')).toBe(true);

    document.querySelector('#need-modal [data-modal-close]')?.click();
    expect(getNeedModal()?.hasAttribute('open')).toBe(false);
    expect(getNeedModal()?.classList.contains('is-need-picker-open')).toBe(false);
    expect(getNeedPicker()?.hidden).toBe(true);

    openNeedModalOnly();
    expect(getNeedModal()?.hasAttribute('open')).toBe(true);
    expect(getNeedPicker()?.hidden).toBe(true);
    expect(getNeedModal()?.classList.contains('is-need-picker-open')).toBe(false);
  });

  it('keeps remove actions locked to edit mode only', () => {
    openNeedModalOnly();

    const createRemoveStart = document.querySelector('[data-need-remove-start]');
    const createRemoveState = document.querySelector('[data-need-remove-state]');
    expect(document.querySelectorAll('[data-need-remove-state]')).toHaveLength(1);
    expect(createRemoveStart?.hidden).toBe(true);
    createRemoveStart?.click();
    expect(createRemoveState?.hidden).toBe(true);

    document.getElementById('edit-need-modal')?.click();
    expect(createRemoveStart?.hidden).toBe(false);
    createRemoveStart?.click();
    expect(getNeedModal()?.classList.contains('is-need-remove-open')).toBe(true);
    expect(document.querySelector('.admin-need-modal__edit-form')?.hidden).toBe(true);
    expect(document.querySelector('[data-need-remove-form]')?.hidden).toBe(false);
    expect(createRemoveState?.hidden).toBe(false);
    expect(document.querySelector('[data-need-remove-label]')?.textContent).toBe('Timbal + Glutenfri');
    expect(document.querySelector('[data-need-edit-state]')?.hidden).toBe(true);
    const removeConfirm = document.querySelector('[data-need-remove-confirm]');
    expect(removeConfirm).not.toBeNull();
    expect(removeConfirm?.getAttribute('type')).toBe('submit');
    expect(removeConfirm?.getAttribute('form')).toBeNull();
    expect(removeConfirm?.getAttribute('name')).toBeNull();
    expect(removeConfirm?.getAttribute('value')).toBeNull();
    expect(document.querySelector('[data-need-remove-form] input[name="remove_request"]')?.value).toBe('1');

    document.querySelector('[data-need-remove-cancel]')?.click();
    expect(getNeedModal()?.classList.contains('is-need-remove-open')).toBe(false);
    expect(createRemoveState?.hidden).toBe(true);
    expect(document.querySelector('[data-need-remove-form]')?.hidden).toBe(true);

    createRemoveStart?.click();
    removeConfirm?.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }));
    expect(getNeedModal()?.hasAttribute('open')).toBe(false);
    expect(getNeedModal()?.classList.contains('ua-modal-open')).toBe(false);
  });
});
