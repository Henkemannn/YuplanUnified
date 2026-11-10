import fs from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(code + `\n//# sourceURL=${relativePath}`);
}

function renderResidenceModal() {
  document.body.innerHTML = `
    <select name="residence_id">
      <option value="">Välj boende</option>
    </select>
    <dialog id="residence-create-modal" class="ua-modal ua-modal-open" open>
      <form action="/ui/admin/residences/new">
        <input name="name" value="Nytt boende">
        <button type="submit">Spara</button>
        <p data-residence-create-status hidden aria-live="polite"></p>
      </form>
    </dialog>
  `;
}

describe('residence create modal', () => {
  beforeEach(() => {
    renderResidenceModal();
    window.fetch = vi.fn();
    loadScript('../js/unified_admin.js');
  });

  it('closes after success and selects the new residence', async () => {
    const dialog = document.querySelector('#residence-create-modal');
    dialog.close = vi.fn(() => dialog.removeAttribute('open'));
    window.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, residence: { id: 'res-1', name: 'Nytt boende' } }),
    });

    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(window.fetch).toHaveBeenCalledTimes(1));
    await vi.waitFor(() => expect(dialog.classList.contains('ua-modal-open')).toBe(false));

    expect(dialog.close).toHaveBeenCalledTimes(1);
    expect(dialog.hasAttribute('open')).toBe(false);
    expect(document.querySelector('select[name="residence_id"]').value).toBe('res-1');
    expect(document.querySelector('select[name="residence_id"] option:last-child').textContent).toBe('Nytt boende');
  });

  it('keeps the modal open and shows an error when the API fails', async () => {
    const dialog = document.querySelector('#residence-create-modal');
    window.fetch.mockResolvedValue({
      ok: false,
      json: async () => ({ ok: false, message: 'Namnet används redan.' }),
    });

    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(window.fetch).toHaveBeenCalledTimes(1));
    await vi.waitFor(() => expect(document.querySelector('[data-residence-create-status]').hidden).toBe(false));

    expect(dialog.hasAttribute('open')).toBe(true);
    expect(dialog.classList.contains('ua-modal-open')).toBe(true);
    expect(document.querySelector('[data-residence-create-status]').textContent).toContain('Namnet används redan.');
  });

  it('uses the fallback close path when native dialog.close is unavailable', async () => {
    const dialog = document.querySelector('#residence-create-modal');
    window.fetch.mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, residence: { id: 'res-2', name: 'Fallbackboende' } }),
    });

    document.querySelector('form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await vi.waitFor(() => expect(dialog.hasAttribute('open')).toBe(false));

    expect(dialog.classList.contains('ua-modal-open')).toBe(false);
  });
});
