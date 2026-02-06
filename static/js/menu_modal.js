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

  function fetchWeekMenu(year, week){
    if(cachedMenu && (!year || !week)) return Promise.resolve(cachedMenu);
    var yw = { year: year, week: week };
    if(!yw.year || !yw.week){ yw = getYearWeek(); }
    var url = '/menu/week' + (yw.year && yw.week ? ('?year=' + encodeURIComponent(yw.year) + '&week=' + encodeURIComponent(yw.week)) : '');
    return fetch(url, { headers: { 'Accept': 'application/json' } })
      .then(function(res){ if(!res.ok) throw new Error('status ' + res.status); return res.json(); })
      .then(function(data){
        var days = (data && data.days) || ((data && data.menu && data.menu.days) || {});
        cachedMenu = Object.assign({}, data, { days: days });
        return cachedMenu;
      });
  }

  function escapeHtml(s){ s = String(s || ''); return s.replace(/[&<>"']/g, function(c){ return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'})[c]; }); }

  function canonKey(k){ var s = String(k || '').trim().toLowerCase(); if(s==='alt 1'||s==='alt_1') s='alt1'; if(s==='alt 2'||s==='alt_2') s='alt2'; if(s==='kvall'||s==='kväll'||s==='dinner') s='main'; return s; }
  function prettyLabel(c){ switch(c){ case 'alt1': return 'Alt1'; case 'alt2': return 'Alt2'; case 'dessert': return 'Dessert'; case 'main': return 'Kvällsmat'; default: return c.charAt(0).toUpperCase()+c.slice(1); } }
  function valueName(v){ if(!v) return ''; if(typeof v==='string') return v; return v.name || v.dish_name || ''; }
  function dedupeItems(obj, prefer){ var best={}; (prefer||[]).forEach(function(k){ var v=obj&&obj[k]; if(v==null) return; var c=canonKey(k); if(best[c]) return; best[c]={label:prettyLabel(c),val:v}; }); Object.keys(obj||{}).forEach(function(k){ var v=obj[k]; if(v==null) return; var c=canonKey(k); if(best[c]) return; best[c]={label:prettyLabel(c),val:v}; }); return best; }

  function dayKeyFromIndex(i){ var m=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']; i=parseInt(i,10); if(isNaN(i)||i<0||i>6) return null; return m[i]; }

  function dayLabelSwe(dayKey){ var k=String(dayKey||'').trim(); var map={ Mon:'Måndag', Tue:'Tisdag', Wed:'Onsdag', Thu:'Torsdag', Fri:'Fredag', Sat:'Lördag', Sun:'Söndag' }; return map[k] || k; }

  function normalizeDayKey(k){ var s=String(k||'').trim().toLowerCase(); var map={ mon:'mon', tue:'tue', wed:'wed', thu:'thu', fri:'fri', sat:'sat', sun:'sun', monday:'mon', tuesday:'tue', wednesday:'wed', thursday:'thu', friday:'fri', saturday:'sat', sunday:'sun', 'mån':'mon','tis':'tue','ons':'wed','tor':'thu','fre':'fri','lör':'sat','sön':'sun' }; return map[s]||s; }
  function findDayObject(days, selectedKey){ var exact=String(selectedKey||'').trim(); var canon=normalizeDayKey(exact); var lowerMap={}; Object.keys(days||{}).forEach(function(k){ lowerMap[String(k).trim().toLowerCase()]=k; }); var cap=canon.charAt(0).toUpperCase()+canon.slice(1); var fullEngMap={ mon:'monday',tue:'tuesday',wed:'wednesday',thu:'thursday',fri:'friday',sat:'saturday',sun:'sunday' }; var fullEng=fullEngMap[canon]; var sweAbbrevMap={ mon:'mån',tue:'tis',wed:'ons',thu:'tor',fri:'fre',sat:'lör',sun:'sön' }; var sweAbbrev=sweAbbrevMap[canon]; var sweFullMap={ mon:'måndag',tue:'tisdag',wed:'onsdag',thu:'torsdag',fri:'fredag',sat:'lördag',sun:'söndag' }; var sweFull=sweFullMap[canon]; var candidates=[exact,canon,cap,fullEng,sweAbbrev,sweFull].filter(Boolean); var hitKey=null; for(var i=0;i<candidates.length;i++){ var low=String(candidates[i]).trim().toLowerCase(); if(lowerMap.hasOwnProperty(low)){ hitKey=lowerMap[low]; break; } } return { key: hitKey, obj: hitKey ? days[hitKey] : undefined };
  }

  function ensureRefs(){ if(!modal){ modal=document.getElementById('menuModal'); } if(!modalBody){ modalBody=document.getElementById('menuModalBody'); } }
  function showModal(html){
    ensureRefs();
    if(!modal||!modalBody) return;
    modalBody.innerHTML=html;
    modal.hidden=false;
    modal.classList.add('is-open');
    document.body.classList.add('menu-modal-open');
  }
  function hideModal(){
    ensureRefs();
    if(!modal) return;
    modal.hidden=true;
    modal.classList.remove('is-open');
    document.body.classList.remove('menu-modal-open');
  }

  function renderDay(menuJson, dayKey){ try{ var days=(menuJson&&menuJson.days)||((menuJson&&menuJson.menu&&menuJson.menu.days)||{}); var found=findDayObject(days, dayKey); var day=found.obj||{}; var lunch=day['Lunch']||day['lunch']||{}; var dinner=day['Dinner']||day['dinner']||{}; function section(title,obj,prefer){ if(!obj||Object.keys(obj).length===0) return ''; var best=dedupeItems(obj,prefer); var order=['alt1','alt2','dessert','main']; var parts=[]; order.forEach(function(c){ var it=best[c]; if(!it) return; var lbl=it.label; var name=valueName(it.val); var pillClass='menu-modal__pill'+(c==='alt2'?' alt2':''); parts.push('<div class="menu-modal__row"><span class="'+pillClass+'">'+escapeHtml(lbl)+'</span><span class="menu-modal__text">'+escapeHtml(name)+'</span></div>'); }); if(parts.length===0) return ''; return '<h4 class="menu-modal__section-title">'+title+'</h4>'+parts.join(''); }
      var html='<div class="menu-modal__inner">'
        + '<div class="menu-modal__day">'+escapeHtml(dayLabelSwe(found.key||dayKey))+'</div>'
        + (section('Lunch', lunch, ['Alt1','Alt2','Dessert','alt1','alt2','dessert']) || '<div>Ingen lunch registrerad</div>')
        + (function(){ var best=dedupeItems(dinner,['Main','Dinner','Kväll','main','dinner','kvall','kväll','Alt1','alt1','Alt2','alt2']); var name=''; if(best.main){ name=valueName(best.main.val); } else if(best.alt1){ name=valueName(best.alt1.val); } else if(best.alt2){ name=valueName(best.alt2.val); } else { var anyKey=Object.keys(best)[0]; if(anyKey){ name=valueName(best[anyKey].val); } } return name ? ('<div class="menu-modal__row"><span class="menu-modal__pill">Kvällsmat</span><span class="menu-modal__text">'+escapeHtml(name)+'</span></div>') : ''; })()
        + '</div>'; return html; }catch(e){ return '<div>Kunde inte läsa meny</div>'; } }

  function openMenuModal(opts){ opts=opts||{}; var year=opts.year, week=opts.week; var di=opts.dayIndex; var dayKey=opts.dayKey || dayKeyFromIndex(di); fetchWeekMenu(year, week).then(function(menu){ showModal(renderDay(menu, dayKey)); }).catch(function(){ showModal('<div>Kunde inte läsa meny</div>'); }); }
  window.openMenuModal=openMenuModal;

  document.addEventListener('keydown', function(ev){ if(ev.key==='Escape'){ hideModal(); }});
  var OPEN_SELECTORS=[
    '[data-action="open-menu-modal"]',
    '#openMenuModal',
    '.js-open-menu-modal'
  ].join(',');
  document.addEventListener('click', function(ev){
    var el=ev.target;
    if(!el) return;
    var closeBtn=el.closest ? el.closest('.js-menu-modal-close') : null;
    if(closeBtn){ ev.preventDefault(); hideModal(); return; }
    var backdrop=el.closest ? el.closest('.js-menu-modal-backdrop') : null;
    if(backdrop && el===backdrop){ hideModal(); return; }
    var btn=el.closest ? el.closest(OPEN_SELECTORS) : null;
    if(!btn) return;
    if(btn.disabled) return;
    ev.preventDefault();
    var di=btn.getAttribute('data-day-index');
    var year=btn.getAttribute('data-year');
    var week=btn.getAttribute('data-week');
    try{ if(window.location && (window.location.hostname==='localhost' || window.location.hostname==='127.0.0.1')){ console.info('menu modal open', { dayIndex: di, year: year, week: week }); } }catch(e){}
    openMenuModal({ dayIndex: di, year: year, week: week });
  });
})();
