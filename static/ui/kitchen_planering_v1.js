(function(){
  function qs(sel){ return document.querySelector(sel); }
  function qsa(sel){ return Array.prototype.slice.call(document.querySelectorAll(sel)); }

  // Mode change: radios without inline handlers
  function kpSetMode(mode){
    try {
      var url = new URL(window.location.href);
      url.searchParams.set('mode', mode);
      window.location.href = url.toString();
    } catch(e){}
  }

  function initModeRadios(){
    var radios = qsa('input[name="mode"]');
    if(!radios.length) return;
    radios.forEach(function(r){
      r.addEventListener('change', function(){ kpSetMode(r.value); });
    });
  }

  // Helper functions for menu mapping
  function getDeep(obj, path){
    try {
      var parts = path.split('.');
      var cur = obj;
      for(var i=0;i<parts.length;i++){
        if(cur == null) return undefined;
        cur = cur[parts[i]];
      }
      return cur;
    } catch(e){ return undefined; }
  }
  function pick(obj, candidates){
    for(var i=0;i<candidates.length;i++){
      var val = getDeep(obj, candidates[i]);
      if(typeof val === 'string' && val.trim().length > 0){ return val; }
    }
    return undefined;
  }

  function resolveDay(data, dayIndex){
    var dayNames = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
    var dayKey = dayNames[dayIndex];
    var days = (data && data.menu && data.menu.days) || data.days;
    var objByKey = (data && data.menu) || data;
    var variants = [dayKey, dayKey.toLowerCase(), dayKey.toUpperCase(), dayKey.charAt(0).toUpperCase()+dayKey.slice(1)];
    if(objByKey && !Array.isArray(objByKey)){
      for(var i=0;i<variants.length;i++){
        if(objByKey[variants[i]]) return objByKey[variants[i]];
        var short = variants[i].slice(0,3);
        if(objByKey[short]) return objByKey[short];
      }
    }
    if(Array.isArray(days)){
      if(days[dayIndex]) return days[dayIndex];
      for(var j=0;j<days.length;j++){
        var d = days[j];
        var name = d && (d.name || d.day || d.Day || d.title);
        if(typeof name === 'string'){
          var n = name.toLowerCase();
          if(n.indexOf(dayKey.slice(0,3)) === 0) return d;
        }
      }
    }
    return null;
  }

  function initMenuAndTitle(){
    var ctx = qs('#kp-context');
    if(!ctx) return;
    var year = ctx.getAttribute('data-year');
    var week = ctx.getAttribute('data-week');
    var dayIndex = parseInt(ctx.getAttribute('data-day-index'), 10);
    var meal = ctx.getAttribute('data-meal');
    if(isNaN(dayIndex) || meal == null) return;

    fetch('/menu/week?year=' + encodeURIComponent(year) + '&week=' + encodeURIComponent(week), {
      headers: { 'Accept': 'application/json' }
    })
    .then(function(r){ return r.json(); })
    .then(function(data){
      var dayEntry = resolveDay(data, dayIndex);
      if(!dayEntry) return;
      var fallback = 'Ingen maträtt hittades för valt tillfälle';
      var suggestion = null;
      if(meal === 'lunch'){
        var alt1 = pick(dayEntry, ['Lunch.Alt1','lunch.alt1','Lunch.alt1','alt1','Alt1','Lunch.Main']);
        var alt2 = pick(dayEntry, ['Lunch.Alt2','lunch.alt2','Lunch.alt2','alt2','Alt2']);
        var el1 = qs('#kp-lunch-alt1');
        var el2 = qs('#kp-lunch-alt2');
        if(el1) el1.textContent = alt1 || fallback;
        if(el2) el2.textContent = alt2 || fallback;
        suggestion = alt1 || alt2 || fallback;
      } else if(meal === 'dinner'){
        var dinner = pick(dayEntry, ['Dinner.Main','Dinner.Alt1','dinner.main','dinner.alt1','Dinner','dinner','Main','Alt1']);
        var ed = qs('#kp-dinner-main');
        if(ed) ed.textContent = dinner || fallback;
        suggestion = dinner || fallback;
      } else {
        var dessert = pick(dayEntry, ['Dessert.Main','Dessert','dessert.main','dessert','Main']);
        var es = qs('#kp-dessert-main');
        if(es) es.textContent = dessert || fallback;
        suggestion = dessert || fallback;
      }
      var titleEl = qs('#kp-special-title');
      if(titleEl && suggestion){ titleEl.textContent = suggestion; }
      var input = qs('#kp-what-to-cook');
      if(input && suggestion){
        input.value = suggestion;
        input.classList.add('is-pristine');
        function onEdit(){
          input.classList.remove('is-pristine');
          if(titleEl){ titleEl.textContent = input.value || suggestion; }
        }
        input.addEventListener('input', onEdit);
        input.addEventListener('change', onEdit);
      }
    })
    .catch(function(){ /* ignore */ });
  }

  function initPrintButton(){
    var btn = qs('.js-print');
    if(btn){
      btn.addEventListener('click', function(){ window.print(); });
    }
  }

  function initDeptSummaryModal(){
    var btn = qs('.js-open-dept-summary');
    var modal = qs('#dept-summary-modal');
    var closeBtn = qs('#close-dept-summary');
    if(btn && modal){ btn.addEventListener('click', function(){ modal.style.display = 'flex'; }); }
    if(closeBtn && modal){ closeBtn.addEventListener('click', function(){ modal.style.display = 'none'; }); }
    if(modal){ modal.addEventListener('click', function(ev){ if(ev.target === modal){ modal.style.display = 'none'; } }); }
  }

  function init(){
    initModeRadios();
    initMenuAndTitle();
    initPrintButton();
    initDeptSummaryModal();
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
