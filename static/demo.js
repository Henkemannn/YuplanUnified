const $ = (id) => document.getElementById(id);
function getCookie(name){
  return (document.cookie||'').split('; ').map(v=>v.split('=')).find(v=>v[0]===name)?.[1] || '';
}
function etagStrongOrWeak(et){ return et && et.startsWith('W/') ? et : et }

let lastDepts = null, lastDeptsEtag = null; // {site_id, items}
let lastAlt2 = null, lastAlt2Etag = null;   // {week, items}
let lastReportJson = null, lastReportWeek = null;
const demoUiEnabled = (document.body?.dataset?.demoUi === '1');

async function loginAdmin(){
  const res = await fetch('/auth/login', {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({role:'admin'})
  });
  $('loginStatus').textContent = res.ok ? 'OK' : 'Failed';
}

async function loadDepts(){
  const siteId = $('siteId').value.trim();
  if(!siteId){ alert('Enter site_id'); return; }
  const res = await fetch(`/admin/departments?site_id=${encodeURIComponent(siteId)}`);
  lastDeptsEtag = res.headers.get('ETag');
  $('deptsEtag').textContent = lastDeptsEtag || '—';
  lastDepts = await res.json();
  renderDepts(lastDepts);
  // Populate header department select with loaded departments (no extra fetch)
  const deptSel = $('header-dept-select');
  if(deptSel){
    while(deptSel.firstChild) deptSel.removeChild(deptSel.firstChild);
    const blank = document.createElement('option'); blank.value=''; blank.textContent='—'; deptSel.appendChild(blank);
    (lastDepts.items||[]).forEach(d=>{
      const opt = document.createElement('option'); opt.value = d.id; opt.textContent = d.name || d.id; deptSel.appendChild(opt);
    });
  }
}
function renderDepts(data){
  const rows = (data.items||[]).map((it,i)=>{
    const et = `W/"admin:dept:${it.id}:v${it.version||0}"`;
    return `<tr><td>${i+1}</td><td class="mono">${it.id}</td><td>${it.name}</td><td class="mono">${et}</td></tr>`
  }).join('');
  $('depts').innerHTML = `<table><tr><th>#</th><th>id</th><th>name</th><th>item ETag</th></tr>${rows}</table>`;
}
async function depts304(){
  if(!lastDeptsEtag){ alert('Load departments first'); return; }
  const res = await fetch(`/admin/departments?site_id=${encodeURIComponent(lastDepts.site_id)}`, { headers: {'If-None-Match': lastDeptsEtag} });
  alert(`Status: ${res.status} (expected 304)`);
}
async function renameFirst(){
  if(!lastDepts || (lastDepts.items||[]).length===0){ alert('Load departments first'); return; }
  const item = lastDepts.items[0];
  const newName = $('deptNewName').value.trim() || (item.name + ' (demo)');
  const ifMatch = `W/"admin:dept:${item.id}:v${item.version||0}"`;
  const csrf = decodeURIComponent(getCookie('csrf_token'));
  const res = await fetch(`/admin/departments/${encodeURIComponent(item.id)}`, {
    method: 'PUT', headers: {'Content-Type':'application/json', 'If-Match': ifMatch, 'X-CSRF-Token': csrf}, body: JSON.stringify({name:newName})
  });
  $('renameStatus').textContent = res.ok ? 'OK' : `Error ${res.status}`;
  if(res.ok){ await loadDepts(); }
}

async function loadAlt2(){
  const week = Number($('week').value || '0');
  if(!(week>=1 && week<=53)){ alert('Enter valid week (1-53)'); return; }
  const res = await fetch(`/admin/alt2?week=${week}`);
  lastAlt2Etag = res.headers.get('ETag');
  $('alt2Etag').textContent = lastAlt2Etag || '—';
  lastAlt2 = await res.json();
  renderAlt2(lastAlt2);
}
function renderAlt2(data){
  const rows = (data.items||[]).map((it,i)=>{
    const badge = demoUiEnabled && lastAlt2Etag ? ` <span class="alt2-etag" aria-label="Row ETag">${escapeHtml(lastAlt2Etag)}</span>` : '';
    return `<tr><td>${i+1}</td><td class="mono">${it.department_id}</td><td>${it.weekday}</td><td>${it.enabled?'true':'false'}${badge}</td></tr>`
  }).join('');
  $('alt2').innerHTML = `<table><tr><th>#</th><th>department</th><th>weekday</th><th>enabled</th></tr>${rows}</table>`;
}
async function alt2_304(){
  if(!lastAlt2Etag){ alert('Load Alt2 first'); return; }
  const res = await fetch(`/admin/alt2?week=${encodeURIComponent(lastAlt2.week)}`, { headers: {'If-None-Match': lastAlt2Etag} });
  alert(`Status: ${res.status} (expected 304)`);
}
async function alt2_idem(){
  if(!lastAlt2){ alert('Load Alt2 first'); return; }
  const csrf = decodeURIComponent(getCookie('csrf_token'));
  const res = await fetch('/admin/alt2', {
    method: 'PUT', headers: {'Content-Type':'application/json', 'If-Match': lastAlt2Etag, 'X-CSRF-Token': csrf},
    body: JSON.stringify({week: lastAlt2.week, items: lastAlt2.items})
  });
  $('alt2Status').textContent = `${res.ok ? 'OK' : 'Error'} (${res.status})`;
  await loadAlt2();
}
async function alt2_toggle(){
  if(!lastAlt2 || (lastAlt2.items||[]).length===0){ alert('Load Alt2 first'); return; }
  const first = {...lastAlt2.items[0]};
  first.enabled = !first.enabled;
  const csrf = decodeURIComponent(getCookie('csrf_token'));
  const res = await fetch('/admin/alt2', {
    method: 'PUT', headers: {'Content-Type':'application/json', 'If-Match': lastAlt2Etag, 'X-CSRF-Token': csrf},
    body: JSON.stringify({week: lastAlt2.week, items: [first]})
  });
  $('alt2Status').textContent = `${res.ok ? 'OK' : 'Error'} (${res.status})`;
  await loadAlt2();
}

// Hash-based routing (replaces tab UI)
function activateRoute(name){
  document.querySelectorAll('.panel').forEach(sec=>{
    const active = sec.getAttribute('data-panel')===name;
    sec.classList.toggle('panel--active', active);
    if(active){ sec.removeAttribute('hidden'); } else { sec.setAttribute('hidden',''); }
  });
  document.querySelectorAll('.app-nav .nav-link').forEach(a=>{
    const id = a.id || '';
    const active = (id === `nav-${name}`);
    a.classList.toggle('active', active);
    if(active){ a.setAttribute('aria-current','page'); } else { a.removeAttribute('aria-current'); }
  });
}
function currentRoute(){ const h=(location.hash||'').replace(/^#/,''); return (['weekview','admin','alt2','report'].includes(h)?h:'weekview'); }
window.addEventListener('hashchange', ()=> activateRoute(currentRoute()));
document.addEventListener('DOMContentLoaded', ()=>{
  const wkSel = $('header-week-select');
  if(wkSel && wkSel.options.length===0){
    for(let w=45; w<=55; w++){ const o=document.createElement('option'); o.value=String(w); o.textContent=`v${w}`; wkSel.appendChild(o); }
    const initW = Number(($('week')?.value)||51); wkSel.value = String(Math.max(1, Math.min(53, initW)));
  }
  const deptSel = $('header-dept-select');
  if(deptSel && deptSel.options.length===0){ const o=document.createElement('option'); o.value=''; o.textContent='—'; deptSel.appendChild(o); }
  activateRoute(currentRoute());
});

// Keyboard navigation for side nav
document.addEventListener('keydown', (e)=>{
  const nav = document.querySelector('.app-nav'); if(!nav) return;
  const links = Array.from(nav.querySelectorAll('.nav-link')); if(links.length===0) return;
  const idx = links.indexOf(document.activeElement); if(idx<0) return;
  if(e.key==='ArrowDown'){ e.preventDefault(); links[(idx+1)%links.length].focus(); }
  else if(e.key==='ArrowUp'){ e.preventDefault(); links[(idx-1+links.length)%links.length].focus(); }
});

// Existing event bindings
const el = (id)=>document.getElementById(id);
el('btnLogin')?.addEventListener('click', loginAdmin);
el('btnLoadDepts')?.addEventListener('click', loadDepts);
el('btnDepts304')?.addEventListener('click', depts304);
el('btnRename')?.addEventListener('click', renameFirst);
el('btnLoadAlt2')?.addEventListener('click', loadAlt2);
el('btnAlt2304')?.addEventListener('click', alt2_304);
el('btnAlt2Idem')?.addEventListener('click', alt2_idem);
el('btnAlt2Toggle')?.addEventListener('click', alt2_toggle);

// Fallback for logo if image fails (no inline onerror to satisfy CSP)
(() => {
  const img = document.getElementById('ylogo');
  const mark = document.getElementById('ymark');
  if(!img || !mark) return;
  img.addEventListener('error', ()=>{ mark.style.display='grid'; img.style.display='none'; });
})();

// --- Report summary ---
(function setupReport(){
  const weekInp = document.getElementById('reportWeek');
  const btn = document.getElementById('btnLoadReport');
  const box = document.getElementById('reportSummary');
  if(!weekInp || !btn || !box) return;

  // init with current ISO-ish week if empty
  if(!weekInp.value){
    const d=new Date(), onejan=new Date(d.getFullYear(),0,1);
    const week=Math.ceil((((d - onejan) / 86400000) + onejan.getDay()+1)/7);
    weekInp.value = Math.min(Math.max(week,1),53);
  }

  let etag = null;

  async function loadReport(){
    const w = Number(weekInp.value||0);
    if(!w || w<1 || w>53){ box.innerHTML = `<div class="muted">Ogiltig vecka.</div>`; return; }
    const hdrs = {'Accept':'application/json'};
    if(etag) hdrs['If-None-Match'] = etag;
    try{
      // Year assumption: current year (could be extended with selector later)
      const year = new Date().getFullYear();
      const res = await fetch(`/api/report?year=${year}&week=${w}`, {headers: hdrs, credentials:'include'});
      if(res.status === 304) return; // unchanged
      if(!res.ok){
        box.innerHTML = `<div class="muted">Kunde inte hämta rapport (HTTP ${res.status}).</div>`;
        return;
      }
      etag = res.headers.get('ETag') || etag;
      const data = await res.json();
      lastReportJson = data; lastReportWeek = w;
      const totals = safeTotals(data);
      box.innerHTML = renderCards(totals, w);
    }catch(e){
      box.innerHTML = `<div class="muted">Fel vid hämtning av rapport.</div>`;
    }
  }

  function safeTotals(d){
    const t = (d && d.totals) || {};
    const lunch = t.lunch || {};
    const eve   = t.evening || t.kväll || {};
    return {
      lunchNormal: Number(lunch.normal || lunch.normalkost || 0),
      lunchSpecial: Number(lunch.special || lunch.specialkost || 0),
      eveNormal: Number(eve.normal || eve.normalkost || 0),
      eveSpecial: Number(eve.special || eve.specialkost || 0),
      allNormal: Number((lunch.normal||0)+(eve.normal||0)),
      allSpecial: Number((lunch.special||0)+(eve.special||0)),
      departments: Array.isArray(d?.departments)? d.departments.length : (Number(d?.department_count)||0)
    };
  }

  function renderCards(t, week){
    return [
      card(`Statistik för vecka ${week}`, `${t.departments} avdelningar`, 'Översikt'),
      card('Normalkost (totalt)', t.allNormal, 'Lunch + kväll'),
      card('Specialkost (totalt)', t.allSpecial, 'Lunch + kväll'),
      card('Lunch – normalkost', t.lunchNormal, 'Summa'),
      card('Lunch – specialkost', t.lunchSpecial, 'Summa'),
      card('Kväll – normalkost', t.eveNormal, 'Summa'),
      card('Kväll – specialkost', t.eveSpecial, 'Summa')
    ].join('');
  }

  function card(title, metric, sub){
    return `<div class="card"><div class="muted">${escapeHtml(String(title))}</div>
      <div class="metric">${escapeHtml(String(metric))}</div>
      <div class="muted">${escapeHtml(String(sub))}</div></div>`;
  }

  function escapeHtml(s){
    const map = { '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;' };
    return String(s).replace(/[&<>"']/g, m=>map[m]);
  }

  btn.addEventListener('click', loadReport);
  document.getElementById('tab-report')?.addEventListener('click', loadReport);
  const btnCsv = document.getElementById('btnExportCsv');
  btnCsv?.addEventListener('click', ()=>{
    if(!lastReportJson || !lastReportWeek){
      box.innerHTML = `<div class="muted">Ingen rapport inläst ännu – klicka \"Läs in\" först.</div>`;
      return;
    }
    exportReportCsv(lastReportJson, lastReportWeek);
  });
})();

// CSV export utilities
function exportReportCsv(reportJson, week){
  const header = ["Department","Lunch special","Lunch normal","Evening special","Evening normal","Total"];
  const rows = [];
  const items = Array.isArray(reportJson?.rows) ? reportJson.rows
    : (Array.isArray(reportJson?.departments) ? reportJson.departments : null);
  if(items){
    for(const r of items){
      const dept = r.department || r.name || r.department_name || '';
      const lunch = r.lunch || {};
      const evening = r.evening || r.kväll || {};
      const total = r.total ?? ((lunch.normal||0)+(lunch.special||0)+(evening.normal||0)+(evening.special||0));
      rows.push([
        dept,
        lunch.special ?? lunch.specialkost ?? 0,
        lunch.normal ?? lunch.normalkost ?? 0,
        evening.special ?? evening.specialkost ?? 0,
        evening.normal ?? evening.normalkost ?? 0,
        total ?? 0
      ]);
    }
  } else {
    const t = (reportJson && reportJson.totals) || {};
    const lunch = t.lunch || {};
    const eve = t.evening || t.kväll || {};
    const total = (lunch.normal||0)+(lunch.special||0)+(eve.normal||0)+(eve.special||0);
    rows.push(['Totals', lunch.special||0, lunch.normal||0, eve.special||0, eve.normal||0, total]);
  }
  const out = [header, ...rows].map(cols => cols.map(csvEscape).join(',')).join('\r\n');
  const BOM = '\uFEFF';
  const blob = new Blob([BOM + out], { type: 'text/csv;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `report_week_${week}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(()=>URL.revokeObjectURL(a.href), 1500);
}
function csvEscape(v){ return '"' + String(v ?? '').replace(/"/g,'""') + '"'; }

// Escape HTML used in ETag badge
// (duplicate guard) already defined above for cards; reused for ETag badge
