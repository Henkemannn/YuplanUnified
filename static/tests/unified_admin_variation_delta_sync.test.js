import fs from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(code + '\n//# sourceURL=' + relativePath);
}

function renderVariationDom() {
  document.body.innerHTML = `
    <dialog id="residents-variation-modal" class="ua-modal admin-variation-modal">
      <div class="ua-modal-inner admin-variation-modal__inner">
        <div class="ua-modal-body admin-variation-modal__body">
          <form id="residents-variation-form" class="admin-variation-modal__form">
            <input type="hidden" name="selected_year" value="2026">
            <input type="hidden" name="selected_week" value="41">
            <input type="hidden" name="variation_focus_group_id" value="">
            <table class="ua-table admin-variation-table">
              <tr>
                <th>Dag</th>
                <th>Lunch</th>
                <th>Kväll</th>
              </tr>
              <tr>
                <td>Ons</td>
                <td><input type="number" name="day_3_lunch" value="12" min="0" class="yp-input admin-variation-input"></td>
                <td><input type="number" name="day_3_dinner" value="14" min="0" class="yp-input admin-variation-input"></td>
              </tr>
              <tr>
                <td>Tors</td>
                <td><input type="number" name="day_4_lunch" value="8" min="0" class="yp-input admin-variation-input"></td>
                <td><input type="number" name="day_4_dinner" value="9" min="0" class="yp-input admin-variation-input"></td>
              </tr>
            </table>
            <section class="admin-variation-needs">
              <details open data-variation-group-id="group-a">
                <summary>Group A</summary>
                <table class="ua-table admin-variation-table admin-variation-table--need">
                  <tr>
                    <th>Dag</th>
                    <th>Lunch</th>
                    <th>Kväll</th>
                  </tr>
                  <tr>
                    <td>Ons</td>
                    <td><input type="number" min="0" step="1" class="yp-input admin-variation-input" name="need_day_group-a_3_lunch" value="2"></td>
                    <td><input type="number" min="0" step="1" class="yp-input admin-variation-input" name="need_day_group-a_3_dinner" value="4"></td>
                  </tr>
                </table>
              </details>
              <details open data-variation-group-id="group-b">
                <summary>Group B</summary>
                <table class="ua-table admin-variation-table admin-variation-table--need">
                  <tr>
                    <th>Dag</th>
                    <th>Lunch</th>
                    <th>Kväll</th>
                  </tr>
                  <tr>
                    <td>Ons</td>
                    <td><input type="number" min="0" step="1" class="yp-input admin-variation-input" name="need_day_group-b_3_lunch" value="3"></td>
                    <td><input type="number" min="0" step="1" class="yp-input admin-variation-input" name="need_day_group-b_3_dinner" value="1"></td>
                  </tr>
                </table>
              </details>
            </section>
          </form>
        </div>
      </div>
    </dialog>
  `;
}

function seedNeedBaselines() {
  document
    .querySelectorAll('#residents-variation-form input[type="number"][name^="need_day_"]')
    .forEach((input) => {
      input.dataset.variationDeltaValue = String(Number.parseInt(input.value || '0', 10) || 0);
    });
}

function setInputValue(name, value) {
  const input = document.querySelector(`[name="${name}"]`);
  expect(input).not.toBeNull();
  if (!input) {
    return;
  }
  input.value = String(value);
  input.dispatchEvent(new Event('input', { bubbles: true }));
}

function getValue(name) {
  return document.querySelector(`[name="${name}"]`)?.value;
}

loadScript('../../static/js/unified_admin.js');
document.dispatchEvent(new Event('DOMContentLoaded'));

describe('Unified admin variation delta sync', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.unstubAllGlobals();
    vi.stubGlobal('requestAnimationFrame', (callback) => {
      callback();
      return 0;
    });
    renderVariationDom();
    seedNeedBaselines();
  });

  it('keeps the matching resident cell in sync with the need delta and leaves other meals alone', () => {
    expect(getValue('day_3_lunch')).toBe('12');
    expect(getValue('day_3_dinner')).toBe('14');

    setInputValue('need_day_group-a_3_lunch', 1);
    expect(getValue('day_3_lunch')).toBe('11');
    expect(getValue('day_3_dinner')).toBe('14');
    expect(Number(getValue('day_3_lunch')) - Number(getValue('need_day_group-a_3_lunch'))).toBe(10);

    setInputValue('need_day_group-a_3_lunch', 3);
    expect(getValue('day_3_lunch')).toBe('13');
    expect(getValue('day_3_dinner')).toBe('14');
    expect(Number(getValue('day_3_lunch')) - Number(getValue('need_day_group-a_3_lunch'))).toBe(10);
  });

  it('lets resident edits stay independent and applies later need deltas to the current resident value', () => {
    expect(getValue('need_day_group-a_3_lunch')).toBe('2');
    expect(getValue('need_day_group-b_3_lunch')).toBe('3');

    setInputValue('day_3_lunch', 11);
    expect(getValue('need_day_group-a_3_lunch')).toBe('2');
    expect(getValue('need_day_group-b_3_lunch')).toBe('3');

    setInputValue('need_day_group-a_3_lunch', 1);
    expect(getValue('day_3_lunch')).toBe('10');

    setInputValue('need_day_group-b_3_lunch', 1);
    expect(getValue('day_3_lunch')).toBe('8');

    expect(getValue('day_4_lunch')).toBe('8');
    expect(getValue('day_4_dinner')).toBe('9');
  });
});