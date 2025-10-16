async function jget(url){
  const r = await fetch(url, {credentials: 'same-origin'});
  if(!r.ok){
    let prob;
    try { prob = await r.json(); } catch(_){ prob = {title:'Fel', detail: String(r.status)} }
    throw prob;
  }
  return r.json();
}

function setKPI(sel, val){
  const el = document.querySelector(sel + ' [data-kpi-value]');
  if(el){ el.textContent = String(val); el.closest('.kpi-card')?.removeAttribute('aria-busy'); }
}

async function loadSummary(){
  const d = await jget('/api/superuser/summary');
  setKPI('#kpi-tenants', d.tenants_total);
  setKPI('#kpi-modules', d.modules_active);
  setKPI('#kpi-flags', d.feature_flags_on);
}

async function loadEvents(){
  const d = await jget('/api/superuser/events?limit=20');
  const list = document.querySelector('#events-list');
  const empty = document.querySelector('#events-empty');
  if(!list) return;
  list.innerHTML='';
  if(!d.items || !d.items.length){
    if(empty) empty.removeAttribute('hidden');
    return;
  }
  if(empty) empty.setAttribute('hidden','');
  d.items.forEach(e => {
    const li = document.createElement('li');
    li.setAttribute('data-testid','event-item');
    li.className = 'event-row';
    li.innerHTML = `<span class="chip">${e.badge}</span><span class="title">${escapeHtml(e.title||e.kind)}</span><time datetime="${e.ts}">${new Date(e.ts).toLocaleString()}</time>`;
    list.appendChild(li);
  });
}

async function loadHealth(){
  const d = await jget('/api/superuser/health');
  renderBadge('#health-api', d.api, 'API');
  renderBadge('#health-db', d.db, 'DB');
  renderBadge('#health-queue', d.queue, 'Queue');
}

function renderBadge(sel, status, label){
  const el = document.querySelector(sel);
  if(!el) return;
  el.textContent = `${label}: ${status}`;
  el.className = 'badge ' + (status === 'OK' ? 'badge-success' : 'badge-warn');
}

function escapeHtml(str){
  return String(str).replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[s]||s));
}

document.addEventListener('DOMContentLoaded', () => {
  // Focus management: move focus to H1 on navigation
  const h1 = document.getElementById('page-title');
  if (h1 && typeof h1.focus === 'function') {
    // Ensure it is programmatically focusable
    if (!h1.hasAttribute('tabindex')) h1.setAttribute('tabindex', '-1');
    h1.focus();
  }

  // Dev-only theme preview (elements exist only when dev flag enabled)
  const brandOcean = document.getElementById('dev-brand-ocean');
  const brandEmerald = document.getElementById('dev-brand-emerald');
  const brandTeal = document.getElementById('dev-brand-teal');
  const modeLight = document.getElementById('dev-mode-light');
  const modeDark = document.getElementById('dev-mode-dark');

  function setBrand(brand) {
    const root = document.documentElement;
    if (!brand || brand === 'teal') root.removeAttribute('data-brand');
    else root.setAttribute('data-brand', brand);
    try {
      localStorage.setItem('yu_brand', brand || 'teal');
      localStorage.setItem('yu-brand', brand || 'teal');
    } catch(_){}
    if (brandOcean) brandOcean.setAttribute('aria-pressed', String(brand === 'ocean'));
    if (brandEmerald) brandEmerald.setAttribute('aria-pressed', String(brand === 'emerald'));
    if (brandTeal) brandTeal.setAttribute('aria-pressed', String(!brand || brand === 'teal'));
  }

  function setMode(mode) {
    const root = document.documentElement;
    root.setAttribute('data-mode', mode === 'light' ? 'light' : 'dark');
    try {
      localStorage.setItem('yu_mode', mode);
      localStorage.setItem('yu-theme', mode); // legacy
    } catch(_){}
    if (modeLight) modeLight.setAttribute('aria-pressed', String(mode === 'light'));
    if (modeDark) modeDark.setAttribute('aria-pressed', String(mode !== 'light'));
  }

  function applySaved() {
    try {
      const b = localStorage.getItem('yu_brand') || localStorage.getItem('yu-brand');
      setBrand(b && b !== 'teal' ? b : 'teal');
      const m = localStorage.getItem('yu_mode') || localStorage.getItem('yu-theme');
      setMode(m === 'light' ? 'light' : 'dark');
    } catch(_){}
  }

  if (brandOcean) brandOcean.addEventListener('click', () => setBrand('ocean'));
  if (brandEmerald) brandEmerald.addEventListener('click', () => setBrand('emerald'));
  if (brandTeal) brandTeal.addEventListener('click', () => setBrand('teal'));
  if (modeLight) modeLight.addEventListener('click', () => setMode('light'));
  if (modeDark) modeDark.addEventListener('click', () => setMode('dark'));

  applySaved();

  // Load dashboard data
  (async () => {
    try {
      await Promise.all([loadSummary(), loadEvents(), loadHealth()]);
    } catch(err){
      // Silently log; optional future UI alert
      console.warn('Dashboard load error', err);
    }
  })();
});
