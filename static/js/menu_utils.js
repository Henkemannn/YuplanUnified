(function(){
  'use strict';

  function get(obj, path){
    try {
      var parts = String(path||'').split('.');
      var cur = obj;
      for(var i=0;i<parts.length;i++){
        if(cur == null) return undefined;
        cur = cur[parts[i]];
      }
      return cur;
    } catch(e){ return undefined; }
  }

  function textFrom(val){
    if(val == null) return '';
    if(typeof val === 'string') return val;
    if(typeof val === 'number') return String(val);
    if(typeof val === 'object'){
      var candidates = ['main','dish_name','name','title','text'];
      for(var i=0;i<candidates.length;i++){
        var v = val[candidates[i]];
        if(typeof v === 'string' && v.trim().length > 0) return v;
      }
    }
    return '';
  }

  function normalizeDayKey(k){
    var s = String(k||'').trim().toLowerCase();
    var map = {
      mon:'mon', tue:'tue', wed:'wed', thu:'thu', fri:'fri', sat:'sat', sun:'sun',
      monday:'mon', tuesday:'tue', wednesday:'wed', thursday:'thu', friday:'fri', saturday:'sat', sunday:'sun',
      'mån':'mon','tis':'tue','ons':'wed','tor':'thu','fre':'fri','lör':'sat','sön':'sun'
    };
    return map[s] || s;
  }

  function dayKeyFromIndex(i){ var m=['Mon','Tue','Wed','Thu','Fri','Sat','Sun']; i=parseInt(i,10); if(isNaN(i)||i<0||i>6) return null; return m[i]; }

  function findDay(menuData, daySpec){
    var data = (menuData && menuData.menu) || menuData || {};
    var days = data.days || {};
    var selectedKey = typeof daySpec === 'number' ? dayKeyFromIndex(daySpec) : daySpec;
    var exact = String(selectedKey||'').trim();
    var canon = normalizeDayKey(exact);
    var lowerMap = {};
    Object.keys(days||{}).forEach(function(k){ lowerMap[String(k).trim().toLowerCase()] = k; });
    var cap = canon.charAt(0).toUpperCase() + canon.slice(1);
    var fullEngMap = { mon:'monday',tue:'tuesday',wed:'wednesday',thu:'thursday',fri:'friday',sat:'saturday',sun:'sunday' };
    var fullEng = fullEngMap[canon];
    var sweAbbrevMap = { mon:'mån',tue:'tis',wed:'ons',thu:'tor',fri:'fre',sat:'lör',sun:'sön' };
    var sweAbbrev = sweAbbrevMap[canon];
    var sweFullMap = { mon:'måndag',tue:'tisdag',wed:'onsdag',thu:'torsdag',fri:'fredag',sat:'lördag',sun:'söndag' };
    var sweFull = sweFullMap[canon];
    var candidates = [exact, canon, cap, fullEng, sweAbbrev, sweFull].filter(Boolean);
    var hitKey = null;
    for(var i=0;i<candidates.length;i++){
      var low = String(candidates[i]).trim().toLowerCase();
      if(lowerMap.hasOwnProperty(low)){ hitKey = lowerMap[low]; break; }
    }
    return { key: hitKey || exact, obj: hitKey ? days[hitKey] : undefined };
  }

  function pickTitles(menuData, daySpec, meal){
    var found = findDay(menuData, daySpec);
    var day = found.obj || {};
    var alt1 = '';
    var alt2 = '';
    var src1 = undefined;
    var src2 = undefined;
    var m = String(meal||'').toLowerCase();
    if(m === 'lunch'){
      var lunch = day['Lunch'] || day['lunch'] || {};
      var main = lunch.main !== undefined ? lunch.main : get(lunch, 'Main');
      var a1 = lunch.alt1 !== undefined ? lunch.alt1 : get(lunch, 'Alt1');
      var a2 = lunch.alt2 !== undefined ? lunch.alt2 : get(lunch, 'Alt2');
      var name = (lunch.name !== undefined ? lunch.name : lunch.dish_name !== undefined ? lunch.dish_name : undefined);
      if(textFrom(main)) { alt1 = textFrom(main); src1 = 'Lunch.main'; }
      else if(textFrom(a1)) { alt1 = textFrom(a1); src1 = 'Lunch.alt1'; }
      else if(textFrom(name)) { alt1 = textFrom(name); src1 = lunch.dish_name !== undefined ? 'Lunch.dish_name' : 'Lunch.name'; }
      alt2 = textFrom(a2); src2 = alt2 ? 'Lunch.alt2' : undefined;
    } else if(m === 'dinner'){
      var dinner = day['Dinner'] || day['dinner'] || {};
      var dmain = dinner.main !== undefined ? dinner.main : get(dinner, 'Main');
      var dname = (dinner.name !== undefined ? dinner.name : dinner.dish_name !== undefined ? dinner.dish_name : undefined);
      if(textFrom(dmain)) { alt1 = textFrom(dmain); src1 = 'Dinner.main'; }
      else if(textFrom(dname)) { alt1 = textFrom(dname); src1 = dinner.dish_name !== undefined ? 'Dinner.dish_name' : 'Dinner.name'; }
      alt2 = ''; src2 = undefined;
    } else {
      var dessert = day['Dessert'] || day['dessert'] || {};
      var smain = dessert.main !== undefined ? dessert.main : get(dessert, 'Main');
      var sname = (dessert.name !== undefined ? dessert.name : dessert.dish_name !== undefined ? dessert.dish_name : undefined);
      if(textFrom(smain)) { alt1 = textFrom(smain); src1 = 'Dessert.main'; }
      else if(textFrom(sname)) { alt1 = textFrom(sname); src1 = dessert.dish_name !== undefined ? 'Dessert.dish_name' : 'Dessert.name'; }
      alt2 = ''; src2 = undefined;
    }
    return { alt1Text: alt1 || '', alt2Text: alt2 || '', source: { alt1: src1, alt2: src2 }, dayKey: found.key };
  }

  window.MenuUtils = {
    pickTitles: pickTitles
  };
})();