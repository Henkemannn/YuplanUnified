import { beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(`${code}\n//# sourceURL=${relativePath}`);
}

function flush() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe('admin menu import week actions', () => {
  beforeEach(() => {
    delete window.YuplanModalHost;
    delete window.AdminWeekBuilderHost;
    delete window.BuilderCompositionSearchRuntime;
    delete window.BuilderDishCreateModal;
    window.fetch = vi.fn();
    window.alert = vi.fn();
    document.body.innerHTML = '';
    document.body.className = '';
  });

  it('opens the inline picker shell and reuses the canonical composition search runtime', async () => {
    document.body.innerHTML = `
      <section class="menu-week__grid" data-builder-menu-id="menu-123">
        <article data-week-slot-row data-menu-detail-id="detail-1" data-day-key="monday" data-day-label="Måndag" data-meal-label="Lunch" data-slot-key="lunch_alt1" data-meal-slot="lunch_alt1" data-dish-name="Köttbullar med potatismos" data-unresolved-text="">
          <button type="button" data-week-slot-action-toggle aria-expanded="false">⋯</button>
          <div hidden data-week-slot-action-menu>
            <button type="button" data-week-slot-action="replace">Byt rätt</button>
          </div>
        </article>
      </section>
      <section class="yp-modal-host" hidden aria-hidden="true" data-modal-host-mode="child-owned-card" data-admin-week-builder-host>
        <div class="yp-modal-host__backdrop" data-admin-week-builder-host-close></div>
        <div class="yp-modal-host__panel" role="dialog" aria-modal="true" aria-label="Redigera rätt" tabindex="-1" data-admin-week-builder-host-panel>
          <div class="yp-modal-host__inline-picker" hidden data-admin-week-builder-inline-picker>
            <header class="yp-modal-host__inline-header">
              <div>
                <p class="workspace-modal-kicker">Menyimport</p>
                <h1 id="adminWeekBuilderInlineTitle">Rättbibliotek</h1>
              </div>
              <button type="button" class="yp-btn yp-btn-secondary" data-admin-week-builder-inline-close>Stäng</button>
            </header>
            <p class="yp-modal-host__inline-context" data-admin-week-builder-inline-context></p>
            <label class="yp-modal-host__inline-search-label" for="adminWeekBuilderInlineSearch">Sök rätt</label>
            <input id="adminWeekBuilderInlineSearch" type="search" class="yp-input yp-modal-host__inline-search" placeholder="Sök rätt…" autocomplete="off" data-admin-week-builder-inline-search>
            <p class="yp-modal-host__inline-status" data-admin-week-builder-inline-status role="status" aria-live="polite">Sök efter en rätt.</p>
            <div class="yp-modal-host__inline-results" data-admin-week-builder-inline-results></div>
            <footer class="yp-modal-host__inline-actions">
              <button type="button" class="yp-btn yp-btn-primary" data-admin-week-builder-inline-create>+ Skapa ny rätt</button>
              <button type="button" class="yp-btn yp-btn-secondary" data-admin-week-builder-inline-close>Avbryt</button>
            </footer>
          </div>
          <iframe class="yp-modal-host__frame" title="Menyimportredigerare" src="about:blank" data-admin-week-builder-host-frame></iframe>
        </div>
      </section>
      <div id="quickCreateModal" class="modal hidden" hidden aria-hidden="true">
        <div class="modal-content modal-content-compact">
          <div class="workspace-modal-header">
            <div>
              <p class="workspace-modal-kicker">Skapa rätt</p>
              <h3>Skapa rätt</h3>
            </div>
            <button id="quickCreateModalClose" type="button">Avbryt</button>
          </div>
          <section class="workspace-quick-card">
            <label>Rättnamn
              <input id="freeDishName" type="text" placeholder="Kottbullar med potatis">
            </label>
            <label>Kategori
              <select id="freeDishCategory">
                <option value="ovrigt" selected>Övrigt</option>
              </select>
            </label>
            <button id="btnCreateDish" type="button">Skapa rätt</button>
            <div id="createDishOut" class="workspace-feedback" aria-live="polite"></div>
          </section>
        </div>
      </div>
    `;

    const compositions = [
      { composition_id: 'dish_1', composition_name: 'Fish Cakes' },
      { composition_id: 'dish_2', composition_name: 'Chicken Soup' },
    ];

    window.fetch = vi.fn(async (url, options) => {
      const requestUrl = String(url);
      if (requestUrl === '/api/builder/compositions') {
        return {
          ok: true,
          status: 200,
          json: async () => ({ ok: true, compositions }),
        };
      }
      if (requestUrl === '/api/builder/menus/menu-123/rows/detail-1') {
        expect(options.method).toBe('PATCH');
        expect(JSON.parse(options.body)).toEqual({
          day: 'monday',
          meal_slot: 'lunch_alt1',
          composition_id: 'dish_1',
        });
        return {
          ok: true,
          status: 200,
          json: async () => ({ ok: true }),
        };
      }
      throw new Error('Unexpected fetch: ' + requestUrl);
    });

    let reloadCount = 0;
    try {
      Object.defineProperty(window.location, 'reload', {
        configurable: true,
        value: () => {
          reloadCount += 1;
        },
      });
    } catch (error) {
      window.location.reload = () => {
        reloadCount += 1;
      };
    }

    loadScript('../../static/js/modal_host.js');
    loadScript('../../static/js/builder_composition_search.js');
    loadScript('../../static/js/builder_dish_create.js');
    loadScript('../../static/ui/admin_menu_import_week_actions.js');
    document.dispatchEvent(new Event('DOMContentLoaded'));

    const replaceButton = document.querySelector('[data-week-slot-action="replace"]');
    replaceButton.click();

    await flush();
    await flush();

    const hostRoot = document.querySelector('[data-admin-week-builder-host]');
    const inlinePicker = document.querySelector('[data-admin-week-builder-inline-picker]');
    const inlineSearch = document.querySelector('[data-admin-week-builder-inline-search]');
    const inlineResults = document.querySelector('[data-admin-week-builder-inline-results]');
    const frame = document.querySelector('[data-admin-week-builder-host-frame]');

    expect(hostRoot.hidden).toBe(false);
    expect(hostRoot.getAttribute('data-modal-host-mode')).toBe('shell-owned-card');
    expect(inlinePicker.hidden).toBe(false);
    expect(frame.getAttribute('src')).toBe('about:blank');

    inlineSearch.value = 'fish';
    inlineSearch.dispatchEvent(new Event('input', { bubbles: true }));

    await flush();

    const resultButton = inlineResults.querySelector('.yp-modal-host__inline-result');
    expect(resultButton).not.toBeNull();
    expect(resultButton.textContent).toBe('Fish Cakes');

    resultButton.click();

    await flush();
    await flush();

    expect(window.fetch).toHaveBeenCalledWith('/api/builder/compositions', expect.any(Object));
    expect(reloadCount).toBe(1);
  });
});
