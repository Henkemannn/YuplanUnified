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
  var selectedChipsNormal = { 1: new Set(), 2: new Set() };
  // Alt group department IDs and per-department diet counts
  var altGroups = { alt1_dept_ids: [], alt2_dept_ids: [] };
  var dietCountsByDept = {};
  // Specialkost selection state
  var selectedChipsSpecial = new Set();
  var isSpecialChipHandlerBound = false;
  var isNormalChipHandlerBound = false;
  var specialSummary = { totals: [], per_department: [] };
  var specialById = {};
  var specialPerDept = [];
  var serviceAddonsSummary = [];
  var selectedServiceAddonId = '';
  var lastPrintMode = 'special';
  var lastSpecialWorklist = [];

  function getDietFamily(item){
    if(item && typeof item === 'object'){
      var fam = String(item.family || '').trim();
      if(fam){ return fam; }
      var nm = String(item.name || '').trim().toLowerCase();
      if(nm.indexOf('timbal') !== -1){ return 'Textur'; }
      return 'Övrigt';
    }
    var low = String(item || '').toLowerCase();
    if(low.indexOf('timbal') !== -1){ return 'Textur'; }
    return 'Övrigt';
  }

  function getDietFamilyLabel(family){
    var fam = String(family || '').trim();
    return fam || 'Övrigt';
  }

  function deriveProductionGroupName(dietName){
    var clean = String(dietName || '').trim();
    if(!clean){ return ''; }
    var low = clean.toLowerCase();
    if(low.indexOf('timbal') !== -1){ return 'Timbal'; }
    if(low.indexOf('grovpat') !== -1 || low.indexOf('grov pat') !== -1){ return 'Grovpaté'; }
    var lead = String((clean.split(/[-–(]/)[0] || '')).trim();
    if(lead && lead.length >= 4 && lead.length < clean.length){
      return lead;
    }
    return clean;
  }

  function buildProductionSpecialGroups(selectedIds){
    var selectedSet = new Set((selectedIds || []).map(String));
    if(selectedSet.size === 0 || !specialPerDept || specialPerDept.length === 0){
      return [];
    }

    var byDiet = {};
    var totalsByDiet = {};
    for(var i=0; i<specialPerDept.length; i++){
      var dep = specialPerDept[i] || {};
      var depItems = dep.items || [];
      for(var j=0; j<depItems.length; j++){
        var row = depItems[j] || {};
        var dietId = String(row.diet_type_id || '');
        if(!dietId || !selectedSet.has(dietId) || !specialById[dietId]){ continue; }
        if(!byDiet[dietId]){ byDiet[dietId] = []; }
        var cnt = parseInt(row.count || 0, 10) || 0;
        byDiet[dietId].push({
          department_id: String(dep.department_id || ''),
          department_name: String(dep.department_name || ''),
          count: cnt
        });
        totalsByDiet[dietId] = (totalsByDiet[dietId] || 0) + cnt;
      }
    }

    var dietIds = Object.keys(byDiet).sort(function(a, b){
      var ta = totalsByDiet[a] || 0;
      var tb = totalsByDiet[b] || 0;
      if(tb !== ta){ return tb - ta; }
      var na = (specialById[a] && specialById[a].name) || a;
      var nb = (specialById[b] && specialById[b].name) || b;
      return String(na).localeCompare(String(nb));
    });

    var groupsByKey = {};
    var groupOrder = [];
    for(var g=0; g<dietIds.length; g++){
      var did = dietIds[g];
      var variantName = (specialById[did] && specialById[did].name) || did;
      var productionGroupName = deriveProductionGroupName(variantName) || variantName;
      var groupKey = 'production:' + String(productionGroupName).toLowerCase();
      if(!groupsByKey[groupKey]){
        groupsByKey[groupKey] = {
          group_id: groupKey,
          production_group_name: productionGroupName,
          group_title: productionGroupName + ' totalt',
          total: 0,
          variants: [],
          departments: {}
        };
        groupOrder.push(groupKey);
      }
      var rows = byDiet[did] || [];
      var variantTotal = totalsByDiet[did] || 0;
      groupsByKey[groupKey].total += variantTotal;
      groupsByKey[groupKey].variants.push({
        diet_type_id: did,
        diet_type_name: variantName,
        count: variantTotal,
        rows: rows
      });
      for(var r=0; r<rows.length; r++){
        var depRow = rows[r] || {};
        var depKey = String(depRow.department_id || '');
        if(!groupsByKey[groupKey].departments[depKey]){
          groupsByKey[groupKey].departments[depKey] = {
            department_id: depKey,
            department_name: String(depRow.department_name || ''),
            total: 0,
            subtype_counts: {}
          };
        }
        groupsByKey[groupKey].departments[depKey].total += (parseInt(depRow.count || 0, 10) || 0);
        groupsByKey[groupKey].departments[depKey].subtype_counts[variantName] =
          (groupsByKey[groupKey].departments[depKey].subtype_counts[variantName] || 0) + (parseInt(depRow.count || 0, 10) || 0);
      }
    }

    var groups = groupOrder.map(function(key){
      var groupDef = groupsByKey[key];
      var variants = (groupDef.variants || []).slice().sort(function(a, b){
        if((b.count || 0) !== (a.count || 0)){ return (b.count || 0) - (a.count || 0); }
        return String(a.diet_type_name || '').localeCompare(String(b.diet_type_name || ''));
      });
      var departments = Object.keys(groupDef.departments || {}).map(function(depKey){
        var dep = groupDef.departments[depKey] || {};
        var subtypeCounts = Object.keys(dep.subtype_counts || {}).map(function(name){
          return {
            diet_type_name: name,
            count: parseInt(dep.subtype_counts[name] || 0, 10) || 0
          };
        }).sort(function(a, b){
          if((b.count || 0) !== (a.count || 0)){ return (b.count || 0) - (a.count || 0); }
          return String(a.diet_type_name || '').localeCompare(String(b.diet_type_name || ''));
        });
        return {
          department_id: String(dep.department_id || ''),
          department_name: String(dep.department_name || ''),
          total: parseInt(dep.total || 0, 10) || 0,
          subtype_counts: subtypeCounts
        };
      }).sort(function(a, b){
        return String(a.department_name || '').localeCompare(String(b.department_name || ''));
      });
      return {
        group_id: groupDef.group_id,
        production_group_name: groupDef.production_group_name,
        group_title: groupDef.group_title,
        total: parseInt(groupDef.total || 0, 10) || 0,
        subtype_breakdown: variants.map(function(v){
          return {
            diet_type_id: String(v.diet_type_id || ''),
            diet_type_name: String(v.diet_type_name || ''),
            count: parseInt(v.count || 0, 10) || 0
          };
        }),
        department_breakdown: departments,
        rows: departments.map(function(dep){
          return {
            department_id: dep.department_id,
            department_name: dep.department_name,
            count: dep.total
          };
        })
      };
    });

    groups.sort(function(a, b){
      if((b.total || 0) !== (a.total || 0)){ return (b.total || 0) - (a.total || 0); }
      return String(a.production_group_name || '').localeCompare(String(b.production_group_name || ''));
    });
    return groups;
  }

  function buildDepartmentSubtypeNote(subtypeCounts, productionGroupName, rowTotal){
    var list = Array.isArray(subtypeCounts) ? subtypeCounts : [];
    if(!list.length){ return ''; }
    var base = String(productionGroupName || '').trim().toLowerCase();
    var total = parseInt(rowTotal || 0, 10) || 0;
    if(list.length === 1){
      var one = list[0] || {};
      var oneName = String(one.diet_type_name || '').trim();
      var oneCount = parseInt(one.count || 0, 10) || 0;
      if(base && oneName.toLowerCase() === base && oneCount === total){
        return '';
      }
      return oneName;
    }
    return list
      .map(function(item){ return String((item && item.diet_type_name) || '').trim(); })
      .filter(function(name){ return !!name; })
      .join(', ');
  }

  function setSpecialChipState(dietId, isActive){
    qsa('.specialkost-view .js-special-chip[data-diet-id="' + String(dietId || '') + '"]').forEach(function(btn){
      if(isActive){
        btn.classList.add('active');
        btn.setAttribute('aria-pressed', 'true');
      } else {
        btn.classList.remove('active');
        btn.setAttribute('aria-pressed', 'false');
      }
    });
  }

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
        selected_diets: Array.from(selectedChipsSpecial),
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
      var deptIds = alt === 2 ? (altGroups.alt2_dept_ids || []) : (altGroups.alt1_dept_ids || []);
      var diets = Array.from((selectedChipsNormal[alt] || new Set()));
      var s = 0;
      for(var d=0; d<diets.length; d++){
        var dietId = String(diets[d]);
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

  function getExcludedForDepartment(alt, departmentId){
    try {
      var diets = Array.from((selectedChipsNormal[alt] || new Set()));
      var deptKey = String(departmentId || '');
      var perDept = null;
      if(specialPerDept && specialPerDept.length > 0){
        for(var p=0; p<specialPerDept.length; p++){
          var dep = specialPerDept[p];
          if(String(dep.department_id || '') !== deptKey) continue;
          perDept = {};
          var items = dep.items || [];
          for(var it=0; it<items.length; it++){
            var item = items[it] || {};
            perDept[String(item.diet_type_id || '')] = parseInt(item.count || 0, 10) || 0;
          }
          break;
        }
      }
      if(!perDept){ perDept = (dietCountsByDept && dietCountsByDept[deptKey]) || {}; }
      var total = 0;
      for(var i=0; i<diets.length; i++){
        var dietId = String(diets[i]);
        var raw = perDept[dietId];
        var cnt = parseInt(raw || '0', 10);
        if(!isNaN(cnt)) total += cnt;
      }
      return total;
    } catch(e){
      return 0;
    }
  }

  function buildNormalLunchModel(){
    if((!specialPerDept || specialPerDept.length === 0) && qs('#kp-context')){
      var parsedSpecial = parseSpecialSummary();
      if(parsedSpecial && parsedSpecial.per_department){
        specialPerDept = (parsedSpecial.per_department || []).map(function(dep){
          var depItems = dep.items || dep['items'] || [];
          return {
            department_id: String(dep.department_id || ''),
            department_name: String(dep.department_name || ''),
            items: depItems.map(function(row){
              return {
                diet_type_id: String(row.diet_type_id || ''),
                count: parseInt(row.count || 0, 10) || 0
              };
            })
          };
        });
      }
    }
    var rows = parseNormalkostRows();
    var totals = { alt1: 0, alt2: 0, total: 0 };
    var overflow = false;
    var mapped = [];
    var alt2Set = new Set((altGroups && altGroups.alt2_dept_ids) || []);
    for(var i=0; i<rows.length; i++){
      var row = rows[i] || {};
      var departmentId = row.department_id || row.departmentId || row.id || '';
      var deptKey = String(departmentId || '');
      var baseAlt1 = parseInt(row.alt1 || '0', 10);
      var baseAlt2 = parseInt(row.alt2 || '0', 10);
      if(isNaN(baseAlt1)) baseAlt1 = 0;
      if(isNaN(baseAlt2)) baseAlt2 = 0;
      var explicitChoice = String(row.selected_alt || row.alt_choice || row.choice || '').toLowerCase();
      var deptChoice = 'alt1';
      if(explicitChoice === 'alt2' || explicitChoice === '2'){
        deptChoice = 'alt2';
      } else if(explicitChoice === 'alt1' || explicitChoice === '1'){
        deptChoice = 'alt1';
      } else if(alt2Set.has(deptKey)){
        deptChoice = 'alt2';
      } else if(baseAlt2 > 0 && baseAlt1 === 0){
        deptChoice = 'alt2';
      }
      var exChosen = getExcludedForDepartment(deptChoice === 'alt2' ? 2 : 1, departmentId);
      if(deptChoice === 'alt2'){
        if(exChosen > baseAlt2){ overflow = true; }
      } else {
        if(exChosen > baseAlt1){ overflow = true; }
      }
      var alt1 = baseAlt1;
      var alt2 = baseAlt2;
      if(deptChoice === 'alt2'){
        alt2 = clamp(baseAlt2 - Math.min(baseAlt2, exChosen), 0, baseAlt2);
      } else {
        alt1 = clamp(baseAlt1 - Math.min(baseAlt1, exChosen), 0, baseAlt1);
      }
      totals.alt1 += alt1;
      totals.alt2 += alt2;
      totals.total += (alt1 + alt2);
      mapped.push({
        department_id: deptKey,
        department_name: String(row.department_name || ''),
        alt1: alt1,
        alt2: alt2,
        alt_choice: deptChoice
      });
    }
    return { rows: mapped, totals: totals, overflow: overflow };
  }

  function renderNormalLunchTableRows(model){
    var tbody = document.getElementById('kp-normal-table-body');
    if(!tbody) return;
    var rows = (model && model.rows) || [];
    var html = rows.map(function(row){
      return '<tr>'
        + '<td class="kp-text-left">' + String(row.department_name || '') + '</td>'
        + '<td>' + String(row.alt1 || 0) + '</td>'
        + '<td class="is-alt2">' + String(row.alt2 || 0) + '</td>'
        + '</tr>';
    }).join('');
    tbody.innerHTML = html;
  }

  function buildNormalSingleModel(){
    var rows = parseNormalkostRows();
    var total = 0;
    var overflow = false;
    var mapped = [];
    for(var i=0; i<rows.length; i++){
      var row = rows[i] || {};
      var departmentId = row.department_id || row.departmentId || row.id || '';
      var baseTotal = parseInt(row.total || '0', 10);
      if(isNaN(baseTotal)) baseTotal = 0;
      var excluded = getExcludedForDepartment(1, departmentId);
      if(excluded > baseTotal){ overflow = true; }
      var remaining = clamp(baseTotal - Math.min(baseTotal, excluded), 0, baseTotal);
      total += remaining;
      mapped.push({
        department_id: String(departmentId || ''),
        department_name: String(row.department_name || ''),
        total: remaining
      });
    }
    return { rows: mapped, total: total, overflow: overflow };
  }

  function renderNormalSingleTableRows(model){
    var tbody = document.getElementById('kp-normal-single-table-body');
    if(!tbody) return;
    var rows = (model && model.rows) || [];
    var html = rows.map(function(row){
      return '<tr>'
        + '<td class="kp-text-left">' + String(row.department_name || '') + '</td>'
        + '<td>' + String(row.total || 0) + '</td>'
        + '</tr>';
    }).join('');
    tbody.innerHTML = html;
  }

  function renderAllTotals(){
    var ctx = qs('#kp-context');
    if(!ctx) return;
    var meal = ctx.getAttribute('data-meal');
    var modeParam = (new URLSearchParams(window.location.search).get('mode')||'').toLowerCase();
    var mode = modeParam || 'special';
    if(mode !== 'normal') return;
    if(meal === 'lunch'){
      var model = buildNormalLunchModel();
      var alt1 = model.totals.alt1;
      var alt2 = model.totals.alt2;
      var total = alt1 + alt2;
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
      if(warn){ warn.style.display = model.overflow ? 'block' : 'none'; }
      renderNormalLunchTableRows(model);
      return;
    }
    if(meal === 'dinner' || meal === 'dessert'){
      var singleModel = buildNormalSingleModel();
      var elSumSingle = qs('#kp-total-sum');
      if(elSumSingle) elSumSingle.textContent = String(singleModel.total);
      var resTotal = qs('[data-result-normal="total"]');
      if(resTotal) resTotal.textContent = String(singleModel.total);
      var warnSingle = qs('#kp-exclusions-warning');
      if(warnSingle){ warnSingle.style.display = singleModel.overflow ? 'block' : 'none'; }
      renderNormalSingleTableRows(singleModel);
    }
  }

  function renderSpecialSelectedList(){
    var list = qs('#kp-special-worklist');
    var empty = qs('#kp-special-selected-empty');
    if(!list || !empty) return;
    list.innerHTML = '';
    var selected = Array.from(selectedChipsSpecial);
    if(!specialPerDept || specialPerDept.length === 0){
      var groups = qsa('#kp-special-worklist .kp-worklist-group');
      if(selected.length === 0){
        empty.style.display = 'block';
        groups.forEach(function(group){ group.style.display = 'none'; });
      } else {
        empty.style.display = 'none';
        groups.forEach(function(group){
          var id = String(group.getAttribute('data-diet-id') || '');
          group.style.display = selectedChipsSpecial.has(id) ? '' : 'none';
        });
      }
      updateBulkButtonState();
      renderDeptSummary();
      renderSpecialResults();
      return;
    }

    if(selected.length === 0){
      empty.style.display = 'block';
      updateBulkButtonState();
      renderDeptSummary();
      renderSpecialResults();
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
        if(selectedChipsSpecial.has(dietId) && specialById[dietId]){
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

    var groups = buildProductionSpecialGroups(selected);
    lastSpecialWorklist = groups.map(function(groupDef){
      return {
        diet_type_id: String(groupDef.group_id || ''),
        production_group_name: String(groupDef.production_group_name || ''),
        diet_type_name: String(groupDef.group_title || ''),
        total: parseInt(groupDef.total || 0, 10) || 0,
        subtype_breakdown: (groupDef.subtype_breakdown || []).map(function(sub){
          return {
            diet_type_id: String(sub.diet_type_id || ''),
            diet_type_name: String(sub.diet_type_name || ''),
            count: parseInt(sub.count || 0, 10) || 0
          };
        }),
        department_breakdown: (groupDef.department_breakdown || []).map(function(dep){
          return {
            department_id: String(dep.department_id || ''),
            department_name: String(dep.department_name || ''),
            total: parseInt(dep.total || 0, 10) || 0,
            subtype_counts: (dep.subtype_counts || []).map(function(sub){
              return {
                diet_type_name: String(sub.diet_type_name || ''),
                count: parseInt(sub.count || 0, 10) || 0
              };
            })
          };
        }),
        rows: (groupDef.rows || []).map(function(r){
          return {
            department_id: r.department_id,
            department_name: r.department_name,
            count: r.count
          };
        })
      };
    });

    for(var d=0; d<groups.length; d++){
      var groupDef = groups[d] || {};
      var group = document.createElement('div');
      group.className = 'kp-worklist-group';
      group.setAttribute('data-diet-id', String(groupDef.group_id || ''));
      var title = document.createElement('div');
      title.className = 'kp-worklist-title';
      title.textContent = String(groupDef.group_title || '') + ' ';
      var totalSpan = document.createElement('span');
      totalSpan.className = 'kp-worklist-total';
      totalSpan.textContent = String(groupDef.total || 0);
      title.appendChild(totalSpan);
      group.appendChild(title);

      var subtypes = groupDef.subtype_breakdown || [];
      if(subtypes.length > 0){
        var subtypeLine = document.createElement('div');
        subtypeLine.className = 'kp-production-subtypes-line';
        subtypeLine.textContent = subtypes.map(function(sub){
          return String((sub && sub.diet_type_name) || '') + ' ' + String((sub && sub.count) || 0);
        }).join(' \u2022 ');
        group.appendChild(subtypeLine);
      }

      var depHeading = document.createElement('div');
      depHeading.className = 'kp-worklist-subheading';
      depHeading.textContent = 'Till avdelningar';
      group.appendChild(depHeading);

      var rowsWrap = document.createElement('div');
      rowsWrap.className = 'kp-worklist-rows';
      var rows = groupDef.department_breakdown || groupDef.rows || [];
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
        countEl.textContent = String((row.total != null ? row.total : row.count) || 0);
        rowEl.appendChild(nameEl);
        rowEl.appendChild(countEl);
        if(row.subtype_counts && row.subtype_counts.length){
          var subtypeNote = buildDepartmentSubtypeNote(
            row.subtype_counts,
            groupDef.production_group_name,
            (row.total != null ? row.total : row.count)
          );
          if(subtypeNote){
            var subtypeText = document.createElement('span');
            subtypeText.className = 'kp-row-subtypes';
            subtypeText.textContent = '(' + subtypeNote + ')';
            rowEl.appendChild(subtypeText);
          }
        }
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
    renderSpecialResults();
  }

  function buildSpecialResultsModel(){
    var ctx = qs('#kp-context');
    if(!ctx) return null;
    var meal = ctx.getAttribute('data-meal') || '';
    var selected = Array.from(selectedChipsSpecial);
    var rows = [];
    var totals = { alt1: 0, alt2: 0, total: 0 };
    if(!specialPerDept || specialPerDept.length === 0){
      return { meal: meal, rows: rows, totals: totals, selected: selected };
    }
    if(selected.length === 0){
      return { meal: meal, rows: rows, totals: totals, selected: selected };
    }
    var alt2Set = new Set((altGroups && altGroups.alt2_dept_ids) || []);
    for(var i=0;i<specialPerDept.length;i++){
      var dep = specialPerDept[i];
      var deptTotal = 0;
      for(var j=0;j<dep.items.length;j++){
        var row = dep.items[j];
        var dietId = String(row.diet_type_id);
        if(selectedChipsSpecial.has(dietId)){
          deptTotal += parseInt(row.count || 0, 10) || 0;
        }
      }
      if(deptTotal === 0){
        continue;
      }
      var isAlt2 = (meal === 'lunch' && alt2Set.has(String(dep.department_id)));
      var alt1 = isAlt2 ? 0 : deptTotal;
      var alt2 = isAlt2 ? deptTotal : 0;
      totals.alt1 += alt1;
      totals.alt2 += alt2;
      totals.total += deptTotal;
      rows.push({
        department_id: String(dep.department_id || ''),
        department_name: String(dep.department_name || ''),
        alt1: alt1,
        alt2: alt2,
        total: deptTotal
      });
    }
    return { meal: meal, rows: rows, totals: totals, selected: selected };
  }

  function renderSpecialResults(){
    var model = buildSpecialResultsModel();
    if(!model) return;
    var elA1 = qs('#kp-total-alt1');
    var elA2 = qs('#kp-total-alt2');
    var elSum = qs('#kp-total-sum');
    if(elA1) elA1.textContent = String(model.totals.alt1);
    if(elA2) elA2.textContent = String(model.totals.alt2);
    if(elSum) elSum.textContent = String(model.totals.total);
    var resA1 = qs('[data-result-normal="alt1"]');
    var resA2 = qs('[data-result-normal="alt2"]');
    if(resA1) resA1.textContent = String(model.totals.alt1);
    if(resA2) resA2.textContent = String(model.totals.alt2);
    var table = qs('.kitchen-planering-card--planering .grid-table');
    if(!table) return;
    var tbody = table.querySelector('tbody');
    if(!tbody) return;
    tbody.innerHTML = '';
    if(model.rows.length === 0){
      return;
    }
    if(model.meal === 'lunch'){
      model.rows.forEach(function(row){
        var tr = document.createElement('tr');
        var tdName = document.createElement('td');
        tdName.className = 'kp-text-left';
        tdName.textContent = row.department_name;
        var tdA1 = document.createElement('td');
        tdA1.textContent = String(row.alt1);
        var tdA2 = document.createElement('td');
        tdA2.className = 'is-alt2';
        tdA2.textContent = String(row.alt2);
        tr.appendChild(tdName);
        tr.appendChild(tdA1);
        tr.appendChild(tdA2);
        tbody.appendChild(tr);
      });
    } else {
      model.rows.forEach(function(row){
        var tr2 = document.createElement('tr');
        var tdName2 = document.createElement('td');
        tdName2.className = 'kp-text-left';
        tdName2.textContent = row.department_name;
        var tdTotal = document.createElement('td');
        tdTotal.textContent = String(row.total);
        tr2.appendChild(tdName2);
        tr2.appendChild(tdTotal);
        tbody.appendChild(tr2);
      });
      var totalCell = table.querySelector('tfoot th:last-child');
      if(totalCell) totalCell.textContent = String(model.totals.total);
    }
  }

  function updateBulkButtonState(){
    var btn = qs('.js-bulk-mark');
    if(!btn) return;
    if(btn.dataset && btn.dataset.defaultLabel && btn.dataset.success === '1'){
      btn.classList.remove('is-success');
      btn.textContent = btn.dataset.defaultLabel;
      btn.dataset.success = '0';
    }
    btn.disabled = (selectedChipsSpecial.size === 0);
  }

  function renderDeptSummary(){
    var body = qs('#dept-summary-body');
    if(!body) return;
    body.innerHTML = '';
    var selected = Array.from(selectedChipsSpecial);
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
        if(selectedChipsSpecial.has(dietId) && specialById[dietId]){
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
    var allIds = Object.keys(specialById || {});
    if(allIds.length === 0){ return []; }
    var groups = buildProductionSpecialGroups(allIds);
    return groups.map(function(groupDef){
      return {
        diet_type_id: String(groupDef.group_id || ''),
        production_group_name: String(groupDef.production_group_name || ''),
        diet_type_name: String(groupDef.group_title || ''),
        total: parseInt(groupDef.total || 0, 10) || 0,
        subtype_breakdown: (groupDef.subtype_breakdown || []).map(function(sub){
          return {
            diet_type_id: String(sub.diet_type_id || ''),
            diet_type_name: String(sub.diet_type_name || ''),
            count: parseInt(sub.count || 0, 10) || 0
          };
        }),
        department_breakdown: (groupDef.department_breakdown || []).map(function(dep){
          return {
            department_id: String(dep.department_id || ''),
            department_name: String(dep.department_name || ''),
            total: parseInt(dep.total || 0, 10) || 0,
            subtype_counts: (dep.subtype_counts || []).map(function(sub){
              return {
                diet_type_name: String(sub.diet_type_name || ''),
                count: parseInt(sub.count || 0, 10) || 0
              };
            })
          };
        }),
        rows: (groupDef.rows || []).map(function(r){
          return {
            department_id: r.department_id,
            department_name: r.department_name,
            count: r.count
          };
        })
      };
    });
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
    var selectedAddon = null;
    for(var sa=0; sa<serviceAddonsSummary.length; sa++){
      var cand = serviceAddonsSummary[sa] || {};
      if(String(cand.addon_id || '') === String(selectedServiceAddonId || '')){
        selectedAddon = cand;
        break;
      }
    }

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
      modalBody.className = 'kp-print-modal-body';
      var blocks = [];
      for(var p=0; p<specialPerDept.length; p++){
        var dep = specialPerDept[p];
        var items = [];
        for(var j=0; j<dep.items.length; j++){
          var row = dep.items[j];
          if(selectedChipsSpecial.has(String(row.diet_type_id))){
            items.push({
              diet_type_name: row.diet_type_name,
              count: row.count
            });
          }
        }
        if(items.length > 0){
          blocks.push({
            department_id: dep.department_id,
            department_name: dep.department_name,
            items: items
          });
        }
      }
      if(blocks.length === 0){
        var emptyBlock = document.createElement('div');
        emptyBlock.className = 'kp-print-empty';
        emptyBlock.textContent = 'Inga avdelningar';
        modalBody.appendChild(emptyBlock);
      } else {
        for(var r=0; r<blocks.length; r++){
          var item = blocks[r];
          var isAlt2Row = (meal === 'lunch' && alt2Set.has(String(item.department_id)));
          var group = document.createElement('div');
          group.className = 'kp-print-modal-dept';

          var head = document.createElement('div');
          head.className = 'kp-print-modal-dept-head';
          head.textContent = item.department_name;
          if(isAlt2Row){
            var badge = document.createElement('span');
            badge.className = 'kp-altpill';
            badge.textContent = 'Alt2';
            head.appendChild(badge);
          }
          group.appendChild(head);

          var list = document.createElement('div');
          list.className = 'kp-print-modal-dept-list';
          for(var d=0; d<item.items.length; d++){
            var diet = item.items[d];
            var rowEl = document.createElement('div');
            rowEl.className = 'kp-print-modal-dept-row';
            rowEl.textContent = String(diet.diet_type_name || '') + ' (' + String(diet.count || 0) + ')';
            list.appendChild(rowEl);
          }
          group.appendChild(list);
          modalBody.appendChild(group);
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

          var subtypeBreakdown = block.subtype_breakdown || [];
          if(subtypeBreakdown.length > 0){
            var variantLine = document.createElement('div');
            variantLine.className = 'kp-print-variant-line';
            variantLine.textContent = subtypeBreakdown.map(function(variant){
              return String((variant && variant.diet_type_name) || '') + ' ' + String((variant && variant.count) || 0);
            }).join(' \u2022 ');
            group.appendChild(variantLine);
          }

          var depSubhead = document.createElement('div');
          depSubhead.className = 'kp-print-subheading';
          depSubhead.textContent = 'Till avdelningar';
          group.appendChild(depSubhead);

          var list = document.createElement('div');
          list.className = 'kp-print-list';
          var rows = block.department_breakdown || block.rows || [];
          if(rows.length === 0){
            list.appendChild(buildPrintRow('sk-row kp-zebra', 'Inga avdelningar', 0, 'Alt1'));
          } else {
            for(var r=0; r<rows.length; r++){
              var item = rows[r];
              var isAlt2 = (meal === 'lunch' && alt2Set.has(String(item.department_id)));
              var rowEl = buildPrintRow('sk-row kp-zebra', item.department_name, (item.total != null ? item.total : item.count), isAlt2 ? 'Alt2' : 'Alt1');
              if(item.subtype_counts && item.subtype_counts.length){
                var detailNote = buildDepartmentSubtypeNote(
                  item.subtype_counts,
                  block.production_group_name || block.diet_type_name,
                  (item.total != null ? item.total : item.count)
                );
                if(detailNote){
                  var detail = document.createElement('span');
                  detail.className = 'kp-print-row-subtypes';
                  detail.textContent = '(' + detailNote + ')';
                  rowEl.appendChild(detail);
                }
              }
              list.appendChild(rowEl);
            }
          }
          group.appendChild(list);
          special.appendChild(group);
        }
      }
      sheet.appendChild(special);
    }

    if(selectedAddon && selectedAddon.total_count > 0){
      var addonSection = document.createElement('div');
      addonSection.className = 'kp-print-special';
      var addonHead = document.createElement('div');
      addonHead.className = 'kp-print-section-title';
      addonHead.textContent = 'Serveringstillägg';
      addonSection.appendChild(addonHead);

      var addonTitle = document.createElement('div');
      addonTitle.className = 'kp-print-special-name';
      addonTitle.textContent = String(selectedAddon.addon_name || '') + ' — Totalt ' + String(selectedAddon.total_count || 0);
      addonSection.appendChild(addonTitle);

      var addonList = document.createElement('div');
      addonList.className = 'kp-print-list';
      var depRows = selectedAddon.departments || [];
      for(var ai=0; ai<depRows.length; ai++){
        var depRow = depRows[ai] || {};
        var row = document.createElement('div');
        row.className = 'kp-print-row sk-row kp-zebra';
        var note = String(depRow.note || '').trim();
        var label = String(depRow.department_name || '');
        if(note){
          label += ' (' + note + ')';
        }
        row.innerHTML = '<span class="kp-dept-name">' + label + '</span>'
          + '<span class="kp-altpill-slot" aria-hidden="true"></span>'
          + '<span class="count">' + String(depRow.count || 0) + '</span>';
        addonList.appendChild(row);
      }
      addonSection.appendChild(addonList);
      sheet.appendChild(addonSection);
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
    var specialView = qs('.specialkost-view');
    if(!specialView) return;
    var chipGrid = specialView.querySelector('[data-mode="special"]');
    var chips = Array.prototype.slice.call(specialView.querySelectorAll('.js-special-chip'));
    if(!chipGrid || !chips.length) return;
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
          name: nm,
          family: String(it.diet_family || it.family || 'Övrigt')
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
            diet_family: String(row.diet_family || specialById[dietId].family || 'Övrigt'),
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
    selectedChipsSpecial = new Set((initialSelected || []).map(String));
    chips.forEach(function(btn){
      var id = String(btn.getAttribute('data-diet-id') || '');
      var isActive = selectedChipsSpecial.has(id);
      setSpecialChipState(id, isActive);
    });
    if(!isSpecialChipHandlerBound){
      specialView.addEventListener('click', function(e){
        var btn = e.target && e.target.closest && e.target.closest('.js-special-chip');
        if(!btn) return;
        if(!btn.closest('.specialkost-view')) return;
        var id = String(btn.getAttribute('data-diet-id') || '');
        if(!id) return;
        if(selectedChipsSpecial.has(id)){
          selectedChipsSpecial.delete(id);
          setSpecialChipState(id, false);
        } else {
          selectedChipsSpecial.add(id);
          setSpecialChipState(id, true);
        }
        renderSpecialSelectedList();
      });
      isSpecialChipHandlerBound = true;
    }
    renderSpecialSelectedList();
  }

  function clearNormalChipState(){
    selectedChipsNormal = { 1: new Set(), 2: new Set() };
    qsa('.normalkost-view .js-normal-chip').forEach(function(btn){
      btn.classList.remove('active');
    });
  }

  function clearSpecialChipState(){
    selectedChipsSpecial = new Set();
    qsa('.specialkost-view .js-special-chip').forEach(function(btn){
      btn.classList.remove('active');
      btn.setAttribute('aria-pressed', 'false');
    });
  }

  function resetChipStateForMode(mode){
    var next = String(mode || '').toLowerCase();
    if(next === 'special'){
      clearNormalChipState();
      renderAllTotals();
      return;
    }
    if(next === 'normal'){
      clearSpecialChipState();
      renderSpecialSelectedList();
    }
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
      if(selectedChipsSpecial.size > 0){
        var selected = Array.from(selectedChipsSpecial);
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
      resetChipStateForMode(mode);
      var url = new URL(window.location.href);
      url.searchParams.set('mode', mode);
      url.searchParams.delete('selected_diets');
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
    var idx = parseInt(dayIndex, 10);
    if(isNaN(idx)) return null;
    if(idx < 0 || idx > 6){
      if(idx >= 1 && idx <= 7){
        idx = idx - 1;
      } else {
        return null;
      }
    }
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
    if(!el) return;
    var next = String(value || '').trim();
    var current = String(el.textContent || '').trim();
    if(next){
      el.textContent = next;
      return;
    }
    if(current){
      return;
    }
    el.textContent = '—';
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
    var currentTitleText = String((qs('#kp-planering-title') || {}).textContent || '').trim();
    var qsParams = new URLSearchParams(window.location.search);
    var siteId = qsParams.get('site_id') || (ctx && ctx.getAttribute('data-site-id')) || '';
    var mode = (qsParams.get('mode') || 'special').toLowerCase();
    var year = qsParams.get('year') || '';
    var week = qsParams.get('week') || '';
    var dayIndex = parseInt(ctx.getAttribute('data-day-index'), 10);
    var meal = ctx.getAttribute('data-meal');
    var serverDishLabel = String(ctx.getAttribute('data-current-dish-label') || '').trim();
    if(isNaN(dayIndex) || meal == null) return;

    if(!siteId){
      console.warn('Missing site_id in planering URL');
      var fb = serverDishLabel || currentTitleText || '—';
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
      var fallback = serverDishLabel || currentTitleText || '—';
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
      var dinnerDish = (meal === 'dinner') ? (alt1 || alt2 || fallback) : '';
      var dessertDish = (meal === 'dessert') ? (alt1 || alt2 || '') : '';
      if(meal === 'dessert' && !dessertDish){
        var dayObj = resolveDay(data, dayIndex) || {};
        var dessertResolved = pick(dayObj, [
          'Dessert.main', 'Dessert.name', 'Dessert.dish_name',
          'dessert.main', 'dessert.name', 'dessert.dish_name',
          'Lunch.dessert', 'lunch.dessert',
          'Dinner.dessert', 'dinner.dessert'
        ]);
        dessertDish = dessertResolved || '';
      }
      if(meal === 'dessert' && !dessertDish){
        dessertDish = fallback;
      }
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
        if(ed) ed.textContent = dinnerDish;
        if(mode === 'normal'){
          var nd = qs('.alt-dish-input');
          if(nd) setInputValue(nd, dinnerDish || '', true);
        }
        if(mode === 'special'){
          var sd = qs('#kp-what-dinner');
          if(sd) setInputValue(sd, dinnerDish || '', true);
        }
      } else {
        var es = qs('#kp-dessert-main');
        if(es) es.textContent = dessertDish;
        if(mode === 'normal'){
          var ndes = qs('.alt-dish-input');
          if(ndes) setInputValue(ndes, dessertDish || '', true);
        }
        if(mode === 'special'){
          var ds = qs('#kp-what-dessert');
          if(ds) setInputValue(ds, dessertDish || '', true);
        }
      }
      suggestionText = buildSuggestionText(mode, meal, { alt1: alt1, alt2: alt2, dinner: dinnerDish, dessert: dessertDish }, fallback);
      setPlaneringTitle(suggestionText);
    })
    .catch(function(){ /* ignore */ });
  }

  function initPrintButton(){
    var btn = qs('.js-print');
    if(btn){
      btn.addEventListener('click', function(ev){
        if(ev && typeof ev.preventDefault === 'function') ev.preventDefault();
        if(ev && typeof ev.stopPropagation === 'function') ev.stopPropagation();
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

  function initPlanTabs(){
    var tabs = qsa('[data-plan-tab]');
    var panels = qsa('[data-plan-panel]');
    if(!tabs.length || !panels.length){ return; }

    function activateTab(tabName){
      tabs.forEach(function(tab){
        var isActive = String(tab.getAttribute('data-plan-tab') || '') === String(tabName || '');
        tab.classList.toggle('is-active', isActive);
        tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
        tab.setAttribute('tabindex', isActive ? '0' : '-1');
      });
      panels.forEach(function(panel){
        var isPanelActive = String(panel.getAttribute('data-plan-panel') || '') === String(tabName || '');
        panel.hidden = !isPanelActive;
        panel.classList.toggle('is-active', isPanelActive);
      });
    }

    tabs.forEach(function(tab){
      tab.addEventListener('click', function(){
        activateTab(tab.getAttribute('data-plan-tab') || 'planera');
      });
    });

    activateTab('planera');
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

  function buildProductionListPayload(){
    var ctx = qs('#kp-context');
    if(!ctx){ return null; }
    var qsParams = new URLSearchParams(window.location.search || '');
    var mode = String(qsParams.get('mode') || 'special').toLowerCase();
    if(mode !== 'normal' && mode !== 'special'){
      mode = 'special';
    }
    var meal = String(ctx.getAttribute('data-meal') || '').trim();
    if(meal !== 'lunch' && meal !== 'dinner'){ return null; }
    var mealLabel = String(ctx.getAttribute('data-meal-label') || '');
    var dayLabel = String(ctx.getAttribute('data-day-label') || '');
    var week = parseInt(ctx.getAttribute('data-week') || '0', 10) || 0;
    var year = parseInt(ctx.getAttribute('data-year') || '0', 10) || 0;
    var dateIso = String(ctx.getAttribute('data-date-iso') || '').trim();
    var dishes = getPrintDishNames(meal);

    var alt2Set = new Set((altGroups && altGroups.alt2_dept_ids) || []);
    var normalRowsRaw = parseNormalkostRows();
    var normalRows = [];
    var alt1Total = 0;
    var alt2Total = 0;
    for(var i=0; i<normalRowsRaw.length; i++){
      var row = normalRowsRaw[i] || {};
      var depId = String(row.department_id || '');
      var depName = String(row.department_name || depId);
      var altChoice = (meal === 'lunch' && alt2Set.has(depId)) ? 'alt2' : 'alt1';
      var count = 0;
      if(meal === 'lunch'){
        count = altChoice === 'alt2' ? (parseInt(row.alt2 || 0, 10) || 0) : (parseInt(row.alt1 || 0, 10) || 0);
      } else {
        count = parseInt(row.total || 0, 10) || 0;
      }
      if(altChoice === 'alt1'){ alt1Total += count; } else { alt2Total += count; }
      normalRows.push({
        department_id: depId,
        department_name: depName,
        alt_choice: altChoice,
        count: count
      });
    }

    var worklist = (lastSpecialWorklist && lastSpecialWorklist.length > 0) ? lastSpecialWorklist : buildSpecialWorklistFromSummary();
    var specialWorklist = worklist.map(function(group){
      var rows = (group.rows || []).map(function(r){
        var isAlt2 = (meal === 'lunch' && alt2Set.has(String(r.department_id || '')));
        return {
          department_id: String(r.department_id || ''),
          department_name: String(r.department_name || ''),
          count: parseInt(r.count || 0, 10) || 0,
          alt_label: isAlt2 ? 'Alt2' : 'Alt1'
        };
      });
      var subtypeBreakdown = (group.subtype_breakdown || []).map(function(sub){
        return {
          diet_type_id: String(sub.diet_type_id || ''),
          diet_type_name: String(sub.diet_type_name || ''),
          count: parseInt(sub.count || 0, 10) || 0
        };
      });
      var deptBreakdown = (group.department_breakdown || []).map(function(dep){
        var isAlt2 = (meal === 'lunch' && alt2Set.has(String(dep.department_id || '')));
        return {
          department_id: String(dep.department_id || ''),
          department_name: String(dep.department_name || ''),
          total: parseInt(dep.total || 0, 10) || 0,
          alt_label: isAlt2 ? 'Alt2' : 'Alt1',
          subtype_counts: (dep.subtype_counts || []).map(function(sub){
            return {
              diet_type_name: String(sub.diet_type_name || ''),
              count: parseInt(sub.count || 0, 10) || 0
            };
          })
        };
      });
      return {
        diet_type_id: String(group.diet_type_id || ''),
        production_group_name: String(group.production_group_name || ''),
        diet_type_name: String(group.diet_type_name || ''),
        total: parseInt(group.total || 0, 10) || 0,
        subtype_breakdown: subtypeBreakdown,
        department_breakdown: deptBreakdown,
        rows: rows
      };
    });

    var selectedAddon = null;
    for(var sa=0; sa<serviceAddonsSummary.length; sa++){
      var cand = serviceAddonsSummary[sa] || {};
      if(String(cand.addon_id || '') === String(selectedServiceAddonId || '')){
        selectedAddon = cand;
        break;
      }
    }
    var addonPayload = null;
    if(selectedAddon){
      addonPayload = {
        addon_id: String(selectedAddon.addon_id || ''),
        addon_name: String(selectedAddon.addon_name || ''),
        total_count: parseInt(selectedAddon.total_count || 0, 10) || 0,
        departments: (selectedAddon.departments || []).map(function(dep){
          return {
            department_id: String(dep.department_id || ''),
            department_name: String(dep.department_name || ''),
            count: parseInt(dep.count || 0, 10) || 0,
            note: String(dep.note || '')
          };
        })
      };
    }

    return {
      date: dateIso,
      meal_type: meal,
      payload: {
        mode: mode,
        year: year,
        week: week,
        day_label: dayLabel,
        date_iso: dateIso,
        meal: meal,
        meal_label: mealLabel,
        dishes: {
          alt1: dishes.alt1 || '',
          alt2: dishes.alt2 || ''
        },
        normal: {
          rows: normalRows,
          alt1_total: alt1Total,
          alt2_total: alt2Total,
          total: alt1Total + alt2Total
        },
        special: {
          selected_diet_ids: Array.from(selectedChipsSpecial),
          worklist: specialWorklist
        },
        service_addon: addonPayload
      }
    };
  }

  function initProductionListModal(){
    var openBtn = qs('.js-open-production-list-modal');
    var modal = qs('#production-list-modal');
    var closeBtn = qs('.js-close-production-list-modal');
    var saveBtn = qs('.js-save-production-list');
    var status = qs('#production-list-status');
    var metaMode = qs('#production-list-meta-mode');
    var metaMeal = qs('#production-list-meta-meal');
    var metaDay = qs('#production-list-meta-day');
    var metaWeek = qs('#production-list-meta-week');
    if(!openBtn || !modal || !saveBtn){ return; }

    function setStatus(msg){ if(status){ status.textContent = msg || ''; } }
    function setMeta(el, val){ if(el){ el.textContent = String(val || '-'); } }
    function refreshMeta(){
      var ctx = qs('#kp-context');
      var qsParams = new URLSearchParams(window.location.search || '');
      var modeRaw = String(qsParams.get('mode') || 'special').toLowerCase();
      var modeLabel = modeRaw === 'normal' ? 'Normal' : 'Specialkost';
      var mealRaw = String((ctx && ctx.getAttribute('data-meal')) || '');
      var mealLabel = mealRaw === 'lunch' ? 'Lunch' : (mealRaw === 'dinner' ? 'Kvällsmat' : (mealRaw === 'dessert' ? 'Dessert' : '-'));
      var dayLabel = String((ctx && ctx.getAttribute('data-day-label')) || '').trim() || '-';
      var weekVal = String((ctx && ctx.getAttribute('data-week')) || '').trim();
      setMeta(metaMode, modeLabel);
      setMeta(metaMeal, mealLabel);
      setMeta(metaDay, dayLabel);
      setMeta(metaWeek, weekVal ? ('Vecka ' + weekVal) : '-');
    }
    function openModal(){ refreshMeta(); modal.classList.add('is-open'); setStatus(''); }
    function closeModal(){ modal.classList.remove('is-open'); }

    openBtn.addEventListener('click', function(){
      if(openBtn.disabled){ return; }
      openModal();
    });
    if(closeBtn){ closeBtn.addEventListener('click', closeModal); }
    modal.addEventListener('click', function(ev){ if(ev.target === modal){ closeModal(); } });

    saveBtn.addEventListener('click', function(){
      var ctx = qs('#kp-context');
      if(!ctx){ return; }
      var siteId = String(ctx.getAttribute('data-site-id') || '').trim();
      var built = buildProductionListPayload();
      if(!siteId || !built || !built.date){
        setStatus('Välj dag och måltid (lunch/kvällsmat) först.');
        return;
      }
      saveBtn.disabled = true;
      setStatus('Sparar...');
      var csrf = getCsrfToken();
      fetch('/api/production-lists', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': csrf,
          'X-CSRF-Token': csrf
        },
        credentials: 'same-origin',
        body: JSON.stringify({
          site_id: siteId,
          date: built.date,
          meal_type: built.meal_type,
          payload: built.payload
        })
      })
      .then(function(r){
        return r.json().then(function(data){
          if(!r.ok){
            var msg = (data && data.message) ? String(data.message) : ('save_failed:' + r.status);
            throw new Error(msg);
          }
          return data;
        }).catch(function(){
          if(!r.ok){ throw new Error('save_failed:' + r.status); }
          return {};
        });
      })
      .then(function(resp){
        var item = (resp && resp.item) || {};
        setStatus('Sparad. Omdirigerar...');
        var target = '/ui/production-lists/' + encodeURIComponent(String(item.id || '')) + '?site_id=' + encodeURIComponent(siteId);
        window.location.href = target;
      })
      .catch(function(err){
        var msg = (err && err.message) ? String(err.message) : 'Kunde inte spara produktionslistan. Försok igen.';
        setStatus(msg);
      })
      .finally(function(){
        saveBtn.disabled = false;
      });
    });
  }

  function init(){
    var qsParams = new URLSearchParams(window.location.search);
    var initialMode = (qsParams.get('mode') || 'special').toLowerCase();
    setPrintMode(initialMode === 'normal' ? 'normal' : 'special');
    initModeRadios();
    initMenuAndTitle();
    initPrintButton();
    initDeptSummaryModal();
    initProductionListModal();
    initPlanTabs();
    // Parse CSP-safe data attributes for alt groups and per-department diet counts
    var ctxData = qs('#kp-context');
    if(ctxData){
      try {
        var isDev = String(ctxData.getAttribute('data-dev-mode') || '') === '1';
        var currentDish = String(ctxData.getAttribute('data-current-dish-label') || '').trim();
        var selectedMeal = String(ctxData.getAttribute('data-meal') || '').trim();
        if(isDev && selectedMeal && !currentDish){
          console.warn('[kitchen_planering_v1] missing current dish label', {
            meal: selectedMeal,
            site_id: ctxData.getAttribute('data-site-id') || '',
            year: ctxData.getAttribute('data-year') || '',
            week: ctxData.getAttribute('data-week') || '',
            day_index: ctxData.getAttribute('data-day-index') || ''
          });
        }
      } catch(e){ /* ignore */ }
      try {
        var ag = ctxData.getAttribute('data-alt-groups');
        if(ag){ altGroups = JSON.parse(ag); }
      } catch(e){ altGroups = { alt1_dept_ids: [], alt2_dept_ids: [] }; }
      try {
        var dc = ctxData.getAttribute('data-diet-counts-by-dept');
        if(dc){ dietCountsByDept = JSON.parse(dc); }
      } catch(e){ dietCountsByDept = {}; }
      try {
        var sas = ctxData.getAttribute('data-service-addons-summary');
        if(sas){ serviceAddonsSummary = JSON.parse(sas); }
      } catch(e){ serviceAddonsSummary = []; }
      selectedServiceAddonId = String(ctxData.getAttribute('data-selected-service-addon-id') || '');
    }
    if(initialMode === 'normal'){
      var normalView = qs('.normalkost-view');
      if(normalView){
        Array.prototype.slice.call(normalView.querySelectorAll('.js-normal-chip.active')).forEach(function(btn){
          var alt = Number(btn.getAttribute('data-alt'));
          var dietId = btn.getAttribute('data-diet-id') || btn.getAttribute('data-diet-type-id');
          if(!alt || !dietId) return;
          var set = selectedChipsNormal[alt] || (selectedChipsNormal[alt] = new Set());
          set.add(dietId);
        });
      }
    } else {
      clearNormalChipState();
    }
    // Initial totals
    renderAllTotals();
    // Initialize special chips and bulk-mark buttons only in special mode
    if(initialMode === 'special'){
      initSpecialChips();
      initBulkMarkButtons();
    } else {
      clearSpecialChipState();
    }
    renderPrintContainer();
    updateModalPrintHeader();
    var state = loadPlaneringState();
    if(state && Array.isArray(state.selected_diets)){
      selectedChipsSpecial = new Set(state.selected_diets.map(String));
      qsa('.js-special-chip').forEach(function(btn){
        var id = String(btn.getAttribute('data-diet-id') || '');
        var active = selectedChipsSpecial.has(id);
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
    if(initialMode === 'special'){
      renderSpecialSelectedList();
    }
    // Event delegation for diet-chip toggling (normal mode UI only)
    if(!isNormalChipHandlerBound){
      document.addEventListener('click', function(e){
        var btn = e.target && e.target.closest && e.target.closest('.js-normal-chip');
        if(!btn) return;
        if(!btn.closest('.normalkost-view')) return;
        var alt = Number(btn.getAttribute('data-alt') || '1');
        var dietId = btn.getAttribute('data-diet-id') || btn.getAttribute('data-diet-type-id');
        if(!alt || !dietId) return;
        var set = selectedChipsNormal[alt] || (selectedChipsNormal[alt] = new Set());
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
      isNormalChipHandlerBound = true;
    }
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
