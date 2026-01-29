(function(){
  function abbrFor(dayIdx){
    switch(dayIdx){
      case 1: return "Mån";
      case 2: return "Tis";
      case 3: return "Ons";
      case 4: return "Tors";
      case 5: return "Fre";
      case 6: return "Lör";
      case 7: return "Sön";
      default: return "Mån";
    }
  }
  async function getEtag(departmentId, year, week){
    const url = `/api/weekview/etag?department_id=${encodeURIComponent(departmentId)}&year=${year}&week=${week}`;
    const resp = await fetch(url, { headers: {"X-User-Role":"cook"} });
    if(!resp.ok){ return null; }
    const j = await resp.json();
    return j.etag || null;
  }
  async function toggleMark(btn){
    const depId = btn.dataset.departmentId;
    const dtId = btn.dataset.dietTypeId;
    const year = parseInt(btn.dataset.year, 10);
    const week = parseInt(btn.dataset.week, 10);
    const dayIdx = parseInt(btn.dataset.dayIndex, 10);
    const meal = btn.dataset.meal || "lunch";
    const marked = !btn.classList.contains('is-done');
    const etag = await getEtag(depId, year, week);
    if(!etag){ return; }
    const payload = {
      year: year,
      week: week,
      department_id: depId,
      diet_type_id: dtId,
      meal: meal,
      weekday_abbr: abbrFor(dayIdx),
      marked: marked
    };
    const resp = await fetch('/api/weekview/specialdiets/mark',{
      method:'POST',
      headers:{
        'Content-Type':'application/json',
        'If-Match': etag,
        'X-User-Role':'cook'
      },
      body: JSON.stringify(payload)
    });
    if(resp.status === 200){
      if(marked){ btn.classList.add('is-done'); } else { btn.classList.remove('is-done'); }
      // Reflect server truth deterministically
      window.location.reload();
    } else if(resp.status === 412){
      // ETag mismatch: re-fetch and retry once
      const etag2 = await getEtag(depId, year, week);
      if(!etag2) return;
      const resp2 = await fetch('/api/weekview/specialdiets/mark',{
        method:'POST',
        headers:{
          'Content-Type':'application/json',
          'If-Match': etag2,
          'X-User-Role':'cook'
        },
        body: JSON.stringify(payload)
      });
      if(resp2.status === 200){
        if(marked){ btn.classList.add('is-done'); } else { btn.classList.remove('is-done'); }
        window.location.reload();
      }
    }
  }
  document.addEventListener('DOMContentLoaded', function(){
    document.querySelectorAll('.kostcell-btn').forEach(function(btn){
      btn.addEventListener('click', function(ev){ toggleMark(btn); });
    });
    const p = document.getElementById('printBtn');
    if(p){ p.addEventListener('click', function(){ window.print(); }); }
  });
})();
