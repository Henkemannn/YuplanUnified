(function(){
  function $(sel, root){ return (root || document).querySelector(sel); }
  function $all(sel, root){ return Array.from((root || document).querySelectorAll(sel)); }
  function openDialog(dlg){ try { dlg.showModal(); } catch(_) { dlg.setAttribute('open', 'open'); } }
  function closeDialog(dlg){ try { dlg.close(); } catch(_) { dlg.removeAttribute('open'); } }
  function getCookie(name){
    try {
      var m = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
      return m ? decodeURIComponent(m[2]) : null;
    } catch(_) {
      return null;
    }
  }

  document.addEventListener('DOMContentLoaded', function(){
    var dlg = document.getElementById('dietOverrideModal');
    if(!dlg) return;

    var statusEl = $('#dietOverrideStatus', dlg);
    var nameEl = $('#dietOverrideName', dlg);
    var saveBtn = $('.js-diet-override-save', dlg);
    var resetBtn = $('.js-diet-override-reset', dlg);
    var closeEls = $all('[data-modal-close]', dlg);
    var inputs = $all('.admin-diet-override-input', dlg);

    var state = {
      departmentId: null,
      dietTypeId: null,
      baseCount: 0,
      dietName: ''
    };

    function setStatus(msg){
      if(statusEl) statusEl.textContent = msg || '';
    }

    function setInputsToBase(){
      inputs.forEach(function(input){
        input.value = String(state.baseCount || 0);
      });
    }

    function applyOverrides(rows){
      setInputsToBase();
      (rows || []).forEach(function(row){
        var day = String(row.day || '');
        var meal = String(row.meal || '');
        var count = parseInt(row.count || 0, 10);
        var el = $('.admin-diet-override-input[data-day="' + day + '"][data-meal="' + meal + '"]', dlg);
        if(el) el.value = String(Number.isFinite(count) ? count : 0);
      });
    }

    function readEntries(){
      return inputs.map(function(input){
        var day = parseInt(input.getAttribute('data-day') || '0', 10);
        var meal = String(input.getAttribute('data-meal') || '').toLowerCase();
        var count = parseInt(input.value || '0', 10);
        if(!Number.isFinite(count) || count < 0) count = 0;
        return { day: day, meal: meal, count: count };
      });
    }

    async function loadOverrides(){
      if(!state.departmentId || !state.dietTypeId) return;
      setStatus('Hämtar...');
      try {
        var r = await fetch('/ui/admin/departments/' + state.departmentId + '/diet-overrides?diet_type_id=' + encodeURIComponent(state.dietTypeId), {
          credentials: 'same-origin'
        });
        if(!r.ok){
          setStatus('Kunde inte hämta.');
          return;
        }
        var data = await r.json();
        state.baseCount = parseInt(data.base_count || 0, 10) || 0;
        applyOverrides(data.overrides || []);
        setStatus('');
      } catch(_) {
        setStatus('Fel vid hämtning.');
      }
    }

    async function saveOverrides(){
      if(!state.departmentId || !state.dietTypeId) return;
      setStatus('Sparar...');
      try {
        var csrf = getCookie('csrf_token');
        var r = await fetch('/ui/admin/departments/' + state.departmentId + '/diet-overrides', {
          method: 'POST',
          credentials: 'same-origin',
          headers: Object.assign({
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          }, csrf ? { 'X-CSRF-Token': csrf } : {}),
          body: JSON.stringify({
            diet_type_id: state.dietTypeId,
            entries: readEntries()
          })
        });
        if(!r.ok){
          setStatus('Kunde inte spara.');
          return;
        }
        setStatus('Sparat.');
      } catch(_) {
        setStatus('Fel vid sparande.');
      }
    }

    async function resetOverrides(){
      if(!state.departmentId || !state.dietTypeId) return;
      setStatus('Återställer...');
      try {
        var csrf = getCookie('csrf_token');
        var r = await fetch('/ui/admin/departments/' + state.departmentId + '/diet-overrides/reset', {
          method: 'POST',
          credentials: 'same-origin',
          headers: Object.assign({
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
          }, csrf ? { 'X-CSRF-Token': csrf } : {}),
          body: JSON.stringify({ diet_type_id: state.dietTypeId })
        });
        if(!r.ok){
          setStatus('Kunde inte återställa.');
          return;
        }
        setInputsToBase();
        setStatus('Återställd.');
      } catch(_) {
        setStatus('Fel vid återställning.');
      }
    }

    document.body.addEventListener('click', function(ev){
      var trigger = ev.target.closest('.js-open-diet-override');
      if(!trigger) return;
      ev.preventDefault();
      state.departmentId = trigger.getAttribute('data-department-id');
      state.dietTypeId = trigger.getAttribute('data-diet-type-id');
      state.dietName = trigger.getAttribute('data-diet-name') || '';
      if(nameEl) nameEl.textContent = state.dietName;
      setInputsToBase();
      setStatus('');
      openDialog(dlg);
      loadOverrides();
    });

    if(saveBtn) saveBtn.addEventListener('click', function(){ void saveOverrides(); });
    if(resetBtn) resetBtn.addEventListener('click', function(){ void resetOverrides(); });
    closeEls.forEach(function(el){
      el.addEventListener('click', function(){ closeDialog(dlg); });
    });
  });
})();
