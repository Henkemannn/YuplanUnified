(function(){
  function $(sel, root){ return (root||document).querySelector(sel); }
  function $all(sel, root){ return Array.from((root||document).querySelectorAll(sel)); }
  function openDialog(dlg){ try { dlg.showModal(); } catch(_) { dlg.setAttribute('open','open'); } }
  function closeDialog(dlg){ try { dlg.close(); } catch(_) { dlg.removeAttribute('open'); } }

  document.addEventListener('DOMContentLoaded', function(){
    const dlg = document.getElementById('alt2Modal');
    if(!dlg) return;
    const bodyEl = $('#alt2ModalBody', dlg) || dlg;
    const yearEl = $('#alt2-year', dlg);
    const weekEl = $('#alt2-week', dlg);
    const saveBtn = $('#alt2-save', dlg);
    const statusEl = $('#alt2-status', dlg);
    const dayNames = {mon:'Mån',tue:'Tis',wed:'Ons',thu:'Tors',fri:'Fre',sat:'Lör',sun:'Sön'};
    const order = ['mon','tue','wed','thu','fri','sat','sun'];
    let selected = [];
    let departmentId = null;

    function render(){
      let html = '<div class="ua-badges alt2-toggles">';
      for(const d of order){
        const active = selected.includes(d);
        html += `<button type="button" class="ua-badge ${active ? 'ua-badge-success' : 'ua-badge-muted'}" data-day="${d}">${dayNames[d]}</button>`;
      }
      html += '</div>';
      bodyEl.innerHTML = html;
      $all('button[data-day]', bodyEl).forEach(el => {
        el.addEventListener('click', function(){
          const d = el.getAttribute('data-day');
          const i = selected.indexOf(d);
          if(i>=0) selected.splice(i,1); else selected.push(d);
          selected.sort((a,b)=>order.indexOf(a)-order.indexOf(b));
          render();
        });
      });
    }

    async function load(){
      if(!departmentId) return;
      const y = parseInt(yearEl && yearEl.value || (new Date()).getFullYear(), 10);
      const w = parseInt(weekEl && weekEl.value || 1, 10);
      bodyEl.innerHTML = '<p class="ua-muted">Hämtar...</p>';
      try{
        const r = await fetch(`/ui/admin/departments/${departmentId}/alt2?year=${y}&week=${w}`, { headers: { 'X-User-Role': 'admin', 'X-Tenant-Id': '1' } });
        if(!r.ok){ bodyEl.innerHTML = '<p class="ua-error">Kunde inte hämta Alt2.</p>'; return; }
        const data = await r.json();
        selected = Array.isArray(data.alt2_days) ? data.alt2_days.slice() : [];
        render();
      } catch(e){ bodyEl.innerHTML = '<p class="ua-error">Fel vid hämtning.</p>'; }
    }

    async function save(){
      if(!departmentId) return;
      if(statusEl) statusEl.textContent = '';
      const y = parseInt(yearEl && yearEl.value || (new Date()).getFullYear(), 10);
      const w = parseInt(weekEl && weekEl.value || 1, 10);
      try{
        const r = await fetch(`/ui/admin/departments/${departmentId}/alt2`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-User-Role': 'admin', 'X-Tenant-Id': '1' },
          body: JSON.stringify({ year: y, week: w, alt2_days: selected })
        });
        if(!r.ok){ if(statusEl) statusEl.textContent = 'Kunde inte spara.'; return; }
        const data = await r.json();
        selected = Array.isArray(data.alt2_days) ? data.alt2_days.slice() : [];
        render();
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

    $all('[data-modal-close]', dlg).forEach(function(el){ el.addEventListener('click', function(){ closeDialog(dlg); }); });
    if(yearEl) yearEl.addEventListener('change', load);
    if(weekEl) weekEl.addEventListener('change', load);
    if(saveBtn) saveBtn.addEventListener('click', save);
  });
})();
