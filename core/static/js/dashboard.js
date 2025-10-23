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
  const modeLight = document.getElementById('dev-mode-light');
  const modeDark = document.getElementById('dev-mode-dark');
  // Header theme toggle buttons (present on all UI pages)
  const hdrLight = document.getElementById('theme-light');
  const hdrDark = document.getElementById('theme-dark');

  function setMode(mode) {
    const root = document.documentElement;
    root.setAttribute('data-mode', mode === 'light' ? 'light' : 'dark');
    try {
      localStorage.setItem('yu_mode', mode);
      localStorage.setItem('yu-theme', mode); // legacy
    } catch(_){}
  if (modeLight) modeLight.setAttribute('aria-pressed', String(mode === 'light'));
  if (modeDark) modeDark.setAttribute('aria-pressed', String(mode !== 'light'));
  if (hdrLight) hdrLight.setAttribute('aria-pressed', String(mode === 'light'));
  if (hdrDark) hdrDark.setAttribute('aria-pressed', String(mode !== 'light'));
  }

  // Apply saved brand (no on-page brand UI, but respect persisted preference)
  function applySavedBrand() {
    try {
      const b = localStorage.getItem('yu_brand') || localStorage.getItem('yu-brand');
      if (b && b !== 'teal') {
        document.documentElement.setAttribute('data-brand', b);
      }
    } catch(_){ }
  }

  function applySaved() {
    try {
      const m = localStorage.getItem('yu_mode') || localStorage.getItem('yu-theme');
      // Default to light when no saved preference exists
      setMode(m === 'dark' ? 'dark' : 'light');
    } catch(_){}
  }

  if (modeLight) modeLight.addEventListener('click', () => setMode('light'));
  if (modeDark) modeDark.addEventListener('click', () => setMode('dark'));
  if (hdrLight) hdrLight.addEventListener('click', () => setMode('light'));
  if (hdrDark) hdrDark.addEventListener('click', () => setMode('dark'));

  applySavedBrand();
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

  // Tenant create modal (compact impl)
  const m=document.getElementById('tenant-modal'), o=document.getElementById('qa-create-tenant'); if(!m||!o)return; const f=m.querySelector('#tenant-form'), n=f.querySelector('#t-name'), s=f.querySelector('#t-slug'), th=f.querySelector('#t-theme'), en=f.querySelector('#t-enabled'), e=document.getElementById('tenant-error'), c=document.getElementById('t-cancel'); const tok=document.querySelector('meta[name="csrf-token"]')?.content||'';
  // Robust slugify with Swedish chars + safe trimming
  const slug=(x)=>{
    return String(x||'')
      .toLowerCase()
      .trim()
      .replaceAll('å','a').replaceAll('ä','a').replaceAll('ö','o')
      .replace(/[^a-z0-9-]/g,'-')
      .replace(/-+/g,'-')
      .replace(/^-+|-+$/g,'')
      .slice(0,60);
  };
  const trap=ev=>{if(ev.key==='Escape'){close();} if(ev.key==='Tab'){const F=[...m.querySelectorAll('a,button,input,select,textarea')].filter(x=>!x.disabled&&!x.hidden&&x.offsetParent); if(!F.length)return; const i=F.indexOf(document.activeElement); if(ev.shiftKey && (i<=0||document.activeElement===F[0])){F[F.length-1].focus(); ev.preventDefault();} else if(!ev.shiftKey && (i===F.length-1)){F[0].focus(); ev.preventDefault();}}};
  let userEditedSlug=false;
  function open(){m.hidden=false; m.addEventListener('keydown',trap); e.hidden=true; if(!userEditedSlug){ s.value = slug(n.value); } n.focus();}
  function close(){m.hidden=true; m.removeEventListener('keydown',trap);} o.addEventListener('click',ev=>{ev.preventDefault(); open();}); c.addEventListener('click',()=>close());
  // Auto-update slug from name until user edits slug field
  n.addEventListener('input',()=>{ if(!userEditedSlug){ s.value=slug(n.value); }});
  s.addEventListener('keydown',()=>{ userEditedSlug=true; });
  s.addEventListener('input',()=>{ s.value=slug(s.value); });
  f.addEventListener('submit',async ev=>{ev.preventDefault(); e.hidden=true; if(!n.value.trim()){e.textContent='Namn krävs'; e.hidden=false; n.focus(); return;} const body={name:n.value.trim(), slug:s.value.trim()||slug(n.value), theme:th.value, enabled:en.checked}; try{const r=await fetch('/api/superuser/tenants',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':tok},credentials:'same-origin',body:JSON.stringify(body)}); if(r.status===201){ const j=await r.json().catch(()=>({})); close(); const k=document.querySelector('#kpi-tenants [data-kpi-value]'); if(k){const v=parseInt(k.textContent)||0; k.textContent=String(v+1);} const L=document.querySelector('#events-list'); if(L){ const li=document.createElement('li'); li.setAttribute('data-testid','event-item'); li.className='event-row'; const ts=new Date().toISOString(); const id = j && (j.id||j.tenant_id); li.innerHTML=`<span class=\"chip\">TENANT</span><span class=\"title\">${escapeHtml('Tenant skapad – '+body.name+' skapad')}</span>${id?` <a href=\"/tenants/${encodeURIComponent(id)}\" class=\"link\">Öppna</a>`:''}<time datetime=\"${ts}\">${new Date(ts).toLocaleString()}</time>`; L.prepend(li);} f.reset(); userEditedSlug=false; } else { const p=await r.json().catch(()=>({title:'Fel',detail:'Något gick fel'})); e.textContent=(p.title? p.title+': ': '')+(p.detail||'Fel'); e.hidden=false; let target = null; if(p && Array.isArray(p.invalid_params)){ const hasSlug = p.invalid_params.find(v=>v && v.name==='slug'); const hasName = p.invalid_params.find(v=>v && v.name==='name'); if(hasSlug) target = s; else if(hasName) target = n; }
    if(!target){ const preferSlug = /slug/i.test(p.detail||''); target = preferSlug? s : (n.value? s: n); }
    target && target.focus(); } }catch(err){ e.textContent='Nätverksfel'; e.hidden=false; }});
});
