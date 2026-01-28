(function(){
  'use strict';

  var cachedMenu = null;
  var modal = null;
  var modalBody = null;

  function getYearWeek(){
    try{
      var p = new URLSearchParams(window.location.search);
      var year = p.get('year');
      var week = p.get('week');
      return { year: year, week: week };
    }catch(e){ return { year: null, week: null }; }
  }

  function fetchWeekMenu(){
    if(cachedMenu) return Promise.resolve(cachedMenu);
    var yw = getYearWeek();
    var url = '/menu/week' + (yw.year && yw.week ? ('?year=' + encodeURIComponent(yw.year) + '&week=' + encodeURIComponent(yw.week)) : '');
    return fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function(res){
        if(!res.ok) throw new Error('status ' + res.status);
        return res.json();
      })
      .then(function(data){
        // Derive days regardless of response shape
        var days = (data && data.days) || ((data && data.menu && data.menu.days) || {});
        // Debug logs (shape insight)
        try {
          console.debug("MENU_WEEK_TOP_KEYS", Object.keys(data || {}));
          console.debug("MENU_WEEK_MENU_KEYS", Object.keys((data && data.menu) || {}));
          console.debug("MENU_WEEK_DAYS_KEYS", Object.keys(days || {}));
        } catch(e){}
        // Cache augmented object with canonical days field
        cachedMenu = Object.assign({}, data, { days: days });
        return cachedMenu;
      });
  }

  function escapeHtml(s){
    s = String(s || '');
    return s.replace(/[&<>"']/g, function(c){ return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'})[c]; });
  }

  function dayLabelSwe(dayKey){
    var k = String(dayKey || '').trim();
    var m = {
      Mon:'Måndag', Tue:'Tisdag', Wed:'Onsdag', Thu:'Torsdag', Fri:'Fredag', Sat:'Lördag', Sun:'Söndag',
      mon:'Måndag', tue:'Tisdag', wed:'Onsdag', thu:'Torsdag', fri:'Fredag', sat:'Lördag', sun:'Söndag',
      monday:'Måndag', tuesday:'Tisdag', wednesday:'Onsdag', thursday:'Torsdag', friday:'Fredag', saturday:'Lördag', sunday:'Söndag',
      'mån':'Måndag', 'tis':'Tisdag', 'ons':'Onsdag', 'tor':'Torsdag', 'fre':'Fredag', 'lör':'Lördag', 'sön':'Söndag'
    };
    return m[k] || m[k.toLowerCase()] || k;
  }

  function canonKey(k){
    var s = String(k || '').trim().toLowerCase();
    if(s === 'alt 1' || s === 'alt_1') s = 'alt1';
    if(s === 'alt 2' || s === 'alt_2') s = 'alt2';
    if(s === 'kvall' || s === 'kväll' || s === 'dinner') s = 'main';
    return s;
  }

  function prettyLabel(canon){
    switch(canon){
      case 'alt1': return 'Alt1';
      case 'alt2': return 'Alt2';
      case 'dessert': return 'Dessert';
      case 'main': return 'Kvällsmat';
      default: return canon.charAt(0).toUpperCase() + canon.slice(1);
    }
  }

  function valueName(v){
    if(!v) return '';
    if(typeof v === 'string') return v;
    return v.name || v.dish_name || '';
  }

  function dedupeItems(obj, preferKeys){
    var best = {};
    (preferKeys || []).forEach(function(k){
      var v = obj && obj[k];
      if(v == null) return;
      var c = canonKey(k);
      if(best[c]) return;
      best[c] = { label: prettyLabel(c), val: v };
    });
    Object.keys(obj || {}).forEach(function(k){
      var v = obj[k];
      if(v == null) return;
      var c = canonKey(k);
      if(best[c]) return;
      best[c] = { label: prettyLabel(c), val: v };
    });
    return best;
  }

  // Canonicalize day keys: mon|tue|wed|thu|fri|sat|sun
  function normalizeDayKey(k){
    var s = String(k || '').trim().toLowerCase();
    var map = {
      // short english
      mon:'mon', tue:'tue', wed:'wed', thu:'thu', fri:'fri', sat:'sat', sun:'sun',
      // full english
      monday:'mon', tuesday:'tue', wednesday:'wed', thursday:'thu', friday:'fri', saturday:'sat', sunday:'sun',
      // swedish abbrev
      'mån':'mon', 'tis':'tue', 'ons':'wed', 'tor':'thu', 'fre':'fri', 'lör':'sat', 'sön':'sun'
    };
    return map[s] || s;
  }

  function findDayObject(days, selectedKey){
    var exact = String(selectedKey || '').trim();
    var canon = normalizeDayKey(exact);
    // Build case-insensitive key map
    var lowerMap = {};
    Object.keys(days || {}).forEach(function(k){ lowerMap[String(k).trim().toLowerCase()] = k; });
    // Candidate keys (in order): exact, canon, Capital short, full english, swedish abbrev, swedish full
    var cap = canon.charAt(0).toUpperCase() + canon.slice(1); // Mon
    var fullEngMap = { mon:'monday', tue:'tuesday', wed:'wednesday', thu:'thursday', fri:'friday', sat:'saturday', sun:'sunday' };
    var fullEng = fullEngMap[canon];
    var sweAbbrevMap = { mon:'mån', tue:'tis', wed:'ons', thu:'tor', fri:'fre', sat:'lör', sun:'sön' };
    var sweAbbrev = sweAbbrevMap[canon];
    var sweFullMap = { mon:'måndag', tue:'tisdag', wed:'onsdag', thu:'torsdag', fri:'fredag', sat:'lördag', sun:'söndag' };
    var sweFull = sweFullMap[canon];
    var candidates = [ exact, canon, cap, fullEng, sweAbbrev, sweFull ].filter(function(x){ return !!x; });
    var hitKey = null;
    for(var i=0;i<candidates.length;i++){
      var low = String(candidates[i]).trim().toLowerCase();
      if(lowerMap.hasOwnProperty(low)){ hitKey = lowerMap[low]; break; }
    }
    // Debug: selected, canonical, and hit
    try{ console.debug('DAY_KEY', { selected: exact, canonical: canon, hit: hitKey }); }catch(e){}
    return { key: hitKey, obj: hitKey ? days[hitKey] : undefined };
  }

  function renderDay(menuJson, dayKey){
    try{
      // Use unified days field if present; else fallback to menu.days
      var days = (menuJson && menuJson.days) || ((menuJson && menuJson.menu && menuJson.menu.days) || {});
      var found = findDayObject(days, dayKey);
      var day = found.obj || {};
      var lunch = day['Lunch'] || day['lunch'] || {};
      var dinner = day['Dinner'] || day['dinner'] || {};
      function section(title, obj, preferKeys){
        if(!obj || Object.keys(obj).length === 0) return '';
        var best = dedupeItems(obj, preferKeys);
        var order = ['alt1','alt2','dessert','main'];
        var parts = [];
        order.forEach(function(c){
          var it = best[c];
          if(!it) return;
          var lbl = it.label;
          var name = valueName(it.val);
          var pillClass = 'menu-modal__pill' + (c === 'alt2' ? ' alt2' : '');
          parts.push('<div class="menu-modal__row"><span class="' + pillClass + '">' + escapeHtml(lbl) + '</span><span class="menu-modal__text">' + escapeHtml(name) + '</span></div>');
        });
        if(parts.length === 0) return '';
        return '<h4 class="menu-modal__section-title">' + title + '</h4>' + parts.join('');
      }
      var html = '<div class="menu-modal__inner">'
        + '<div class="menu-modal__day">' + escapeHtml(dayLabelSwe(found.key || dayKey)) + '</div>'
        + (section('Lunch', lunch, ['Alt1','Alt2','Dessert','alt1','alt2','dessert']) || '<div>Ingen lunch registrerad</div>')
        + (function(){
            var best = dedupeItems(dinner, ['Main','Dinner','Kväll','main','dinner','kvall','kväll','Alt1','alt1','Alt2','alt2']);
            var name = '';
            if(best.main){ name = valueName(best.main.val); }
            else if(best.alt1){ name = valueName(best.alt1.val); }
            else if(best.alt2){ name = valueName(best.alt2.val); }
            else {
              var anyKey = Object.keys(best)[0];
              if(anyKey){ name = valueName(best[anyKey].val); }
            }
            return name ? ('<div class="menu-modal__row"><span class="menu-modal__pill">Kvällsmat</span><span class="menu-modal__text">' + escapeHtml(name) + '</span></div>') : '';
          })()
        + '</div>';
      return html;
    }catch(e){ return '<div>Kunde inte läsa meny</div>'; }
  }

  function ensureModal(){
    if(!modal){
      var existing = document.getElementById('menuModal');
      if(existing){
        if(existing.parentElement !== document.body){ document.body.appendChild(existing); }
        modal = existing;
      } else {
        modal = document.createElement('div');
        modal.id = 'menuModal';
        modal.className = 'menu-modal';
        document.body.appendChild(modal);
      }
    }
    if(!modalBody){
      var content = document.createElement('div');
      content.className = 'menu-modal__content';
      var header = document.createElement('div');
      header.className = 'menu-modal__header';
      var h = document.createElement('div');
      h.textContent = 'Meny';
      h.className = 'menu-modal__header-title';
      var actions = document.createElement('div');
      actions.className = 'menu-modal__header-actions';
      var closeBtn = document.createElement('button');
      closeBtn.type = 'button';
      closeBtn.textContent = '✕';
      closeBtn.setAttribute('aria-label','Stäng');
      closeBtn.className = 'menu-modal__close';
      closeBtn.id = 'menuModalClose';
      actions.appendChild(closeBtn);
      header.appendChild(h);
      header.appendChild(actions);
      modalBody = document.createElement('div');
      modalBody.id = 'menuModalBody';
      modalBody.className = 'menu-modal__body';
      content.appendChild(header);
      content.appendChild(modalBody);
      modal.appendChild(content);
    }
  }

  function showModal(html){ ensureModal(); modalBody.innerHTML = html; modal.classList.add('is-open'); }
  function hideModal(){ if(modal){ modal.classList.remove('is-open'); } }

  document.addEventListener('keydown', function(ev){ if(ev.key === 'Escape'){ hideModal(); }});

  document.addEventListener('click', function(ev){
    var el = ev.target;
    if(el && el.classList && el.classList.contains('menu-icon')){
      var dayKey = el.getAttribute('data-day');
      if(!dayKey) return;
      fetchWeekMenu().then(function(menu){ showModal(renderDay(menu, dayKey)); }).catch(function(){});
      ev.stopPropagation();
      return;
    }
    if(el && el.id === 'menuModal' && el.classList.contains('is-open')){ hideModal(); return; }
    if(el && el.id === 'menuModalClose'){ hideModal(); return; }
  });
})();
