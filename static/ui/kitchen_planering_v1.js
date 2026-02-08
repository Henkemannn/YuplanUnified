(function(){
  function qs(sel){ return document.querySelector(sel); }
  function qsa(sel){ return Array.prototype.slice.call(document.querySelectorAll(sel)); }

  // CSRF helpers: read from meta[name="csrf-token"] or cookie "csrf_token"
  function getCookie(name){
    try {
      var m = document.cookie.match(new RegExp('(^|; )' + name + '=([^;]*)'));
      return m ? decodeURIComponent(m[2]) : '';
    } catch(e){ return ''; }
  }
  function getCsrfToken(){
    var token = '';
    try {
      var meta = document.querySelector('meta[name="csrf-token"]');
      var metaTok = meta && meta.getAttribute('content');
      if(metaTok && String(metaTok).trim().length > 0){
        token = String(metaTok).trim();
      } else {
        console.warn('[csrf] missing meta token');
      }
    } catch(e){
      console.warn('[csrf] meta read error');
    }
    if(!token){
      var cookieTok = getCookie('csrf_token');
      if(cookieTok){ token = cookieTok; }
    }
    return token;
  }

  // In-memory UI-only state for normal-mode diet toggles
  var cannotEat = { 1: new Set(), 2: new Set() };
  // Alt group department IDs and per-department diet counts
  var altGroups = { alt1_dept_ids: [], alt2_dept_ids: [] };
  var dietCountsByDept = {};
   // Specialkost selection state
   var selectedSpecialDietIds = new Set();
   var specialSummary = { totals: [], per_department: [] };
   var specialById = {};
   var specialPerDept = [];

  function clamp(n, min, max){
    n = Number(n||0);
    if(isNaN(n)) n = 0;
    if(n < min) return min;
    if(n > max) return max;
    return n;
  }

  function parseSelectedDiets(){
    var ctx = qs('#kp-context');
    if(!ctx) return [];
    var raw = ctx.getAttribute('data-selected-diets') || '[]';
    try { return JSON.parse(raw); } catch(e){ return []; }
  }

   function parseSpecialSummary(){
     var ctx = qs('#kp-context');
     if(!ctx) return { totals: [], per_department: [] };
     var raw = ctx.getAttribute('data-special-summary') || '{}';
     try {
       var parsed = JSON.parse(raw);
       if(parsed && typeof parsed === 'object'){
         return parsed;
       }
     } catch(e){ /* ignore */ }
     return { totals: [], per_department: [] };
   }

  function getBaselines(){
    var a1El = qs('[data-baseline="alt1"]') || qs('#kp-base-alt1');
    var a2El = qs('[data-baseline="alt2"]') || qs('#kp-base-alt2');
    var totEl = qs('#kp-base-total');
    var baseAlt1 = parseInt((a1El && a1El.textContent) || '0', 10);
    var baseAlt2 = parseInt((a2El && a2El.textContent) || '0', 10);
    var baseTotal = parseInt((totEl && totEl.textContent) || '0', 10);
    if(isNaN(baseAlt1)) baseAlt1 = 0;
    if(isNaN(baseAlt2)) baseAlt2 = 0;
    if(isNaN(baseTotal)) baseTotal = 0;
    return { baseAlt1: baseAlt1, baseAlt2: baseAlt2, baseTotal: baseTotal };
  }

  function sumExcluded(alt){
    try {
      var ctx = qs('#kp-context');
      if(!ctx) return 0;
      var selected = parseSelectedDiets();
      var isSelected = function(id){ return selected.indexOf(String(id)) !== -1; };
      var deptIds = alt === 2 ? (altGroups.alt2_dept_ids || []) : (altGroups.alt1_dept_ids || []);
      var diets = Array.from((cannotEat[alt] || new Set()));
      var s = 0;
      for(var d=0; d<diets.length; d++){
        var dietId = String(diets[d]);
        if(isSelected(dietId)) continue; // adapted specials are excluded from normal
        for(var j=0; j<deptIds.length; j++){
          var deptId = String(deptIds[j]);
          var m = dietCountsByDept && dietCountsByDept[deptId];
          var c = m && m[dietId];
          var cnt = parseInt(c || '0', 10);
          if(!isNaN(cnt)) s += cnt;
        }
      }
      return s;
    } catch(e){ return 0; }
  }

  function renderAllTotals(){
    var ctx = qs('#kp-context');
    if(!ctx) return;
    var meal = ctx.getAttribute('data-meal');
    var modeParam = (new URLSearchParams(window.location.search).get('mode')||'').toLowerCase();
    var mode = modeParam || 'special';
    if(mode !== 'normal' || meal !== 'lunch') return; // only lunch normal mode has Alt 1/2
    var bases = getBaselines();
    var baseAlt1 = bases.baseAlt1, baseAlt2 = bases.baseAlt2, baseTotal = bases.baseTotal;
    var ex1 = sumExcluded(1);
    var ex2 = sumExcluded(2);
    var overflow = (ex1 > baseAlt1) || (ex2 > baseAlt2);
    var excluded1 = Math.min(baseAlt1, ex1);
    var excluded2 = Math.min(baseAlt2, ex2);
    var alt1 = clamp(baseAlt1 - excluded1, 0, baseTotal);
    var alt2 = clamp(baseAlt2 - excluded2, 0, baseTotal);
    var total = baseTotal; // keep consistent with table baseline
    var elA1 = qs('#kp-total-alt1');
    var elA2 = qs('#kp-total-alt2');
    var elSum = qs('#kp-total-sum');
    if(elA1) elA1.textContent = String(alt1);
    if(elA2) elA2.textContent = String(alt2);
    if(elSum) elSum.textContent = String(total);
    // Update bottom result table spans
    var resA1 = qs('[data-result-normal="alt1"]');
    var resA2 = qs('[data-result-normal="alt2"]');
    if(resA1) resA1.textContent = String(alt1);
    if(resA2) resA2.textContent = String(alt2);
    var warn = qs('#kp-exclusions-warning');
    if(warn){ warn.style.display = overflow ? 'block' : 'none'; }
  }

   function renderSpecialOverview(){
     var ctx = qs('#kp-context');
     if(!ctx) return;
     var totalEl = qs('#kp-special-total');
     var doneEl = qs('#kp-special-done');
     var remEl = qs('#kp-special-remaining');
     if(!totalEl || !doneEl || !remEl) return;
     var hasSelection = selectedSpecialDietIds.size > 0;
     if(!hasSelection){
       totalEl.textContent = String(ctx.getAttribute('data-special-total') || '0');
       doneEl.textContent = String(ctx.getAttribute('data-special-done') || '0');
       remEl.textContent = String(ctx.getAttribute('data-special-remaining') || '0');
       return;
     }
     var t = 0;
     var d = 0;
     selectedSpecialDietIds.forEach(function(id){
       var item = specialById[String(id)];
       if(item){
         t += item.total;
         d += item.done;
       }
     });
     var r = Math.max(t - d, 0);
     totalEl.textContent = String(t);
     doneEl.textContent = String(d);
     remEl.textContent = String(r);
   }

   function renderSpecialSelectedList(){
     var list = qs('#kp-special-selected-list');
     var empty = qs('#kp-special-selected-empty');
     var countEl = qs('#kp-special-selected-count');
     var totalEl = qs('#kp-special-selected-total');
     if(!list || !empty) return;
     list.innerHTML = '';
     var selected = Array.from(selectedSpecialDietIds);
     if(countEl) countEl.textContent = String(selected.length);
     var totalCount = 0;
     var groups = [];
     for(var i=0;i<specialPerDept.length;i++){
       var dep = specialPerDept[i];
       var items = [];
       for(var j=0;j<dep.items.length;j++){
         var row = dep.items[j];
         if(selectedSpecialDietIds.has(String(row.diet_type_id))){
           items.push(row);
           totalCount += row.count;
         }
       }
       if(items.length){
         groups.push({ name: dep.department_name, items: items });
       }
     }
     if(totalEl) totalEl.textContent = String(totalCount);
     if(groups.length === 0){
       empty.style.display = 'block';
       return;
     }
     empty.style.display = 'none';
     for(var g=0; g<groups.length; g++){
       var group = groups[g];
       var wrap = document.createElement('div');
       wrap.className = 'kp-special-group';
       var title = document.createElement('div');
       title.className = 'kp-special-group-title';
       title.textContent = group.name;
       wrap.appendChild(title);
       var grid = document.createElement('div');
       grid.className = 'kp-chip-grid';
       for(var k=0; k<group.items.length; k++){
         var item = group.items[k];
         var chip = document.createElement('span');
         chip.className = 'kp-chip kp-chip--mini is-active';
         chip.textContent = item.diet_type_name + ' ' + item.count;
         grid.appendChild(chip);
       }
       wrap.appendChild(grid);
       list.appendChild(wrap);
     }
   }

   function initSpecialChips(){
     var ctx = qs('#kp-context');
     if(!ctx) return;
     var chips = qsa('.js-special-chip');
     if(!chips.length) return;
     // Build special summary maps
     specialSummary = parseSpecialSummary();
     specialById = {};
     specialPerDept = [];
     try {
       var totals = specialSummary.totals || [];
       for(var i=0;i<totals.length;i++){
         var it = totals[i];
         var id = String(it.diet_type_id);
         specialById[id] = {
           total: parseInt(it.count || 0, 10) || 0,
           done: parseInt(it.done || 0, 10) || 0,
           name: String(it.diet_type_name || id)
         };
       }
       var per = specialSummary.per_department || [];
       for(var d=0; d<per.length; d++){
         var dep = per[d];
         var items = [];
         var depItems = dep.items || dep['items'] || [];
         for(var j=0; j<depItems.length; j++){
           var row = depItems[j];
           items.push({
             diet_type_id: String(row.diet_type_id),
             diet_type_name: String(row.diet_type_name || row.diet_type_id),
             count: parseInt(row.count || 0, 10) || 0,
             done: !!row.done
           });
         }
         specialPerDept.push({
           department_name: String(dep.department_name || ''),
           items: items
         });
       }
     } catch(e){ /* ignore */ }

     var initialSelected = parseSelectedDiets();
     selectedSpecialDietIds = new Set((initialSelected || []).map(String));
     chips.forEach(function(btn){
       var id = String(btn.getAttribute('data-diet-id') || '');
       var isActive = selectedSpecialDietIds.has(id);
       if(isActive){ btn.classList.add('is-active'); }
       btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
       btn.addEventListener('click', function(){
         if(selectedSpecialDietIds.has(id)){
           selectedSpecialDietIds.delete(id);
           btn.classList.remove('is-active');
           btn.setAttribute('aria-pressed', 'false');
         } else {
           selectedSpecialDietIds.add(id);
           btn.classList.add('is-active');
           btn.setAttribute('aria-pressed', 'true');
         }
         renderSpecialOverview();
         renderSpecialSelectedList();
       });
     });
     renderSpecialOverview();
     renderSpecialSelectedList();
   }

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
      initSpecialChips();
      return cur;
    } catch(e){ return undefined; }
  }
  function pick(obj, candidates){
    for(var i=0;i<candidates.length;i++){
      var val = getDeep(obj, candidates[i]);
      if(typeof val === 'string' && val.trim().length > 0){ return val; }
      if(val && typeof val === 'object'){
        var name = val.dish_name || val.name;
        if(typeof name === 'string' && name.trim().length > 0){ return name; }
      }
    }
    return undefined;
  }

  function pickWithSource(obj, candidates){
    for(var i=0;i<candidates.length;i++){
      var key = candidates[i];
      var val = getDeep(obj, key);
      if(typeof val === 'string' && val.trim().length > 0){ return { value: val, source: key }; }
      if(val && typeof val === 'object'){
        var name = val.dish_name || val.name;
        if(typeof name === 'string' && name.trim().length > 0){ return { value: name, source: key }; }
      }
    }
    return { value: undefined, source: undefined };
  }

  function normalizeSourceKey(key){
    if(!key) return key;
    var k = String(key);
    if(/^(Lunch|lunch)\.main$/.test(k)) return 'Lunch.main';
    if(/^(Lunch|lunch)\.alt1$/.test(k)) return 'Lunch.alt1';
    if(/^(Lunch|lunch)\.alt2$/.test(k)) return 'Lunch.alt2';
    if(/^(Lunch|lunch)\.dish_name$/.test(k)) return 'Lunch.dish_name';
    if(/^(Lunch|lunch)\.name$/.test(k)) return 'Lunch.name';
    if(/^(Dinner|dinner)\.main$/.test(k)) return 'Dinner.main';
    if(/^(Dinner|dinner)\.name$/.test(k)) return 'Dinner.name';
    if(/^(Dessert|dessert)\.main$/.test(k)) return 'Dessert.main';
    if(/^(Dessert|dessert)\.name$/.test(k)) return 'Dessert.name';
    return k;
  }

  function resolveDay(data, dayIndex){
    var dayNames = ['monday','tuesday','wednesday','thursday','friday','saturday','sunday'];
    var idx = dayIndex;
    if(idx >= 1 && idx <= 7){ idx = idx - 1; }
    var dayKey = dayNames[idx];
    var days = (data && data.menu && data.menu.days) || data.days;
    var objByKey = (data && data.menu && data.menu.days) || data.days || (data && data.menu) || data;
    var variants = [dayKey, dayKey.toLowerCase(), dayKey.toUpperCase(), dayKey.charAt(0).toUpperCase()+dayKey.slice(1)];
    if(objByKey && !Array.isArray(objByKey)){
      for(var i=0;i<variants.length;i++){
        if(objByKey[variants[i]]) return objByKey[variants[i]];
        var short = variants[i].slice(0,3);
        if(objByKey[short]) return objByKey[short];
      }
      if(objByKey['Mon'] && idx === 0) return objByKey['Mon'];
      if(objByKey['Tue'] && idx === 1) return objByKey['Tue'];
      if(objByKey['Wed'] && idx === 2) return objByKey['Wed'];
      if(objByKey['Thu'] && idx === 3) return objByKey['Thu'];
      if(objByKey['Fri'] && idx === 4) return objByKey['Fri'];
      if(objByKey['Sat'] && idx === 5) return objByKey['Sat'];
      if(objByKey['Sun'] && idx === 6) return objByKey['Sun'];
    }
    if(Array.isArray(days)){
      if(days[idx]) return days[idx];
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

  function setPlaneringTitle(value){
    var el = qs('#kp-planering-title');
    if(el){ el.textContent = value || '—'; }
  }

  function setInputValue(input, value, pristine){
    if(!input) return;
    input.value = value;
    if(pristine){
      input.classList.add('is-pristine');
    } else {
      input.classList.remove('is-pristine');
    }
  }

  function buildSuggestionText(mode, meal, dishes, fallback){
    // For normal lunch, prefer a neutral contextual suggestion (no Alt1|Alt2 combined)
    if(mode === 'normal' && meal === 'lunch'){
      return null; // caller will compute a neutral suggestion
    }
    if(meal === 'lunch') return dishes.alt1 || dishes.alt2 || fallback;
    if(meal === 'dinner') return dishes.dinner || fallback;
    return dishes.dessert || fallback;
  }

  function initMenuAndTitle(){
    var ctx = qs('#kp-context');
    if(!ctx) return;
    var qsParams = new URLSearchParams(window.location.search);
    var siteId = qsParams.get('site_id') || (ctx && ctx.getAttribute('data-site-id')) || '';
    var mode = (qsParams.get('mode') || 'special').toLowerCase();
    var year = qsParams.get('year') || '';
    var week = qsParams.get('week') || '';
    var dayIndex = parseInt(ctx.getAttribute('data-day-index'), 10);
    var meal = ctx.getAttribute('data-meal');
    if(isNaN(dayIndex) || meal == null) return;

    if(!siteId){
      console.warn('Missing site_id in planering URL');
      var fb = '—';
      var el1 = qs('#kp-lunch-alt1');
      var el2 = qs('#kp-lunch-alt2');
      var ed = qs('#kp-dinner-main');
      var es = qs('#kp-dessert-main');
      if(el1) el1.textContent = fb;
      if(el2) el2.textContent = fb;
      if(ed) ed.textContent = fb;
      if(es) es.textContent = fb;
      setPlaneringTitle(fb);
      setInputValue(qs('#whatToCook'), fb, true);
      return;
    }

    var url = '/menu/week?site_id=' + encodeURIComponent(siteId)
      + '&year=' + encodeURIComponent(year)
      + '&week=' + encodeURIComponent(week);
    // Using shared menu utils; no instrumentation

    fetch(url, {
      headers: { 'Accept': 'application/json' },
      credentials: 'same-origin'
    })
    .then(function(r){
      if(!r.ok){
        var errClone = r.clone();
        return errClone.text().then(function(t){
          console.warn('menu/week failed', r.status, r.headers.get('content-type'), (t || '').slice(0, 200));
          return null;
        });
      }
      var clone = r.clone();
      return r.json().catch(function(){
        return clone.text().then(function(t){
          console.warn('menu/week invalid json', r.status, r.headers.get('content-type'), (t || '').slice(0, 200));
          return null;
        });
      });
    })
    .then(function(data){
      var fallback = '—';
      // instrumentation removed
      if(!data){
        setPlaneringTitle(fallback);
        setInputValue(qs('#whatToCook'), fallback, true);
        return;
      }
      // Use shared helper to resolve titles
      var titles = (window.MenuUtils && typeof window.MenuUtils.pickTitles==='function')
        ? window.MenuUtils.pickTitles(data, dayIndex, meal)
        : { alt1Text: '', alt2Text: '', source: {} };
      var suggestionText = null;
      var alt1 = titles.alt1Text || '';
      var alt2 = titles.alt2Text || '';
      if(meal === 'lunch'){
        var el1 = qs('#kp-lunch-alt1');
        var el2 = qs('#kp-lunch-alt2');
        if(el1) el1.textContent = alt1 || fallback;
        if(el2) el2.textContent = alt2 || fallback;
        if(mode === 'normal'){
          var a1 = qs('.alt-dish-input[data-alt="1"]');
          var a2 = qs('.alt-dish-input[data-alt="2"]');
          if(a1) setInputValue(a1, alt1 || '', true);
          if(a2) setInputValue(a2, alt2 || '', true);
        }
      } else if(meal === 'dinner'){
        var ed = qs('#kp-dinner-main');
        if(ed) ed.textContent = alt1 || fallback;
      } else {
        var es = qs('#kp-dessert-main');
        if(es) es.textContent = alt1 || fallback;
      }
      // Compute neutral suggestion for normal lunch (e.g., "Lunch – Tor vecka 9")
      if(mode === 'normal' && meal === 'lunch'){
        var dayAbbr = ['Mån','Tis','Ons','Tor','Fre','Lör','Sön'];
        var mealLabel = 'Lunch';
        var di = dayIndex;
        suggestionText = mealLabel + ' – ' + (dayAbbr[di] || '') + ' vecka ' + (week || '');
      } else {
        suggestionText = buildSuggestionText(mode, meal, { alt1: alt1, alt2: alt2, dinner: null, dessert: null }, fallback);
      }
      setPlaneringTitle(suggestionText);
      var input = qs('#whatToCook');
      if(input){
        setInputValue(input, suggestionText, true);
        function onEdit(){
          var val = input.value.trim();
          if(val.length === 0){
            setInputValue(input, suggestionText, true);
            setPlaneringTitle(suggestionText);
            return;
          }
          input.classList.remove('is-pristine');
          setPlaneringTitle(input.value);
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
    if(btn && modal){ btn.addEventListener('click', function(){ modal.classList.add('is-open'); document.body.classList.add('kp-dept-summary-open'); }); }
    if(closeBtn && modal){ closeBtn.addEventListener('click', function(){ modal.classList.remove('is-open'); document.body.classList.remove('kp-dept-summary-open'); }); }
    if(modal){ modal.addEventListener('click', function(ev){ if(ev.target === modal){ modal.classList.remove('is-open'); document.body.classList.remove('kp-dept-summary-open'); } }); }
  }

  function init(){
    initModeRadios();
    initMenuAndTitle();
    initPrintButton();
    initDeptSummaryModal();
    // Parse CSP-safe data attributes for alt groups and per-department diet counts
    var ctxData = qs('#kp-context');
    if(ctxData){
      try {
        var ag = ctxData.getAttribute('data-alt-groups');
        if(ag){ altGroups = JSON.parse(ag); }
      } catch(e){ altGroups = { alt1_dept_ids: [], alt2_dept_ids: [] }; }
      try {
        var dc = ctxData.getAttribute('data-diet-counts-by-dept');
        if(dc){ dietCountsByDept = JSON.parse(dc); }
      } catch(e){ dietCountsByDept = {}; }
    }
    // Initialize cannotEat sets based on server-rendered state
    qsa('.diet-chip.active').forEach(function(btn){
      var alt = Number(btn.getAttribute('data-alt'));
      var dietId = btn.getAttribute('data-diet-id');
      if(!alt || !dietId) return;
      var set = cannotEat[alt] || (cannotEat[alt] = new Set());
      set.add(dietId);
    });
    // Initial totals
    renderAllTotals();
    // Event delegation for diet-chip toggling (normal mode UI only)
    document.addEventListener('click', function(e){
      var btn = e.target && e.target.closest && e.target.closest('.diet-chip');
      if(!btn) return;
      var alt = Number(btn.getAttribute('data-alt'));
      var dietId = btn.getAttribute('data-diet-id');
      if(!alt || !dietId) return;
      var set = cannotEat[alt] || (cannotEat[alt] = new Set());
      var wasActive = btn.classList.contains('active');
      // Optimistic UI toggle
      if(wasActive){
        btn.classList.remove('active');
        set.delete(dietId);
      } else {
        btn.classList.add('active');
        set.add(dietId);
      }
      // Recalc after optimistic change
      renderAllTotals();
      // Build payload from context
      var ctx = qs('#kp-context');
      if(!ctx){ return; }
      var qsParams = new URLSearchParams(window.location.search);
      var siteId = qsParams.get('site_id') || (ctx && ctx.getAttribute('data-site-id')) || '';
      var year = parseInt(qsParams.get('year') || ctx.getAttribute('data-year') || '0', 10);
      var week = parseInt(qsParams.get('week') || ctx.getAttribute('data-week') || '0', 10);
      var dayIndex = parseInt(ctx.getAttribute('data-day-index'), 10);
      var meal = ctx.getAttribute('data-meal');
      var payload = {
        site_id: siteId,
        year: year,
        week: week,
        day_index: dayIndex,
        meal: meal,
        alt: String(alt),
        diet_type_id: dietId
      };
      var csrf = getCsrfToken();
      var hdrs = { 'Content-Type': 'application/json' };
      // Always send CSRF headers; backend will validate value
      hdrs['X-CSRFToken'] = csrf;
      hdrs['X-CSRF-Token'] = csrf;
      fetch('/api/kitchen/planering/normal_exclusions/toggle', {
        method: 'POST',
        headers: hdrs,
        credentials: 'same-origin',
        body: JSON.stringify(payload)
      })
      .then(function(r){
        if(!r.ok){
          throw new Error('toggle_failed:' + r.status);
        }
        return r.json().catch(function(){ return { excluded: btn.classList.contains('active') }; });
      })
      .then(function(resp){
        var shouldActive = !!resp && !!resp.excluded;
        var isActive = btn.classList.contains('active');
        if(shouldActive !== isActive){
          if(shouldActive){
            btn.classList.add('active');
            set.add(dietId);
          } else {
            btn.classList.remove('active');
            set.delete(dietId);
          }
        }
        // Recalc in case server reconciled differently
        renderAllTotals();
      })
      .catch(function(){
        // Revert to previous state on error
        if(wasActive){
          btn.classList.add('active');
          set.add(dietId);
        } else {
          btn.classList.remove('active');
          set.delete(dietId);
        }
        renderAllTotals();
      });
    });
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
