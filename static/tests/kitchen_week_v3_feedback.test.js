import fs from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(code + '\n//# sourceURL=' + relativePath);
}

function response(status, etag = 'W/"weekview:etag-1"') {
  return {
    status,
    ok: status >= 200 && status < 300,
    json: async () => ({ etag }),
  };
}

function renderDom({ cohort = false, disabled = false } = {}) {
  document.body.innerHTML = `
    <div data-weekview-status role="status" aria-live="polite"></div>
    <button
      class="kostcell-btn${cohort ? ' kostcell-btn--cohort' : ''}"
      ${cohort ? 'data-row-kind="cohort" data-group-id="group-1" data-service-date="2026-09-28"' : 'data-diet-type-id="diet-1"'}
      data-department-id="dept-1"
      data-year="2026"
      data-week="39"
      data-day-index="1"
      data-meal="lunch"
      ${disabled ? 'disabled' : ''}
    >3</button>
  `;
  document.dispatchEvent(new Event('DOMContentLoaded'));
  return document.querySelector('.kostcell-btn');
}

function settle() {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

loadScript('../../static/js/kitchen_week_v3.js');

describe('Kitchen Weekview completion feedback', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    vi.unstubAllGlobals();
    vi.stubGlobal('fetch', vi.fn());
  });

  it.each([false, true])('marks %s rows only after HTTP 200', async (cohort) => {
    const button = renderDom({ cohort });
    fetch.mockResolvedValueOnce(response(200)).mockResolvedValueOnce(response(200));

    button.click();
    expect(button.classList.contains('is-done')).toBe(false);
    await settle();
    await settle();

    expect(button.classList.contains('is-done')).toBe(true);
    expect(document.querySelector('[data-weekview-status]').textContent).toContain('sparad');
    expect(button.disabled).toBe(false);
  });

  it.each([400, 403, 500])('shows a visible error for ETag HTTP %s', async (status) => {
    const button = renderDom();
    fetch.mockResolvedValueOnce(response(status));

    button.click();
    await settle();

    expect(button.classList.contains('is-done')).toBe(false);
    expect(document.querySelector('[data-weekview-status]').dataset.state).toBe('error');
    expect(document.querySelector('[data-weekview-status]').textContent).toContain('inte sparas');
    expect(button.disabled).toBe(false);
  });

  it.each([
    [false, 400], [false, 403], [false, 409], [false, 500],
    [true, 400], [true, 403], [true, 409], [true, 500],
  ])('shows a visible error for %s POST HTTP %s', async (cohort, status) => {
    const button = renderDom({ cohort });
    fetch.mockResolvedValueOnce(response(200)).mockResolvedValueOnce(response(status));

    button.click();
    await settle();
    await settle();

    expect(button.classList.contains('is-done')).toBe(false);
    expect(document.querySelector('[data-weekview-status]').dataset.state).toBe('error');
    expect(button.disabled).toBe(false);
  });

  it('retries one 412 and succeeds without optimistic marking', async () => {
    const button = renderDom();
    fetch
      .mockResolvedValueOnce(response(200, 'etag-1'))
      .mockResolvedValueOnce(response(412))
      .mockResolvedValueOnce(response(200, 'etag-2'))
      .mockResolvedValueOnce(response(200, 'etag-2'));

    button.click();
    expect(button.classList.contains('is-done')).toBe(false);
    await settle();
    await settle();
    await settle();

    expect(button.classList.contains('is-done')).toBe(true);
    expect(fetch).toHaveBeenCalledTimes(4);
  });

  it('reports a second 412 as a conflict and does not reload', async () => {
    const button = renderDom();
    fetch
      .mockResolvedValueOnce(response(200))
      .mockResolvedValueOnce(response(412))
      .mockResolvedValueOnce(response(200, 'etag-2'))
      .mockResolvedValueOnce(response(412));

    button.click();
    await settle();
    await settle();
    await settle();
    expect(button.classList.contains('is-done')).toBe(false);
    expect(document.querySelector('[data-weekview-status]').textContent).toContain('ändrades');
    expect(document.querySelector('[data-weekview-status]').textContent).toContain('ändrades');
  });

  it('prevents a second click on the same pending button while another button remains independent', async () => {
    const first = renderDom();
    const second = document.createElement('button');
    second.className = 'kostcell-btn';
    second.dataset.departmentId = 'dept-2';
    second.dataset.dietTypeId = 'diet-2';
    second.dataset.year = '2026';
    second.dataset.week = '39';
    second.dataset.dayIndex = '2';
    second.dataset.meal = 'lunch';
    document.body.appendChild(second);
    const firstResponse = {};
    firstResponse.promise = new Promise((resolve) => { firstResponse.resolve = resolve; });
    fetch.mockReturnValueOnce(firstResponse.promise).mockResolvedValueOnce(response(200)).mockResolvedValueOnce(response(200));

    first.click();
    first.click();
    expect(first.disabled).toBe(true);
    second.click();
    await settle();
    await settle();

    expect(fetch).toHaveBeenCalledTimes(3);
    expect(second.classList.contains('is-done')).toBe(true);
    firstResponse.resolve(response(200));
    await settle();
    expect(first.disabled).toBe(false);
  });

  it('does not request a disabled button', async () => {
    const button = renderDom({ disabled: true });

    button.click();
    await settle();

    expect(fetch).not.toHaveBeenCalled();
    expect(button.disabled).toBe(true);
  });

  it('reports network errors and restores the button', async () => {
    const button = renderDom();
    fetch.mockRejectedValueOnce(new Error('offline'));

    button.click();
    await settle();

    expect(document.querySelector('[data-weekview-status]').textContent).toContain('nätverksanslutningen');
    expect(button.disabled).toBe(false);
  });
});
