import fs from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(code + '\n//# sourceURL=' + relativePath);
}

function createDeferred() {
  let resolve;
  let reject;
  const promise = new Promise((promiseResolve, promiseReject) => {
    resolve = promiseResolve;
    reject = promiseReject;
  });
  return { promise, resolve, reject };
}

async function waitForCondition(check, timeoutMs = 1000) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (check()) {
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  return check();
}

function renderPage3Dom({
  departments = ['dept-a', 'dept-b'],
  serviceDate = '2026-09-08',
  year = 2026,
  week = 37,
  ready = true,
  withButton = true,
} = {}) {
  const buttonMarkup = withButton
    ? `
      <div class="yp-planera-page3-action-row" data-page3-completion-shell>
        <button class="yp-planera-page3-completion-button" type="button" data-page3-completion-button>Markera som gjorda i veckolistan</button>
        <p class="yp-planera-page3-completion-feedback" data-page3-completion-feedback aria-live="polite" hidden></p>
      </div>`
    : '';

  document.body.innerHTML = `
    <div
      id="yp-product-app"
      data-theme="light"
      data-screen="production-underlag"
      data-page3-site-id="site-1"
      data-page3-service-date="${serviceDate}"
      data-page3-meal="lunch"
      data-page3-year="${year}"
      data-page3-week="${week}"
      data-page3-completion-target-departments='${JSON.stringify(departments)}'
    >
      <header class="yp-planera-page3-hero">
        <div class="yp-planera-page3-hero__row">
          <div class="yp-planera-page3-hero__heading">
            <h1 class="yp-planera-page3-title" id="yp-planera-page3-title">Produktionsunderlag</h1>
          </div>
          <a class="yp-planera-page3-backlink" href="#">Granska underlag</a>
        </div>
        <div class="yp-planera-page3-context" aria-label="Produktionskontext">
          <div class="yp-planera-page3-date-control" aria-label="Datum">
            <span class="yp-planera-page3-date-control__arrow" aria-hidden="true">‹</span>
            <span class="yp-planera-page3-date-control__date">tisdag 8 sep 2026</span>
            <span class="yp-planera-page3-date-control__arrow" aria-hidden="true">›</span>
          </div>
          <div class="yp-planera-page3-context__line">
            <p class="yp-planera-page3-subtitle">Kommunköket · Lunch</p>
            <span class="yp-planera-page3-status-pill ${ready ? 'is-ready' : 'is-blocked'}">${ready ? 'Produktionsunderlaget är klart' : 'Underlag behöver granskas'}</span>
          </div>
        </div>
        ${buttonMarkup}
      </header>
      <nav class="yp-planera-page3-tabs" aria-label="Produktionsvyer" data-page3-tabs>
        <a class="yp-planera-page3-tab is-active" data-page3-view-link data-page3-view="overview" href="#">Översikt</a>
      </nav>
      <section class="yp-planera-page3-section" data-page3-panel="overview">Översikt</section>
    </div>
  `;

  document.dispatchEvent(new Event('DOMContentLoaded'));
}

function clickCompletionButton() {
  const button = document.querySelector('[data-page3-completion-button]');
  expect(button).toBeTruthy();
  button.click();
  return button;
}

loadScript('../../static/js/planera_product2_page3.js');

describe('Product2 Page3 completion contract', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.unstubAllGlobals();
  });

  it('deduplicates affected departments before fetching ETags', async () => {
    renderPage3Dom({ departments: ['dept-a', 'dept-b', 'dept-a'] });
    const fetchMock = vi.fn(async (input) => {
      const url = String(input);
      if (url.startsWith('/api/weekview/etag')) {
        return {
          ok: true,
          status: 200,
          headers: new Headers({ ETag: `W/"${url}"` }),
          json: async () => ({ etag: `W/"${url}"` }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ marked: true, target_count: 2, departments: { 'dept-a': 1, 'dept-b': 1 } }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);

    clickCompletionButton();

    await waitForCondition(() => fetchMock.mock.calls.length === 3);
    const etagUrls = fetchMock.mock.calls.slice(0, 2).map(([input]) => String(input));
    expect(etagUrls.filter((url) => url.includes('department_id=dept-a'))).toHaveLength(1);
    expect(etagUrls.filter((url) => url.includes('department_id=dept-b'))).toHaveLength(1);
  });

  it('fetches every department ETag before posting completion and sends only the approved payload', async () => {
    renderPage3Dom({ departments: ['dept-a', 'dept-b'] });
    const etagA = createDeferred();
    const etagB = createDeferred();
    const postDeferred = createDeferred();
    const fetchMock = vi.fn((input, init) => {
      const url = String(input);
      if (url.includes('/api/weekview/etag') && url.includes('department_id=dept-a')) {
        return etagA.promise;
      }
      if (url.includes('/api/weekview/etag') && url.includes('department_id=dept-b')) {
        return etagB.promise;
      }
      if (url === '/api/planera/product2/production-completion') {
        return postDeferred.promise;
      }
      return Promise.reject(new Error(`unexpected fetch: ${url}`));
    });
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('Headers', Headers);

    clickCompletionButton();
    expect(document.querySelector('[data-page3-completion-button]')?.disabled).toBe(true);
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes('/api/planera/product2/production-completion'))).toHaveLength(0);

    etagA.resolve({
      ok: true,
      status: 200,
      headers: new Headers({ ETag: 'W/"etag-a"' }),
      json: async () => ({ etag: 'W/"etag-a"' }),
    });
    await waitForCondition(() => fetchMock.mock.calls.filter(([input]) => String(input).includes('/api/weekview/etag')).length === 2);
    expect(fetchMock.mock.calls.filter(([input]) => String(input).includes('/api/planera/product2/production-completion'))).toHaveLength(0);

    etagB.resolve({
      ok: true,
      status: 200,
      headers: new Headers({ ETag: 'W/"etag-b"' }),
      json: async () => ({ etag: 'W/"etag-b"' }),
    });
    await waitForCondition(() => fetchMock.mock.calls.filter(([input]) => String(input).includes('/api/planera/product2/production-completion')).length === 1);

    const [, requestInit] = fetchMock.mock.calls.find(([input]) => String(input) === '/api/planera/product2/production-completion');
    const body = JSON.parse(requestInit.body);
    expect(body).toEqual({
      site_id: 'site-1',
      service_date: '2026-09-08',
      meal: 'lunch',
      marked: true,
      expected_etags: {
        'dept-a': 'W/"etag-a"',
        'dept-b': 'W/"etag-b"',
      },
    });
    expect(body).not.toHaveProperty('group_id');
    expect(body).not.toHaveProperty('requirement_group_id');
    expect(body).not.toHaveProperty('completion_targets');
    expect(body).not.toHaveProperty('combination_key');
    expect(body).not.toHaveProperty('diet_type_id');

    postDeferred.resolve({
      ok: true,
      status: 200,
      json: async () => ({ marked: true, target_count: 2, departments: { 'dept-a': 1, 'dept-b': 1 } }),
    });
    await waitForCondition(() => document.querySelector('[data-page3-completion-button]')?.textContent === 'Markerat i veckolistan ✓');
  });

  it('marks completion success and keeps the button disabled', async () => {
    renderPage3Dom({ departments: ['dept-a'] });
    const fetchMock = vi.fn(async (input) => {
      const url = String(input);
      if (url.includes('/api/weekview/etag')) {
        return {
          ok: true,
          status: 200,
          headers: new Headers({ ETag: 'W/"etag-a"' }),
          json: async () => ({ etag: 'W/"etag-a"' }),
        };
      }
      return {
        ok: true,
        status: 200,
        json: async () => ({ marked: true, target_count: 1, departments: { 'dept-a': 1 } }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);

    clickCompletionButton();

    await waitForCondition(() => document.querySelector('[data-page3-completion-button]')?.textContent === 'Markerat i veckolistan ✓');
    expect(document.querySelector('[data-page3-completion-button]')?.disabled).toBe(true);
    expect(document.querySelector('[data-page3-completion-feedback]')?.textContent).toContain('Markerat i veckolistan.');
  });

  it('restores the button after a failure and shows stale-weekview feedback on 412', async () => {
    renderPage3Dom({ departments: ['dept-a'] });
    const fetchMock = vi.fn(async (input) => {
      const url = String(input);
      if (url.includes('/api/weekview/etag')) {
        return {
          ok: true,
          status: 200,
          headers: new Headers({ ETag: 'W/"etag-a"' }),
          json: async () => ({ etag: 'W/"etag-a"' }),
        };
      }
      return {
        ok: false,
        status: 412,
        json: async () => ({ detail: 'etag_mismatch' }),
      };
    });
    vi.stubGlobal('fetch', fetchMock);

    const button = clickCompletionButton();
    await waitForCondition(() => document.querySelector('[data-page3-completion-feedback]')?.textContent?.includes('Veckolistan har ändrats'));
    expect(button.disabled).toBe(false);
    expect(button.textContent).toBe('Markera som gjorda i veckolistan');
    expect(document.querySelector('[data-page3-completion-feedback]')?.textContent).toContain('Veckolistan har ändrats. Försök igen.');
  });

  it('does not reference legacy mark or clear endpoints', () => {
    const url = new URL('../../static/js/planera_product2_page3.js', import.meta.url);
    const source = fs.readFileSync(url, 'utf8');
    expect(source).not.toContain('mark_produced_special');
    expect(source).not.toContain('clear_produced_special');
  });
});
