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
    const fullDayNames = { mon: 'Måndag', tue: 'Tisdag', wed: 'Onsdag', thu: 'Torsdag', fri: 'Fredag', sat: 'Lördag', sun: 'Söndag' };
    const dayLabels = { mon: 'Mån', tue: 'Tis', wed: 'Ons', thu: 'Tors', fri: 'Fre', sat: 'Lör', sun: 'Sön' };
    let choicesByDay = {};
    let departmentId = null;
    let siteId = null;
    const hiddenInput = $('#alt2-days', dlg);

    // Apply selection classes to existing day buttons
    function updateHidden(){
      if(!hiddenInput) return;
      const ordered = order.filter(function(day){ return choicesByDay[day] === 'Alt2'; });
      hiddenInput.value = ordered.join(',');
    }

    function normalizeChoice(value){
      if(value === 'Alt1' || value === 'alt1' || value === 1) return 'Alt1';
      if(value === 'Alt2' || value === 'alt2' || value === 2) return 'Alt2';
      return null;
    }

    function stateClass(choice){
      return choice === 'Alt2' ? 'is-alt2' : (choice === 'Alt1' ? 'is-alt1' : 'is-none');
    }

    function stateLabel(choice){
      return choice === 'Alt2' ? 'Alt2' : (choice === 'Alt1' ? 'Alt1' : 'inget explicit val');
    }

    function ensureChoiceMap(source){
      const next = {};
      order.forEach(function(day){
        next[day] = normalizeChoice(source && source[day]);
      });
      return next;
    }

    function renderButtons(){
      $all('.js-alt2-day', bodyEl).forEach(function(btn){
        const short = (btn.getAttribute('data-day') || '').trim();
        const activeChoice = normalizeChoice(choicesByDay[short]);
        const label = dayLabels[short] || short;
        btn.classList.remove('is-none', 'is-alt1', 'is-alt2');
        btn.classList.add(stateClass(activeChoice));
        btn.setAttribute('aria-pressed', activeChoice === 'Alt2' ? 'true' : 'false');
        btn.setAttribute('aria-label', (fullDayNames[short] || label) + ', ' + stateLabel(activeChoice));
        btn.setAttribute('title', stateLabel(activeChoice));
        btn.setAttribute('data-choice', activeChoice || '');
        btn.textContent = label;
      });
      updateHidden();
    }

    function toggleChoice(day){
      if(!day) return;
      const current = normalizeChoice(choicesByDay[day]);
      choicesByDay = Object.assign({}, choicesByDay, { [day]: current === 'Alt2' ? 'Alt1' : 'Alt2' });
      renderButtons();
    }

    async function load(){
      if(!departmentId) return;
      const y = parseInt(yearEl && yearEl.value || (new Date()).getFullYear(), 10);
      const w = parseInt(weekEl && weekEl.value || 1, 10);
      const siteQ = siteId ? ('&site_id=' + encodeURIComponent(siteId)) : '';
      // Keep existing buttons; just show loading state subtly
      const old = bodyEl.innerHTML;
      bodyEl.setAttribute('data-loading', '1');
      try{
        const r = await fetch(`/ui/admin/departments/${departmentId}/alt2?year=${y}&week=${w}${siteQ}`, { credentials: 'same-origin' });
        if(!r.ok){
          var msg = 'Kunde inte hämta Alt2.';
          try {
            const err = await r.json();
            if(err && err.message){ msg += ' ' + String(err.message); }
          } catch(_) {}
          bodyEl.innerHTML = '<p class="ua-error">' + msg + '</p>';
          return;
        }
        const data = await r.json();
        if(data && data.choices && typeof data.choices === 'object'){
          choicesByDay = ensureChoiceMap(data.choices);
        } else {
          const selected = new Set(Array.isArray(data.alt2_days) ? data.alt2_days.slice() : []);
          choicesByDay = {};
          order.forEach(function(day){
            choicesByDay[day] = selected.has(day) ? 'Alt2' : 'Alt1';
          });
        }
        renderButtons();
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
        const nextChoices = {};
        order.forEach(function(day){
          nextChoices[day] = normalizeChoice(choicesByDay[day]);
        });
        const r = await fetch(`/ui/admin/departments/${departmentId}/alt2`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(csrf ? { 'X-CSRF-Token': csrf } : {}),
            'X-Requested-With': 'XMLHttpRequest',
          },
          body: JSON.stringify({ year: y, week: w, choices: nextChoices, site_id: siteId || '' })
        , credentials: 'same-origin' });
        if(!r.ok){ if(statusEl) statusEl.textContent = 'Kunde inte spara.'; return; }
        const data = await r.json();
        if(data && data.choices && typeof data.choices === 'object'){
          choicesByDay = ensureChoiceMap(data.choices);
        } else {
          const selected = new Set(Array.isArray(data.alt2_days) ? data.alt2_days.slice() : []);
          choicesByDay = {};
          order.forEach(function(day){
            choicesByDay[day] = selected.has(day) ? 'Alt2' : 'Alt1';
          });
        }
        renderButtons();
        if(statusEl){ statusEl.textContent = 'Sparat ✔'; setTimeout(function(){ statusEl.textContent=''; }, 1500); }
      } catch(e){ if(statusEl) statusEl.textContent = 'Fel vid sparande.'; }
    }

    document.body.addEventListener('click', function(ev){
      const t = ev.target.closest('.js-open-alt2');
      if(!t) return;
      ev.preventDefault();
      departmentId = t.getAttribute('data-department-id');
      siteId = t.getAttribute('data-site-id');
      openDialog(dlg);
      load();
    });

    // Event delegation for day toggles
    bodyEl.addEventListener('click', function(ev){
      const btn = ev.target && ev.target.closest('.js-alt2-day');
      if(!btn) return;
      const short = (btn.getAttribute('data-day') || '').trim();
      if(!short || order.indexOf(short) === -1) return;
      toggleChoice(short);
    });

    $all('[data-modal-close]', dlg).forEach(function(el){ el.addEventListener('click', function(){ closeDialog(dlg); }); });
    if(yearEl) yearEl.addEventListener('change', load);
    if(weekEl) weekEl.addEventListener('change', load);
    const saveEl = $('.js-alt2-save', dlg) || saveBtn;
    if(saveEl) saveEl.addEventListener('click', save);
  });
})();
