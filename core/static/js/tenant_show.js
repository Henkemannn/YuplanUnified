// Accessible tabs + a11y focus, CSRF header, and Org-enheter modal
document.addEventListener('DOMContentLoaded', () => {
  // Focus H1 for a11y
  const h = document.getElementById('tenant-h1');
  if (h) { if (!h.hasAttribute('tabindex')) h.setAttribute('tabindex', '-1'); h.focus(); }

  // Tabs
  const tabButtons = Array.from(document.querySelectorAll('[role="tablist"] [role="tab"]'));
  const main = document.querySelector('main[data-tenant-id]');
  const storageKey = main && main.getAttribute('data-tenant-id') ? `tenant_tab_${main.getAttribute('data-tenant-id')}` : null;
  function getPanel(btn){ const id = btn && btn.getAttribute('aria-controls'); return id ? document.getElementById(id) : null; }
  function activate(btn, { focus = true } = {}){
    tabButtons.forEach(t => { const sel = t === btn; t.setAttribute('aria-selected', sel ? 'true':'false'); t.tabIndex = sel ? 0 : -1; const p=getPanel(t); if(p) p.hidden = !sel; });
    if (focus) btn.focus(); if (storageKey) { try { localStorage.setItem(storageKey, btn.id); } catch(_){} }
  }
  tabButtons.forEach(t => {
    t.addEventListener('click', () => activate(t));
    t.addEventListener('keydown', (e) => { const i=tabButtons.indexOf(t); let n=i; if(e.key==='ArrowRight') n=(i+1)%tabButtons.length; else if(e.key==='ArrowLeft') n=(i-1+tabButtons.length)%tabButtons.length; else if(e.key==='Home') n=0; else if(e.key==='End') n=tabButtons.length-1; else return; e.preventDefault(); activate(tabButtons[n]); });
  });
  // Deep link support: ?tab=org|overview|modules|flags|settings
  try {
    const url = new URL(window.location.href);
    const tabParam = url.searchParams.get('tab');
    if (tabParam){ const btn = document.getElementById(`tab-${tabParam}`); if (btn && tabButtons.includes(btn)) activate(btn, { focus:false }); }
  } catch(_){ }
  if (storageKey) { try { const last = localStorage.getItem(storageKey); const btn = last && document.getElementById(last); if (btn && tabButtons.includes(btn)) activate(btn, { focus:false }); } catch(_){} }

  // Org-enheter: list + modal create
  if (!main) return; const tid = main.getAttribute('data-tenant-id');
  const list = document.getElementById('org-list');
  const addBtn = document.getElementById('btn-add-org');
  const modal = document.getElementById('org-modal');
  const nameInput = document.getElementById('org-name');
  const typeSelect = document.getElementById('org-type');
  const saveBtn = document.getElementById('org-save');
  const cancelBtn = document.getElementById('org-cancel');
  const errBox = document.getElementById('org-errors');
  const metaCsrf = document.querySelector('meta[name="csrf-token"]');
  function readCookie(n){ return (document.cookie.split('; ').find(r=>r.startsWith(n+'='))||'').split('=')[1]||''; }
  const csrf = () => (metaCsrf && metaCsrf.getAttribute('content')) || readCookie('csrf_token') || '';

  function escapeHtml(s){ return String(s||'').replace(/[&<>"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }
  async function loadOrg(){ if(!list) return; try{ const r=await fetch(`/api/superuser/tenants/${tid}/org-units`); const j=await r.json(); list.innerHTML=''; (j.items||[]).forEach(u=>{ const li=document.createElement('li'); li.tabIndex = 0; li.setAttribute('data-testid','org-item'); li.setAttribute('data-id', String(u.id)); li.innerHTML = `
        <span class="org-name">${escapeHtml(u.name)}</span>
        ${u.slug?` <code class="org-slug">${escapeHtml(u.slug)}</code>`:''}
        ${u.type?` <span class="chip">${escapeHtml(u.type)}</span>`:''}
        <span class="yu-gap-1" style="margin-left:.5rem;">
          <button class="yu-btn yu-btn--tiny" data-testid="org-edit" data-id="${u.id}" aria-label="Byt namn på ${escapeHtml(u.name)}">Byt namn</button>
          <button class="yu-btn yu-btn--tiny yu-btn--danger" data-testid="org-delete" data-id="${u.id}" aria-label="Ta bort ${escapeHtml(u.name)}">Ta bort</button>
        </span>`; list.appendChild(li); }); }catch(_){ /* ignore */ } }

  function openModal(opts){ if(!modal) return; errBox.textContent=''; const title=document.getElementById('org-modal-title'); if(title){ title.textContent = opts && opts.mode==='edit' ? 'Redigera org-enhet' : 'Ny org-enhet'; } modal.hidden=false; const focusables = [nameInput, typeSelect, saveBtn, cancelBtn].filter(Boolean); let first=focusables[0], last=focusables[focusables.length-1]; (nameInput||modal).focus(); function trap(e){ if(e.key!=='Tab') return; const a=document.activeElement; if(e.shiftKey && a===first){ e.preventDefault(); last.focus(); } else if(!e.shiftKey && a===last){ e.preventDefault(); first.focus(); } } function onKey(e){ if(e.key==='Escape'){ closeModal(); } }
    modal.addEventListener('keydown', trap); modal.addEventListener('keydown', onKey);
    modal._cleanup = () => { modal.removeEventListener('keydown', trap); modal.removeEventListener('keydown', onKey); };
  }
  function closeModal(){ if(!modal) return; if (modal._cleanup) modal._cleanup(); modal.hidden=true; }

  async function saveOrg(){ const name=(nameInput && nameInput.value||'').trim(); const type=(typeSelect && typeSelect.value)||'kitchen'; errBox.textContent=''; if(!name || name.length>80){ errBox.textContent='Ange ett giltigt namn (1–80).'; (nameInput||modal).focus(); return; }
    const editId = modal && modal.dataset && modal.dataset.editId;
    const url = editId ? `/api/superuser/tenants/${tid}/org-units/${encodeURIComponent(editId)}` : `/api/superuser/tenants/${tid}/org-units`;
    const method = editId ? 'PATCH' : 'POST';
    const r = await fetch(url, { method, headers:{ 'Content-Type':'application/json', 'X-CSRF-Token': csrf() }, body: JSON.stringify({ name, type }) });
    if (r.ok){ const wasEdit = !!editId; if (modal){ delete modal.dataset.editId; } closeModal(); if (nameInput) nameInput.value=''; await loadOrg(); if (list){ if (wasEdit){ const li = list.querySelector(`[data-id="${editId}"]`); if (li) (li).focus(); } else if (list.lastElementChild) list.lastElementChild.focus(); } }
    else { try{ const j = await r.json(); const d = (j && (j.detail || (j.title+': '+j.status))) || 'Fel'; const inv = (j && j.invalid_params)||[]; errBox.textContent = inv.length ? inv.map(x=>`${x.name}: ${x.reason}`).join(', ') : d; }catch(_){ errBox.textContent = editId ? 'Kunde inte uppdatera org-enhet.' : 'Kunde inte skapa org-enhet.'; } }
  }

  if (addBtn) addBtn.addEventListener('click', ()=>{ if (modal){ delete modal.dataset.editId; } if (nameInput) nameInput.value=''; if (typeSelect) typeSelect.value='kitchen'; openModal({mode:'create'}); });
  if (cancelBtn) cancelBtn.addEventListener('click', (e)=>{ e.preventDefault(); closeModal(); });
  if (saveBtn) saveBtn.addEventListener('click', (e)=>{ e.preventDefault(); saveOrg(); });
  if (nameInput) nameInput.addEventListener('keydown', (e)=>{ if(e.key==='Enter'){ e.preventDefault(); saveOrg(); }});
  // Edit/Delete via event delegation
  if (list) list.addEventListener('click', async (e)=>{
    const t = e.target;
    if (!(t instanceof HTMLElement)) return;
    const id = t.getAttribute('data-id') || (t.closest('[data-id]') && t.closest('[data-id]').getAttribute('data-id'));
    if (!id) return;
    if (t.matches('[data-testid="org-edit"]')){
      // Prefill modal
      const li = t.closest('[data-id]');
      const nm = li && li.querySelector('.org-name') ? li.querySelector('.org-name').textContent : '';
      const typeChip = li && li.querySelector('.chip') ? li.querySelector('.chip').textContent : 'kitchen';
      if (nameInput) nameInput.value = nm || '';
      if (typeSelect) typeSelect.value = (typeChip||'kitchen');
      if (modal) modal.dataset.editId = String(id);
      openModal({mode:'edit'});
    } else if (t.matches('[data-testid="org-delete"]')){
      const confirmed = window.confirm('Ta bort org-enhet?');
      if (!confirmed) return;
      try{
        const r = await fetch(`/api/superuser/tenants/${tid}/org-units/${encodeURIComponent(id)}`, { method:'DELETE', headers:{ 'X-CSRF-Token': csrf() } });
        if (r.status===204){ await loadOrg(); if (list && list.firstElementChild) list.firstElementChild.focus(); }
      }catch(_){ /* ignore */ }
    }
  });
  const tabOrg = document.getElementById('tab-org'); if (tabOrg) tabOrg.addEventListener('click', loadOrg, { once:true });
});
