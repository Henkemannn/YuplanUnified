import fs from 'node:fs';
import { beforeEach, describe, expect, it, vi } from 'vitest';

function loadScript(relativePath) {
  const url = new URL(relativePath, import.meta.url);
  const code = fs.readFileSync(url, 'utf8');
  window.eval(code + '\n//# sourceURL=' + relativePath);
}

function renderPage3Dom(url = '/ui/kitchen/planering/day/production?ui=product2&site_id=fantasik%C3%B6ket&date=2026-11-09&meal=lunch&view=overview') {
  window.history.replaceState({}, '', url);
  document.body.innerHTML = `
    <div id="yp-product-app" data-page3-site-id="fantasiköket" data-page3-service-date="2026-11-09" data-page3-meal="lunch">
      <nav data-page3-tabs>
        <a data-page3-view-link data-page3-view="overview" href="/ui/kitchen/planering/day/production?ui=product2&site_id=fantasik%C3%B6ket&date=2026-11-09&meal=lunch&view=overview">Översikt</a>
        <a data-page3-view-link data-page3-view="normal" href="/ui/kitchen/planering/day/production?ui=product2&site_id=fantasik%C3%B6ket&date=2026-11-09&meal=lunch&view=normal">Normalkost</a>
        <a data-page3-view-link data-page3-view="addons" href="/ui/kitchen/planering/day/production?ui=product2&site_id=fantasik%C3%B6ket&date=2026-11-09&meal=lunch&option_id=alt-1&view=addons">Serveringsanpassningar</a>
      </nav>
      <nav>
        <a data-page3-special-view-link data-page3-special-view="production" href="/ui/kitchen/planering/day/production?ui=product2&site_id=fantasik%C3%B6ket&date=2026-11-09&meal=lunch&view=special&special_view=production">Produktionslista</a>
        <a data-page3-special-view-link data-page3-special-view="department" href="/ui/kitchen/planering/day/production?ui=product2&site_id=fantasik%C3%B6ket&date=2026-11-09&meal=lunch&view=special&special_view=department">Packlista</a>
      </nav>
      <section data-page3-panel="overview">Översikt</section>
      <section data-page3-panel="normal" hidden>Normalkost</section>
      <section data-page3-panel="addons" hidden>Serveringsanpassningar</section>
      <section data-page3-special-view-panel="production" hidden>Produktionslista</section>
      <section data-page3-special-view-panel="department" hidden>Packlista</section>
    </div>
  `;
  document.dispatchEvent(new Event('DOMContentLoaded'));
}

loadScript('../../static/js/planera_product2_page3.js');

describe('Product2 Page3 server-backed navigation', () => {
  beforeEach(() => {
    document.body.innerHTML = '';
    window.history.replaceState({}, '', '/');
  });

  it('lets overview, normalkost, and addons links perform full navigation', () => {
    renderPage3Dom();
    const pushState = vi.spyOn(window.history, 'pushState');
    const navigationGuard = (event) => event.preventDefault();
    document.addEventListener('click', navigationGuard);

    for (const link of document.querySelectorAll('[data-page3-view-link]')) {
      const event = new MouseEvent('click', { bubbles: true, cancelable: true });
      link.dispatchEvent(event);
    }

    document.removeEventListener('click', navigationGuard);
    expect(pushState).not.toHaveBeenCalled();
    expect(window.location.search).toContain('view=overview');
  });

  it('lets the department packlist link perform full navigation', () => {
    renderPage3Dom();
    const link = document.querySelector('[data-page3-special-view="department"]');
    const pushState = vi.spyOn(window.history, 'pushState');
    const event = new MouseEvent('click', { bubbles: true, cancelable: true });
    const navigationGuard = (clickEvent) => clickEvent.preventDefault();
    document.addEventListener('click', navigationGuard);

    link.dispatchEvent(event);
    document.removeEventListener('click', navigationGuard);
    expect(pushState).not.toHaveBeenCalled();
    expect(link.href).toContain('view=special');
    expect(link.href).toContain('special_view=department');
  });

  it('renders the server-selected addons panel on direct opening and preserves context in hrefs', () => {
    renderPage3Dom('/ui/kitchen/planering/day/production?ui=product2&site_id=fantasik%C3%B6ket&date=2026-11-09&meal=lunch&option_id=alt-1&view=addons');

    expect(document.querySelector('[data-page3-panel="addons"]').hidden).toBe(false);
    expect(document.querySelector('[data-page3-view="addons"]').href).toContain('site_id=fantasik%C3%B6ket');
    expect(document.querySelector('[data-page3-view="addons"]').href).toContain('date=2026-11-09');
    expect(document.querySelector('[data-page3-view="addons"]').href).toContain('meal=lunch');
    expect(document.querySelector('[data-page3-view="addons"]').href).toContain('option_id=alt-1');
    expect(document.querySelector('[data-page3-view="addons"]').href).toContain('view=addons');
  });

  it('keeps browser history navigation on the server-rendered URL state', () => {
    renderPage3Dom();
    window.history.replaceState({}, '', '/ui/kitchen/planering/day/production?ui=product2&view=addons');
    window.dispatchEvent(new PopStateEvent('popstate'));

    expect(document.querySelector('[data-page3-panel="addons"]').hidden).toBe(false);
    expect(window.location.search).toContain('view=addons');
  });
});
