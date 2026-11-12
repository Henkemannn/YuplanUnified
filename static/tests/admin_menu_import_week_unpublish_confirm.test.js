import { beforeEach, describe, expect, it, vi } from 'vitest';
import fs from 'node:fs';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(`${code}\n//# sourceURL=${relativePath}`);
}

describe('Admin unpublish confirmation', () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <form action="/ui/admin/menu-import/week/2025/47/unpublish" method="POST">
        <input name="_etag" value="etag-1">
        <input name="_confirm_unpublish" value="0" data-unpublish-confirmation>
        <button type="submit">Återgå till utkast</button>
      </form>
      <dialog data-unpublish-confirmation-dialog>
        <form method="dialog">
          <button type="submit" data-unpublish-confirmation-cancel>Avbryt</button>
          <button type="button" data-unpublish-confirmation-confirm>Återgå till utkast</button>
        </form>
      </dialog>
    `;

    const dialog = document.querySelector('[data-unpublish-confirmation-dialog]');
    dialog.showModal = vi.fn(() => {
      dialog.open = true;
    });
    dialog.close = vi.fn(() => {
      dialog.open = false;
    });
    const form = document.querySelector('form[action$="/unpublish"]');
    form.requestSubmit = vi.fn();
  });

  it('opens without submitting, then submits once after confirmation', () => {
    loadScript('../../static/ui/admin_menu_import_week_unpublish_confirm.js');

    const form = document.querySelector('form[action$="/unpublish"]');
    const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
    form.dispatchEvent(submitEvent);

    expect(submitEvent.defaultPrevented).toBe(true);
    expect(form.requestSubmit).not.toHaveBeenCalled();

    document.querySelector('[data-unpublish-confirmation-confirm]').click();

    expect(document.querySelector('[data-unpublish-confirmation]').value).toBe('1');
    expect(form.requestSubmit).toHaveBeenCalledTimes(1);
  });

  it('allows the confirmed submit through without opening the dialog again', () => {
    loadScript('../../static/ui/admin_menu_import_week_unpublish_confirm.js');

    const form = document.querySelector('form[action$="/unpublish"]');
    const confirmation = document.querySelector('[data-unpublish-confirmation]');
    const dialog = document.querySelector('[data-unpublish-confirmation-dialog]');
    confirmation.value = '1';

    const submitEvent = new Event('submit', { bubbles: true, cancelable: true });
    form.dispatchEvent(submitEvent);

    expect(submitEvent.defaultPrevented).toBe(false);
    expect(dialog.showModal).not.toHaveBeenCalled();
  });

  it('cancels without submitting or activating confirmation', () => {
    loadScript('../../static/ui/admin_menu_import_week_unpublish_confirm.js');

    const form = document.querySelector('form[action$="/unpublish"]');
    const confirmation = document.querySelector('[data-unpublish-confirmation]');
    const dialog = document.querySelector('[data-unpublish-confirmation-dialog]');
    const cancelButton = document.querySelector('[data-unpublish-confirmation-cancel]');

    cancelButton.addEventListener('click', (event) => {
      event.preventDefault();
      dialog.close('cancel');
    });
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    cancelButton.click();

    expect(confirmation.value).toBe('0');
    expect(form.requestSubmit).not.toHaveBeenCalled();
    expect(dialog.showModal).toHaveBeenCalledTimes(1);
    expect(dialog.close).toHaveBeenCalledWith('cancel');
  });

  it('leaves native cancel and Escape without a POST or confirmation', () => {
    loadScript('../../static/ui/admin_menu_import_week_unpublish_confirm.js');

    const form = document.querySelector('form[action$="/unpublish"]');
    const confirmation = document.querySelector('[data-unpublish-confirmation]');
    const dialog = document.querySelector('[data-unpublish-confirmation-dialog]');
    const cancelEvent = new Event('cancel', { bubbles: true, cancelable: true });

    dialog.addEventListener('cancel', () => {
      dialog.close('cancel');
    });
    form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    dialog.dispatchEvent(cancelEvent);

    expect(cancelEvent.defaultPrevented).toBe(false);
    expect(confirmation.value).toBe('0');
    expect(form.requestSubmit).not.toHaveBeenCalled();
    expect(dialog.showModal).toHaveBeenCalledTimes(1);
    expect(dialog.close).toHaveBeenCalledWith('cancel');
  });
});
