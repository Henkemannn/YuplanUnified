(function(){
  function $(sel, root){ return (root||document).querySelector(sel); }
  function $all(sel, root){ return Array.from((root||document).querySelectorAll(sel)); }
  function openDialog(dlg){ try { dlg.showModal(); } catch(_) { dlg.setAttribute('open','open'); } }
  function closeDialog(dlg){ try { dlg.close(); } catch(_) { dlg.removeAttribute('open'); } }
  function getCookie(name){
    try {
      var m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
      return m ? decodeURIComponent(m[2]) : null;
    } catch(_) { return null; }
  }

  document.addEventListener('DOMContentLoaded', function(){
    const dlg = document.getElementById('alt2Modal');
    if(!dlg) return;
    const bodyEl = $('#alt2ModalBody', dlg) || dlg;
    const yearEl = $('#alt2-year', dlg);
    const weekEl = $('#alt2-week', dlg);
    const saveBtn = $('#alt2-save', dlg);
    const statusEl = $('#alt2-status', dlg);
    const order = ['mon','tue','wed','thu','fri','sat','sun'];
    let selected = [];
    let departmentId = null;

    // Apply selection classes to existing day buttons
    function applySelection(){
      const idxToShort = order;
      $all('.js-alt2-day', bodyEl).forEach(function(btn){
        const idx = parseInt(btn.getAttribute('data-day-index') || '-1', 10);
        const short = idxToShort[idx];
        const active = short && selected.includes(short);
        btn.classList.toggle('is-alt2-selected', !!active);
      });
    }

    async function load(){
      if(!departmentId) return;
      const y = parseInt(yearEl && yearEl.value || (new Date()).getFullYear(), 10);
      const w = parseInt(weekEl && weekEl.value || 1, 10);
      // Keep existing buttons; just show loading state subtly
      const old = bodyEl.innerHTML;
      bodyEl.setAttribute('data-loading', '1');
      try{
        const r = await fetch(`/ui/admin/departments/${departmentId}/alt2?year=${y}&week=${w}`, { credentials: 'same-origin' });
        if(!r.ok){ bodyEl.innerHTML = '<p class="ua-error">Kunde inte hämta Alt2.</p>'; return; }
        const data = await r.json();
        selected = Array.isArray(data.alt2_days) ? data.alt2_days.slice() : [];
        applySelection();
      } catch(e){ bodyEl.innerHTML = '<p class="ua-error">Fel vid hämtning.</p>'; }
      bodyEl.removeAttribute('data-loading');
    }

    async function save(){
      if(!departmentId) return;
      if(statusEl) statusEl.textContent = '';
      const y = parseInt(yearEl && yearEl.value || (new Date()).getFullYear(), 10);
      const w = parseInt(weekEl && weekEl.value || 1, 10);
      try{
        const csrf = getCookie('csrf_token');
        const r = await fetch(`/ui/admin/departments/${departmentId}/alt2`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ year: y, week: w, alt2_days: selected })
        , credentials: 'same-origin' });
        if(!r.ok){ if(statusEl) statusEl.textContent = 'Kunde inte spara.'; return; }
        const data = await r.json();
        selected = Array.isArray(data.alt2_days) ? data.alt2_days.slice() : [];
        applySelection();
        if(statusEl){ statusEl.textContent = 'Sparat ✔'; setTimeout(function(){ statusEl.textContent=''; }, 1500); }
      } catch(e){ if(statusEl) statusEl.textContent = 'Fel vid sparande.'; }
    }

    document.body.addEventListener('click', function(ev){
      const t = ev.target.closest('.js-open-alt2');
      if(!t) return;
      ev.preventDefault();
      departmentId = t.getAttribute('data-department-id');
      openDialog(dlg);
      load();
    });

    // Event delegation for day toggles
    bodyEl.addEventListener('click', function(ev){
      const btn = ev.target && ev.target.closest('.js-alt2-day');
      if(!btn) return;
      const idx = parseInt(btn.getAttribute('data-day-index') || '-1', 10);
      if(isNaN(idx) || idx < 0 || idx > 6) return;
      const short = order[idx];
      const i = selected.indexOf(short);
      if(i>=0) selected.splice(i,1); else selected.push(short);
      selected.sort(function(a,b){ return order.indexOf(a) - order.indexOf(b); });
      btn.classList.toggle('is-alt2-selected');
    });

    $all('[data-modal-close]', dlg).forEach(function(el){ el.addEventListener('click', function(){ closeDialog(dlg); }); });
    if(yearEl) yearEl.addEventListener('change', load);
    if(weekEl) weekEl.addEventListener('change', load);
    const saveEl = $('.js-alt2-save', dlg) || saveBtn;
    if(saveEl) saveEl.addEventListener('click', save);
  });
})();
