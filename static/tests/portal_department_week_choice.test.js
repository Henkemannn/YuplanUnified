import fs from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const WEEKDAY_CASES = [
  ['Måndag', 'mon'],
  ['Tisdag', 'tue'],
  ['Onsdag', 'wed'],
  ['Torsdag', 'thu'],
  ['Fredag', 'fri'],
  ['Lördag', 'sat'],
  ['Söndag', 'sun'],
];

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

function createFetchResponse(status, newEtag = 'W/"portal-dept-week:etag-2"') {
  return {
    status,
    json: async () => ({ new_etag: newEtag, selected_alt: 'Alt2' }),
  };
}

function getWeekdayLabel(row) {
  return row.querySelector('.portal-day-name > div')?.textContent?.trim() || '';
}

function renderPortalDom(initialSelections = {}) {
  const weekdayLabels = [
    ['Måndag', '2026-08-31'],
    ['Tisdag', '2026-09-01'],
    ['Onsdag', '2026-09-02'],
    ['Torsdag', '2026-09-03'],
    ['Fredag', '2026-09-04'],
    ['Lördag', '2026-09-05'],
    ['Söndag', '2026-09-06'],
  ];

  const weekdayRows = weekdayLabels
    .map(([weekdayLabel, dateLabel]) => {
      const selectedAlt = initialSelections[weekdayLabel] || null;
      const alt1Selected = selectedAlt === 'Alt1';
      const alt2Selected = selectedAlt === 'Alt2';
      return `
        <tr class="portal-day-row">
          <td class="portal-day-name">
            <div>${weekdayLabel}</div>
            <div class="portal-day-date">${dateLabel}</div>
          </td>
          <td
            class="portal-alt-cell portal-alt1-cell${alt1Selected ? ' portal-alt-selected' : ''}"
            data-weekday="${weekdayLabel}"
            data-selected-alt="Alt1"
            role="button"
            tabindex="0"
            aria-pressed="${alt1Selected ? 'true' : 'false'}"
            aria-label="Välj Alt 1 för ${weekdayLabel}"
          >Alt1</td>
          <td
            class="portal-alt-cell portal-alt2-cell${alt2Selected ? ' portal-alt-selected' : ''}"
            data-weekday="${weekdayLabel}"
            data-selected-alt="Alt2"
            role="button"
            tabindex="0"
            aria-pressed="${alt2Selected ? 'true' : 'false'}"
            aria-label="Välj Alt 2 för ${weekdayLabel}"
          >Alt2</td>
        </tr>`;
    })
    .join('');

  const weekDots = weekdayLabels
    .map(([weekdayLabel]) => {
      const selectedAlt = initialSelections[weekdayLabel] || null;
      return `<div class="portal-week-dot${selectedAlt ? ' chosen' : ''}" role="listitem" aria-label="${weekdayLabel}${selectedAlt ? ' vald' : ' ej vald'}"></div>`;
    })
    .join('');

  document.body.innerHTML = `
    <div
      id="portal-dept-week-root"
      class="portal-dept-week"
      data-year="2026"
      data-week="35"
      data-menu-choice-etag='W/"portal-menu-choice:etag-1"'
    ></div>
    <div id="portal-status-message" class="portal-status" aria-live="polite"></div>
    <section class="portal-progress"><p>Valda dagar: 0 / 7</p></section>
    <div class="portal-week-status">
      <div class="portal-week-status-label">Valda dagar:</div>
      <div class="portal-week-dots" role="list">${weekDots}</div>
      <div class="portal-week-status-count">0 / 7</div>
      <div id="portal-sync-indicator" class="portal-sync-indicator">Synkad</div>
    </div>
    <table>
      <tbody>
        ${weekdayRows}
      </tbody>
    </table>
    <div id="portal-menu-overlay" hidden></div>
    <div id="portal-conflict-overlay" hidden></div>
  `;

  document.dispatchEvent(new Event('DOMContentLoaded'));
}

function clickWeekdayAlt(weekdayLabel, altSelector) {
  const row = Array.from(document.querySelectorAll('.portal-day-row')).find((candidate) => getWeekdayLabel(candidate) === weekdayLabel);
  expect(row).toBeTruthy();
  const cell = row.querySelector(altSelector);
  expect(cell).toBeTruthy();
  cell.click();
  return cell;
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

loadScript('../../static/js/portal_department_week.js');

describe('Department Portal weekday choice contract', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.unstubAllGlobals();
  });

  it.each(WEEKDAY_CASES)('maps %s to %s before POST', async (weekdayLabel, apiCode) => {
    renderPortalDom();
    const fetchMock = vi.fn(async () => createFetchResponse(200));
    vi.stubGlobal('fetch', fetchMock);

    clickWeekdayAlt(weekdayLabel, '.portal-alt2-cell');

    await waitForCondition(() => fetchMock.mock.calls.length === 1);
    const [, requestInit] = fetchMock.mock.calls[0];
    expect(JSON.parse(requestInit.body)).toMatchObject({
      year: 2026,
      week: 35,
      weekday: apiCode,
      selected_alt: 'Alt2',
    });
  });

  it('applies the green state only after a successful save and updates progress', async () => {
    renderPortalDom();
    const firstResponse = createDeferred();
    const secondResponse = createDeferred();
    let callIndex = 0;
    const fetchMock = vi.fn(() => {
      callIndex += 1;
      return callIndex === 1 ? firstResponse.promise : secondResponse.promise;
    });
    vi.stubGlobal('fetch', fetchMock);

    clickWeekdayAlt('Måndag', '.portal-alt2-cell');
    expect(document.querySelector('.portal-progress p')?.textContent).toBe('Valda dagar: 0 / 7');
    expect(document.querySelector('.portal-week-status-count')?.textContent).toBe('0 / 7');
    expect(document.querySelector('.portal-day-row .portal-alt2-cell')?.classList.contains('portal-alt-selected')).toBe(false);
    expect(document.getElementById('portal-status-message')?.textContent).toContain('Sparar val');

    firstResponse.resolve(createFetchResponse(200, 'W/"portal-dept-week:etag-2"'));
    await waitForCondition(() => document.querySelector('.portal-day-row .portal-alt2-cell')?.classList.contains('portal-alt-selected'));
    expect(document.querySelector('.portal-progress p')?.textContent).toBe('Valda dagar: 1 / 7');
    expect(document.querySelector('.portal-week-status-count')?.textContent).toBe('1 / 7');
    expect(document.querySelector('.portal-week-dot.chosen')?.getAttribute('aria-label')).toContain('vald');
    expect(document.getElementById('portal-status-message')?.textContent).toContain('Val sparat');

    clickWeekdayAlt('Tisdag', '.portal-alt1-cell');
    expect(document.querySelector('.portal-progress p')?.textContent).toBe('Valda dagar: 1 / 7');
    expect(document.querySelector('.portal-day-row:nth-child(2) .portal-alt1-cell')?.classList.contains('portal-alt-selected')).toBe(false);

    secondResponse.resolve(createFetchResponse(200, 'W/"portal-dept-week:etag-3"'));
    await waitForCondition(() => document.querySelector('.portal-progress p')?.textContent === 'Valda dagar: 2 / 7');
    expect(document.querySelector('.portal-week-status-count')?.textContent).toBe('2 / 7');
    expect(document.querySelectorAll('.portal-week-dot.chosen')).toHaveLength(2);
  });

  it('restores the previously persisted state when a save fails', async () => {
    renderPortalDom({ Måndag: 'Alt1' });
    const failure = createDeferred();
    const fetchMock = vi.fn(() => failure.promise);
    vi.stubGlobal('fetch', fetchMock);

    clickWeekdayAlt('Måndag', '.portal-alt2-cell');
    expect(document.querySelector('.portal-day-row .portal-alt1-cell')?.classList.contains('portal-alt-selected')).toBe(true);
    expect(document.querySelector('.portal-day-row .portal-alt2-cell')?.classList.contains('portal-alt-selected')).toBe(false);
    expect(document.querySelector('.portal-progress p')?.textContent).toBe('Valda dagar: 1 / 7');
    expect(document.getElementById('portal-status-message')?.textContent).toContain('Sparar val');

    failure.resolve({
      status: 400,
      json: async () => ({ error: 'invalid_weekday' }),
    });
    await waitForCondition(() => document.getElementById('portal-status-message')?.textContent?.includes('Ogiltig förfrågan'));
    expect(document.querySelector('.portal-day-row .portal-alt1-cell')?.classList.contains('portal-alt-selected')).toBe(true);
    expect(document.querySelector('.portal-day-row .portal-alt2-cell')?.classList.contains('portal-alt-selected')).toBe(false);
    expect(document.querySelector('.portal-progress p')?.textContent).toBe('Valda dagar: 1 / 7');
  });
});
