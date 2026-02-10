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
  var lastPrintMode = 'special';
  var lastSpecialWorklist = [];

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

  function getStorageKey(){
    var ctx = qs('#kp-context');
    if(!ctx) return null;
    var qsParams = new URLSearchParams(window.location.search);
    var mode = (qsParams.get('mode') || 'special').toLowerCase();
    var siteId = qsParams.get('site_id') || ctx.getAttribute('data-site-id') || '';
    var year = qsParams.get('year') || ctx.getAttribute('data-year') || '';
    var week = qsParams.get('week') || ctx.getAttribute('data-week') || '';
    var dayIndex = ctx.getAttribute('data-day-index') || '';
    var meal = ctx.getAttribute('data-meal') || '';
    if(!siteId || !year || !week || !meal){ return null; }
    return 'kp:planering:' + siteId + ':' + year + ':' + week + ':' + dayIndex + ':' + meal + ':' + mode;
  }

  function loadPlaneringState(){
    try {
      var key = getStorageKey();
      if(!key || !window.localStorage) return null;
      var raw = window.localStorage.getItem(key);
      if(!raw) return null;
      var parsed = JSON.parse(raw);
      if(parsed && typeof parsed === 'object'){ return parsed; }
    } catch(e){ /* ignore */ }
    return null;
  }

  function savePlaneringState(){
    try {
      var key = getStorageKey();
      if(!key || !window.localStorage) return;
      var state = {
        selected_diets: Array.from(selectedSpecialDietIds),
        inputs: {
          alt1: getTextValue('#kp-what-alt1') || '',
          alt2: getTextValue('#kp-what-alt2') || '',
          dinner: getTextValue('#kp-what-dinner') || '',
          dessert: getTextValue('#kp-what-dessert') || '',
          normal_alt1: getTextValue('.alt-dish-input[data-alt="1"]') || '',
          normal_alt2: getTextValue('.alt-dish-input[data-alt="2"]') || '',
          normal_main: getTextValue('.alt-dish-input') || ''
        },
        bulk_marked: !!(qs('.js-bulk-mark') && qs('.js-bulk-mark').dataset && qs('.js-bulk-mark').dataset.success === '1')
      };
      window.localStorage.setItem(key, JSON.stringify(state));
    } catch(e){ /* ignore */ }
  }

  function applyStoredInputs(state){
    if(!state || !state.inputs) return;
    var inp = state.inputs;
    var a1 = qs('#kp-what-alt1');
    var a2 = qs('#kp-what-alt2');
    var d1 = qs('#kp-what-dinner');
    var ds = qs('#kp-what-dessert');
    if(a1 && inp.alt1){ setInputValue(a1, inp.alt1, false); }
    if(a2 && inp.alt2){ setInputValue(a2, inp.alt2, false); }
    if(d1 && inp.dinner){ setInputValue(d1, inp.dinner, false); }
    if(ds && inp.dessert){ setInputValue(ds, inp.dessert, false); }
    var n1 = qs('.alt-dish-input[data-alt="1"]');
    var n2 = qs('.alt-dish-input[data-alt="2"]');
    if(n1 && inp.normal_alt1){ setInputValue(n1, inp.normal_alt1, false); }
    if(n2 && inp.normal_alt2){ setInputValue(n2, inp.normal_alt2, false); }
    var nm = qs('.alt-dish-input');
    if(nm && inp.normal_main){ setInputValue(nm, inp.normal_main, false); }
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

  function renderSpecialSelectedList(){
    var list = qs('#kp-special-worklist');
    var empty = qs('#kp-special-selected-empty');
    if(!list || !empty) return;
    list.innerHTML = '';
    var selected = Array.from(selectedSpecialDietIds);
    if(selected.length === 0){
      empty.style.display = 'block';
      updateBulkButtonState();
      renderDeptSummary();
      return;
    }
    empty.style.display = 'none';
    var byDiet = {};
    var totalsByDiet = {};
    for(var i=0;i<specialPerDept.length;i++){
      var dep = specialPerDept[i];
      for(var j=0;j<dep.items.length;j++){
        var row = dep.items[j];
        var dietId = String(row.diet_type_id);
        if(selectedSpecialDietIds.has(dietId) && specialById[dietId]){
          if(!byDiet[dietId]){ byDiet[dietId] = []; }
          byDiet[dietId].push({
            department_id: dep.department_id,
            department_name: dep.department_name,
            count: row.count
          });
          totalsByDiet[dietId] = (totalsByDiet[dietId] || 0) + row.count;
        }
      }
    }
    var alt2Set = new Set((altGroups && altGroups.alt2_dept_ids) || []);
    var dietIds = Object.keys(byDiet).sort(function(a, b){
      var ta = totalsByDiet[a] || 0;
      var tb = totalsByDiet[b] || 0;
      if(tb !== ta){ return tb - ta; }
      var na = (specialById[a] && specialById[a].name) || a;
      var nb = (specialById[b] && specialById[b].name) || b;
      return String(na).localeCompare(String(nb));
    });
    lastSpecialWorklist = dietIds.map(function(id){
      return {
        diet_type_id: id,
        diet_type_name: (specialById[id] && specialById[id].name) || id,
        total: totalsByDiet[id] || 0,
        rows: (byDiet[id] || []).map(function(r){
          return {
            department_id: r.department_id,
            department_name: r.department_name,
            count: r.count
          };
        })
      };
    });
    for(var d=0; d<dietIds.length; d++){
      var id = dietIds[d];
      var group = document.createElement('div');
      group.className = 'kp-worklist-group';
      group.setAttribute('data-diet-id', id);
      var title = document.createElement('div');
      title.className = 'kp-worklist-title';
      var name = (specialById[id] && specialById[id].name) || id;
      title.textContent = name + ' ';
      var totalSpan = document.createElement('span');
      totalSpan.className = 'kp-worklist-total';
      totalSpan.textContent = String(totalsByDiet[id] || 0);
      title.appendChild(totalSpan);
      group.appendChild(title);
      var rowsWrap = document.createElement('div');
      rowsWrap.className = 'kp-worklist-rows';
      var rows = byDiet[id] || [];
      for(var r=0; r<rows.length; r++){
        var row = rows[r];
        var rowEl = document.createElement('div');
        var isAlt2 = (qs('#kp-context') && qs('#kp-context').getAttribute('data-meal') === 'lunch' && alt2Set.has(String(row.department_id)));
        rowEl.className = 'kp-worklist-row' + (isAlt2 ? ' is-alt2-row' : '');
        var nameEl = document.createElement('span');
        nameEl.className = 'kp-row-name';
        nameEl.textContent = row.department_name;
        var countEl = document.createElement('span');
        countEl.className = 'kp-row-count';
        countEl.textContent = String(row.count);
        rowEl.appendChild(nameEl);
        rowEl.appendChild(countEl);
        if(isAlt2){
          var altBadge = document.createElement('span');
          altBadge.className = 'kp-row-alt2';
          altBadge.textContent = 'Alt 2';
          rowEl.appendChild(altBadge);
        }
        rowsWrap.appendChild(rowEl);
      }
      group.appendChild(rowsWrap);
      list.appendChild(group);
    }
    updateBulkButtonState();
    renderDeptSummary();
    renderPrintContainer();
    savePlaneringState();
  }

  function updateBulkButtonState(){
    var btn = qs('.js-bulk-mark');
    if(!btn) return;
    if(btn.dataset && btn.dataset.defaultLabel && btn.dataset.success === '1'){
      btn.classList.remove('is-success');
      btn.textContent = btn.dataset.defaultLabel;
      btn.dataset.success = '0';
    }
    btn.disabled = (selectedSpecialDietIds.size === 0);
  }

  function renderDeptSummary(){
    var body = qs('#dept-summary-body');
    if(!body) return;
    body.innerHTML = '';
    var selected = Array.from(selectedSpecialDietIds);
    if(selected.length === 0){
      var empty = document.createElement('div');
      empty.className = 'empty-text';
      empty.textContent = 'Välj specialkoster för att se sammanfattning.';
      body.appendChild(empty);
      return;
    }
    var byDept = [];
    for(var i=0;i<specialPerDept.length;i++){
      var dep = specialPerDept[i];
      var items = [];
      for(var j=0;j<dep.items.length;j++){
        var row = dep.items[j];
        var dietId = String(row.diet_type_id);
        if(selectedSpecialDietIds.has(dietId) && specialById[dietId]){
          items.push({
            diet_type_id: dietId,
            diet_type_name: specialById[dietId].name,
            count: row.count
          });
        }
      }
      if(items.length > 0){
        byDept.push({
          department_id: dep.department_id,
          department_name: dep.department_name,
          items: items
        });
      }
    }
    if(byDept.length === 0){
      var empty2 = document.createElement('div');
      empty2.className = 'empty-text';
      empty2.textContent = 'Inga valda specialkoster matchar vald dag.';
      body.appendChild(empty2);
      return;
    }
    var alt2Set = new Set((altGroups && altGroups.alt2_dept_ids) || []);
    for(var t=0; t<byDept.length; t++){
      var it = byDept[t];
      var block = document.createElement('div');
      block.className = 'kp-dept-summary';
      var head = document.createElement('div');
      var isAlt2 = (qs('#kp-context') && qs('#kp-context').getAttribute('data-meal') === 'lunch' && alt2Set.has(String(it.department_id)));
      head.className = 'kp-worklist-row' + (isAlt2 ? ' is-alt2-row' : '');
      var nameEl = document.createElement('span');
      nameEl.className = 'kp-row-name';
      nameEl.textContent = it.department_name;
      head.appendChild(nameEl);
      if(isAlt2){
        var altBadge = document.createElement('span');
        altBadge.className = 'kp-row-alt2';
        altBadge.textContent = 'Alt 2';
        head.appendChild(altBadge);
      }
      block.appendChild(head);
      var list = document.createElement('div');
      list.className = 'kp-dept-diets';
      for(var k=0; k<it.items.length; k++){
        var row = it.items[k];
        var dietEl = document.createElement('div');
        dietEl.className = 'kp-dept-diet';
        dietEl.textContent = row.diet_type_name + ' (' + String(row.count) + ')';
        list.appendChild(dietEl);
      }
      block.appendChild(list);
      body.appendChild(block);
    }
  }

  function parseNormalkostRows(){
    var ctx = qs('#kp-context');
    if(!ctx) return [];
    var raw = ctx.getAttribute('data-normalkost-rows') || '[]';
    try {
      var parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : [];
    } catch(e){
      return [];
    }
  }

  function getTextValue(sel){
    var el = qs(sel);
    if(!el) return '';
    if(typeof el.value === 'string'){ return el.value.trim(); }
    return String(el.textContent || '').trim();
  }

  function getPrintDishNames(meal){
    var alt1 = '';
    var alt2 = '';
    if(meal === 'lunch'){
      alt1 = getTextValue('#kp-what-alt1') || getTextValue('.alt-dish-input[data-alt="1"]') || getTextValue('#kp-lunch-alt1');
      alt2 = getTextValue('#kp-what-alt2') || getTextValue('.alt-dish-input[data-alt="2"]') || getTextValue('#kp-lunch-alt2');
    } else if(meal === 'dinner'){
      alt1 = getTextValue('#kp-what-dinner') || getTextValue('#kp-dinner-main') || getTextValue('.alt-dish-input');
    } else {
      alt1 = getTextValue('#kp-what-dessert') || getTextValue('#kp-dessert-main') || getTextValue('.alt-dish-input');
    }
    return { alt1: alt1, alt2: alt2 };
  }

  function buildPrintRow(rowClass, name, count, altLabel){
    var rowEl = document.createElement('div');
    rowEl.className = 'kp-print-row ' + rowClass;
    var badge = altLabel
      ? '<span class="kp-altpill">' + altLabel + '</span>'
      : '<span class="kp-altpill-slot" aria-hidden="true"></span>';
    rowEl.innerHTML = '<span class="kp-dept-name">' + name + '</span>' + badge + '<span class="count">' + count + '</span>';
    return rowEl;
  }


  function buildPrintColumn(title, dishName, rows, total, isAlt2){
    var col = document.createElement('div');
    col.className = 'kp-print-col' + (isAlt2 ? ' nk-alt2-card' : '');
    var head = document.createElement('div');
    head.className = 'kp-print-col-title';
    head.textContent = title + ' — Totalt ' + total;
    col.appendChild(head);
    var dish = document.createElement('div');
    dish.className = 'kp-print-dish';
    if(isAlt2 && (!dishName || !String(dishName).trim().length)){
      dish.textContent = 'Alt 2: Ej planerad';
    } else {
      dish.textContent = dishName || '—';
    }
    col.appendChild(dish);
    var list = document.createElement('div');
    list.className = 'kp-print-list';
    if(rows.length === 0){
      list.appendChild(buildPrintRow('nk-row kp-zebra', 'Inga avdelningar', 0, null));
    } else {
      for(var i=0;i<rows.length;i++){
        var r = rows[i];
        list.appendChild(buildPrintRow('nk-row kp-zebra', r.name, r.count, null));
      }
    }
    col.appendChild(list);
    return col;
  }

  function buildSpecialWorklistFromSummary(){
    var byDiet = {};
    for(var p=0; p<specialPerDept.length; p++){
      var dep = specialPerDept[p];
      for(var j=0; j<dep.items.length; j++){
        var row = dep.items[j];
        var dietId = String(row.diet_type_id);
        if(!specialById[dietId]){ continue; }
        if(!byDiet[dietId]){
          byDiet[dietId] = {
            diet_type_id: dietId,
            diet_type_name: specialById[dietId].name,
            total: 0,
            rows: []
          };
        }
        byDiet[dietId].total += row.count;
        byDiet[dietId].rows.push({
          department_id: dep.department_id,
          department_name: dep.department_name,
          count: row.count
        });
      }
    }
    var list = Object.keys(byDiet).map(function(id){ return byDiet[id]; });
    list.sort(function(a, b){
      if(b.total !== a.total){ return b.total - a.total; }
      return String(a.diet_type_name).localeCompare(String(b.diet_type_name));
    });
    return list;
  }

  function renderPrintContainer(){
    var ctx = qs('#kp-context');
    var printEl = qs('#yp-print-root');
    if(!ctx || !printEl) return;
    var bodyMode = (document.body && document.body.dataset && document.body.dataset.printMode) || 'special';
    var week = ctx.getAttribute('data-week') || '';
    var dayLabel = ctx.getAttribute('data-day-label') || '';
    var mealLabel = ctx.getAttribute('data-meal-label') || '';
    var meal = ctx.getAttribute('data-meal') || '';
    var dishNames = getPrintDishNames(meal);
    var alt1Name = dishNames.alt1;
    var alt2Name = dishNames.alt2;
    var normRows = parseNormalkostRows();
    var alt2Set = new Set((altGroups && altGroups.alt2_dept_ids) || []);
    var worklist = (lastSpecialWorklist && lastSpecialWorklist.length > 0) ? lastSpecialWorklist : buildSpecialWorklistFromSummary();

    var alt1Rows = [];
    var alt2Rows = [];
    var alt1Total = 0;
    var alt2Total = 0;
    for(var i=0;i<normRows.length;i++){
      var row = normRows[i];
      var name = row.department_name || row.department_id || '';
      var depId = row.department_id || '';
      if(meal === 'lunch'){
        var c1 = parseInt(row.alt1 || 0, 10) || 0;
        var c2 = parseInt(row.alt2 || 0, 10) || 0;
        if(alt2Set.has(String(depId))){
          alt2Rows.push({ name: name, count: c2, department_id: depId });
          alt2Total += c2;
        } else {
          alt1Rows.push({ name: name, count: c1, department_id: depId });
          alt1Total += c1;
        }
      } else {
        var ct = parseInt(row.total || 0, 10) || 0;
        alt1Rows.push({ name: name, count: ct, department_id: depId });
        alt1Total += ct;
      }
    }

    var hasAlt2Rows = false;
    if(meal === 'lunch' && alt2Rows.length > 0){
      hasAlt2Rows = true;
    }
    if(meal === 'lunch' && worklist.length > 0){
      for(var wl=0; wl<worklist.length; wl++){
        var wrows = worklist[wl].rows || [];
        for(var wr=0; wr<wrows.length; wr++){
          if(alt2Set.has(String(wrows[wr].department_id))){
            hasAlt2Rows = true;
            break;
          }
        }
        if(hasAlt2Rows){ break; }
      }
    }

    printEl.innerHTML = '';

    if(bodyMode === 'modal'){
      var modalWrap = document.createElement('div');
      modalWrap.className = 'kp-print-sheet';
      var modalHeader = document.createElement('div');
      modalHeader.className = 'kp-print-header';
      var modalChips = '<span class="kp-print-chip">Vecka ' + week + '</span>'
        + '<span class="kp-print-chip">' + dayLabel + '</span>'
        + '<span class="kp-print-chip">' + mealLabel + '</span>';
      modalHeader.innerHTML = '<div class="kp-print-title">Tillagningslista</div>'
        + '<div class="kp-print-chip-row">' + modalChips + '</div>';
      modalWrap.appendChild(modalHeader);
      var modalTitle = document.createElement('div');
      modalTitle.className = 'kp-print-special-title';
      modalTitle.textContent = 'Sammanfattning per boende';
      modalWrap.appendChild(modalTitle);
      var modalBody = document.createElement('div');
      modalBody.className = 'kp-print-list';
      var rows = [];
      for(var p=0; p<specialPerDept.length; p++){
        var dep = specialPerDept[p];
        var sum = 0;
        for(var j=0; j<dep.items.length; j++){
          var row = dep.items[j];
          if(selectedSpecialDietIds.has(String(row.diet_type_id))){
            sum += row.count;
          }
        }
        if(sum > 0){
          rows.push({ department_id: dep.department_id, department_name: dep.department_name, count: sum });
        }
      }
      if(rows.length === 0){
        modalBody.appendChild(buildPrintRow('sk-row', 'Inga avdelningar', 0, 'Alt1'));
      } else {
        for(var r=0; r<rows.length; r++){
          var item = rows[r];
          var isAlt2Row = (meal === 'lunch' && alt2Set.has(String(item.department_id)));
          modalBody.appendChild(buildPrintRow('sk-row', item.department_name, item.count, isAlt2Row ? 'Alt2' : 'Alt1'));
        }
      }
      modalWrap.appendChild(modalBody);
      printEl.appendChild(modalWrap);
      return;
    }

    var sheet = document.createElement('div');
    sheet.className = 'kp-print-sheet';
    var header = document.createElement('div');
    header.className = 'kp-print-header';
    var chips = '<span class="kp-print-chip">Vecka ' + week + '</span>'
      + '<span class="kp-print-chip">' + dayLabel + '</span>'
      + '<span class="kp-print-chip">' + mealLabel + '</span>';
    header.innerHTML = '<div class="kp-print-title">Tillagningslista</div>'
      + '<div class="kp-print-chip-row">' + chips + '</div>';
    sheet.appendChild(header);

    if(bodyMode === 'full' || bodyMode === 'normal'){
      var normHead = document.createElement('div');
      normHead.className = 'kp-print-section-title';
      normHead.textContent = 'Normalkost';
      sheet.appendChild(normHead);
      var grid = document.createElement('div');
      grid.className = 'kp-print-grid';
      grid.appendChild(buildPrintColumn('Alt 1', alt1Name, alt1Rows, alt1Total, false));
      var alt2Dish = alt2Name || 'Ej planerad';
      var alt2TotalOut = alt2Name ? alt2Total : 0;
      grid.appendChild(buildPrintColumn('Alt 2', alt2Dish, alt2Rows, alt2TotalOut, true));
      sheet.appendChild(grid);
    }

    if(bodyMode === 'full' || bodyMode === 'special'){
      var special = document.createElement('div');
      special.className = 'kp-print-special';
      var specialHead = document.createElement('div');
      specialHead.className = 'kp-print-section-title';
      specialHead.textContent = 'Specialkost';
      special.appendChild(specialHead);

      if(worklist.length === 0){
        var empty = document.createElement('div');
        empty.className = 'kp-print-empty';
        empty.textContent = 'Ingen specialkost vald.';
        special.appendChild(empty);
      } else {
        var planRow2 = document.createElement('div');
        planRow2.className = 'kp-print-plan';
        var planList = document.createElement('div');
        planList.className = 'kp-print-plan-list';
        var planAlt1b = document.createElement('div');
        planAlt1b.className = 'kp-print-plan-pill';
        planAlt1b.textContent = 'Alt1: ' + (alt1Name || '—');
        planList.appendChild(planAlt1b);
        if(meal === 'lunch'){
          var planAlt2b = document.createElement('div');
          planAlt2b.className = 'kp-print-plan-pill';
          planAlt2b.textContent = 'Alt2: ' + (alt2Name || 'Ej planerad');
          planList.appendChild(planAlt2b);
        }
        planRow2.appendChild(planList);
        special.appendChild(planRow2);

        var specialListTitle = document.createElement('div');
        specialListTitle.className = 'kp-print-special-title';
        specialListTitle.textContent = 'Vald specialkost';
        special.appendChild(specialListTitle);
        for(var d=0; d<worklist.length; d++){
          var block = worklist[d];
          var group = document.createElement('div');
          group.className = 'kp-print-special-group sk-card';
          var title = document.createElement('div');
          title.className = 'kp-print-special-name';
          title.textContent = block.diet_type_name + ' — Totalt ' + (block.total || 0);
          group.appendChild(title);
          var list = document.createElement('div');
          list.className = 'kp-print-list';
          var rows = block.rows || [];
          if(rows.length === 0){
            list.appendChild(buildPrintRow('sk-row kp-zebra', 'Inga avdelningar', 0, 'Alt1'));
          } else {
            for(var r=0; r<rows.length; r++){
              var item = rows[r];
              var isAlt2 = (meal === 'lunch' && alt2Set.has(String(item.department_id)));
              list.appendChild(buildPrintRow('sk-row kp-zebra', item.department_name, item.count, isAlt2 ? 'Alt2' : 'Alt1'));
            }
          }
          group.appendChild(list);
          special.appendChild(group);
        }
      }
      sheet.appendChild(special);
    }

    printEl.appendChild(sheet);
  }

  function triggerPrintWithGuard(){
    renderPrintContainer();
    var printEl = qs('#yp-print-root');
    if(!printEl || !printEl.firstElementChild){
      renderPrintContainer();
      if(window && window.requestAnimationFrame){
        window.requestAnimationFrame(function(){ window.print(); });
        return;
      }
    }
    window.print();
  }

  function setPrintMode(mode){
    if(document.body && document.body.dataset){
      document.body.dataset.printMode = mode;
    }
    lastPrintMode = mode;
  }

  function updateModalPrintHeader(){
    var hdr = qs('#kp-modal-print-header');
    var ctx = qs('#kp-context');
    if(!hdr || !ctx) return;
    var week = ctx.getAttribute('data-week') || '';
    var dayLabel = ctx.getAttribute('data-day-label') || '';
    var mealLabel = ctx.getAttribute('data-meal-label') || '';
    hdr.innerHTML = '<div class="kp-print-title">Tillagningslista</div>'
      + '<div class="kp-print-chip-row">'
      + '<span class="kp-print-chip">Vecka ' + week + '</span>'
      + '<span class="kp-print-chip">' + dayLabel + '</span>'
      + '<span class="kp-print-chip">' + mealLabel + '</span>'
      + '</div>';
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
        var nm = String(it.diet_type_name || '').trim();
        if(!nm || /^[0-9]+$/.test(nm)){
          continue;
        }
        specialById[id] = {
          total: parseInt(it.count || 0, 10) || 0,
          done: parseInt(it.done || 0, 10) || 0,
          name: nm
        };
      }
      var per = specialSummary.per_department || [];
      for(var d=0; d<per.length; d++){
        var dep = per[d];
        var items = [];
        var depItems = dep.items || dep['items'] || [];
        for(var j=0; j<depItems.length; j++){
          var row = depItems[j];
          var dietId = String(row.diet_type_id);
          var dietName = String(row.diet_type_name || '').trim();
          if(!dietName || /^[0-9]+$/.test(dietName) || !specialById[dietId]){
            continue;
          }
          items.push({
            diet_type_id: dietId,
            diet_type_name: dietName,
            count: parseInt(row.count || 0, 10) || 0,
            done: !!row.done
          });
        }
        specialPerDept.push({
          department_id: String(dep.department_id || ''),
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
      if(isActive){ btn.classList.add('active'); }
      btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      btn.addEventListener('click', function(){
        if(selectedSpecialDietIds.has(id)){
          selectedSpecialDietIds.delete(id);
          btn.classList.remove('active');
          btn.setAttribute('aria-pressed', 'false');
        } else {
          selectedSpecialDietIds.add(id);
          btn.classList.add('active');
          btn.setAttribute('aria-pressed', 'true');
        }
        renderSpecialSelectedList();
      });
    });
    renderSpecialSelectedList();
  }

  function showToast(message){
    var toast = qs('#kp-toast');
    if(!toast) return;
    toast.textContent = message;
    toast.classList.add('is-visible');
    window.setTimeout(function(){ toast.classList.remove('is-visible'); }, 3000);
  }

  function initBulkMarkButtons(){
    var markBtn = qs('.js-bulk-mark');
    var clearBtn = qs('.js-bulk-clear');
    if(!markBtn && !clearBtn) return;
    if(markBtn && (!markBtn.dataset || !markBtn.dataset.defaultLabel)){
      markBtn.dataset.defaultLabel = markBtn.textContent || 'Markera som gjorda i veckolistan';
      markBtn.dataset.success = '0';
    }
    function runBulk(url, successMsg, errorMsg){
      var ctx = qs('#kp-context');
      if(!ctx) return;
      var qsParams = new URLSearchParams(window.location.search);
      var payload = {
        site_id: qsParams.get('site_id') || ctx.getAttribute('data-site-id') || '',
        year: parseInt(qsParams.get('year') || ctx.getAttribute('data-year') || '0', 10),
        week: parseInt(qsParams.get('week') || ctx.getAttribute('data-week') || '0', 10),
        day_index: parseInt(ctx.getAttribute('data-day-index') || '0', 10),
        meal: ctx.getAttribute('data-meal')
      };
      if(selectedSpecialDietIds.size > 0){
        var selected = Array.from(selectedSpecialDietIds);
        payload.selected_diet_type_ids = selected;
        payload.diet_type_ids = selected;
      }
      var csrf = getCsrfToken();
      var hdrs = { 'Content-Type': 'application/json' };
      hdrs['X-CSRF-Token'] = csrf;
      fetch(url, {
        method: 'POST',
        headers: hdrs,
        credentials: 'same-origin',
        body: JSON.stringify(payload)
      })
      .then(function(r){
        if(!r.ok){ throw new Error('bulk_failed:' + r.status); }
        return r.json();
      })
      .then(function(){
        showToast(successMsg);
        if(markBtn && url.indexOf('/mark_produced_special') !== -1){
          markBtn.classList.add('is-success');
          markBtn.textContent = 'Markerat ✅';
          markBtn.dataset.success = '1';
          markBtn.disabled = true;
          savePlaneringState();
        }
      })
      .catch(function(){
        showToast(errorMsg);
      });
    }
    if(markBtn){
      markBtn.addEventListener('click', function(){
        runBulk('/api/planering/mark_produced_special', 'Markerat i veckolistan ✅', 'Kunde inte markera i veckolistan');
      });
    }
    if(clearBtn){
      clearBtn.addEventListener('click', function(){
        runBulk('/api/planering/clear_produced_special', 'Rensat i veckovyn ✅', 'Kunde inte rensa i veckovyn');
      });
    }
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
        if(mode === 'special'){
          var s1 = qs('#kp-what-alt1');
          var s2 = qs('#kp-what-alt2');
          if(s1) setInputValue(s1, alt1 || '', true);
          if(s2) setInputValue(s2, alt2 || '', true);
        }
      } else if(meal === 'dinner'){
        var ed = qs('#kp-dinner-main');
        if(ed) ed.textContent = alt1 || fallback;
        if(mode === 'special'){
          var sd = qs('#kp-what-dinner');
          if(sd) setInputValue(sd, alt1 || '', true);
        }
      } else {
        var es = qs('#kp-dessert-main');
        if(es) es.textContent = alt1 || fallback;
        if(mode === 'special'){
          var ds = qs('#kp-what-dessert');
          if(ds) setInputValue(ds, alt1 || '', true);
        }
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
    })
    .catch(function(){ /* ignore */ });
  }

  function initPrintButton(){
    var btn = qs('.js-print');
    if(btn){
      btn.addEventListener('click', function(){
        var qsParams = new URLSearchParams(window.location.search);
        var mode = (qsParams.get('mode') || 'special').toLowerCase();
        if(mode === 'normal'){
          setPrintMode('normal');
        } else {
          setPrintMode('special');
        }
        triggerPrintWithGuard();
      });
    }
  }

  function initDeptSummaryModal(){
    var btn = qs('.js-open-dept-summary');
    var modal = qs('#dept-summary-modal');
    var closeBtn = qs('#close-dept-summary');
    var printBtn = qs('.js-print-modal');
    if(btn && modal){ btn.addEventListener('click', function(){ modal.classList.add('is-open'); document.body.classList.add('kp-dept-summary-open'); }); }
    if(closeBtn && modal){ closeBtn.addEventListener('click', function(){ modal.classList.remove('is-open'); document.body.classList.remove('kp-dept-summary-open'); }); }
    if(modal){ modal.addEventListener('click', function(ev){ if(ev.target === modal){ modal.classList.remove('is-open'); document.body.classList.remove('kp-dept-summary-open'); } }); }
    if(printBtn){
      printBtn.addEventListener('click', function(){
        setPrintMode('modal');
        updateModalPrintHeader();
        triggerPrintWithGuard();
      });
    }
    if(window && typeof window.addEventListener === 'function'){
      window.addEventListener('afterprint', function(){
        setPrintMode(lastPrintMode || 'special');
        renderPrintContainer();
      });
    }
  }

  function init(){
    var qsParams = new URLSearchParams(window.location.search);
    var initialMode = (qsParams.get('mode') || 'special').toLowerCase();
    setPrintMode(initialMode === 'normal' ? 'normal' : 'special');
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
    // Initialize special chips and bulk-mark buttons once on load
    initSpecialChips();
    initBulkMarkButtons();
    renderPrintContainer();
    updateModalPrintHeader();
    var state = loadPlaneringState();
    if(state && Array.isArray(state.selected_diets)){
      selectedSpecialDietIds = new Set(state.selected_diets.map(String));
      qsa('.js-special-chip').forEach(function(btn){
        var id = String(btn.getAttribute('data-diet-id') || '');
        var active = selectedSpecialDietIds.has(id);
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-pressed', active ? 'true' : 'false');
      });
    }
    if(state){
      applyStoredInputs(state);
      if(state.bulk_marked){
        var markBtn = qs('.js-bulk-mark');
        if(markBtn){
          markBtn.classList.add('is-success');
          markBtn.textContent = 'Markerat ✅';
          markBtn.dataset.success = '1';
          markBtn.disabled = true;
        }
      }
    }
    renderSpecialSelectedList();
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
    qsa('.kp-what-input, .alt-dish-input').forEach(function(input){
      input.addEventListener('input', function(){
        savePlaneringState();
        renderPrintContainer();
      });
    });
  }

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
