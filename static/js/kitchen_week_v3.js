(function(){
  class WeekviewRequestError extends Error {
    constructor(status, phase, network = false){
      super(network ? 'network_error' : `${phase}_${status}`);
      this.status = status;
      this.phase = phase;
      this.network = network;
    }
  }

  function getCookie(name){
    try {
      const cookie = document.cookie
        .split('; ')
        .find(row => row.startsWith(name + '='));
      return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
    } catch(e){
      return '';
    }
  }

  function getCsrfToken(){
    const meta = document.querySelector('meta[name="csrf-token"]');
    if(meta && meta.getAttribute('content')){
      return meta.getAttribute('content');
    }
    return getCookie('csrf_token');
  }

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

  function resolveSiteId(){
    const qs = new URLSearchParams(window.location.search);
    const querySiteId = qs.get('site_id');
    if(querySiteId){ return querySiteId; }
    if(window.VM && window.VM.site_id){ return window.VM.site_id; }
    const byDataAttr = document.querySelector('[data-site-id]');
    if(byDataAttr && byDataAttr.getAttribute('data-site-id')){ return byDataAttr.getAttribute('data-site-id'); }
    const shell = document.querySelector('[data-page-site-id]');
    if(shell && shell.getAttribute('data-page-site-id')){ return shell.getAttribute('data-page-site-id'); }
    return null;
  }

  function setStatus(message, state){
    const status = document.querySelector('[data-weekview-status]');
    if(!status){ return; }
    status.textContent = message;
    if(state){ status.dataset.state = state; }
    else { delete status.dataset.state; }
  }

  function errorMessage(error){
    if(error && error.network){
      return 'Markeringen kunde inte sparas. Kontrollera nätverksanslutningen och försök igen.';
    }
    const status = error && error.status;
    if(status === 401 || status === 403){
      return 'Markeringen kunde inte sparas. Kontrollera att sessionen fortfarande är aktiv och försök igen.';
    }
    if(status === 400 || status === 404){
      return 'Markeringen kunde inte sparas eftersom veckovyn eller raden inte längre är giltig.';
    }
    if(status === 409){
      return 'Markeringen kunde inte sparas eftersom uppgifterna ändrades. Läs in veckovyn igen.';
    }
    if(status === 412){
      return 'Markeringen kunde inte sparas eftersom veckovyn ändrades av någon annan. Försök igen.';
    }
    return 'Markeringen kunde inte sparas på grund av ett serverfel. Försök igen.';
  }

  async function fetchOrThrow(url, options, phase){
    let resp;
    try {
      resp = await fetch(url, options);
    } catch(e){
      throw new WeekviewRequestError(0, phase, true);
    }
    return resp;
  }

  async function getEtag(departmentId, year, week){
    const siteId = resolveSiteId();
    const base = `/api/weekview/etag?department_id=${encodeURIComponent(departmentId)}&year=${year}&week=${week}`;
    const url = siteId ? `${base}&site_id=${encodeURIComponent(siteId)}` : base;
    console.debug("[K3] GET ETag URL:", url);
    const resp = await fetchOrThrow(url, { headers: {"X-User-Role":"cook"} }, 'etag');
    if(!resp.ok){ throw new WeekviewRequestError(resp.status, 'etag'); }
    let json;
    try {
      json = await resp.json();
    } catch(e){
      throw new WeekviewRequestError(500, 'etag');
    }
    if(!json || !json.etag){ throw new WeekviewRequestError(500, 'etag'); }
    console.debug("[K3] Fetched ETag:", json.etag);
    return json.etag;
  }

  function requestOptions(etag, csrf, payload){
    return {
      method:'POST',
      credentials:'same-origin',
      headers:{
        'Content-Type':'application/json',
        'If-Match': etag,
        'X-User-Role':'cook',
        ...(csrf ? { 'X-CSRF-Token': csrf } : {})
      },
      body: JSON.stringify(payload)
    };
  }

  async function postWithRetry(url, payload, departmentId, year, week, csrf, label){
    let etag = await getEtag(departmentId, year, week);
    let resp = await fetchOrThrow(url, requestOptions(etag, csrf, payload), label);
    if(resp.status === 412){
      etag = await getEtag(departmentId, year, week);
      resp = await fetchOrThrow(url, requestOptions(etag, csrf, payload), label);
      if(resp.status === 412){
        throw new WeekviewRequestError(412, 'post');
      }
    }
    if(resp.status !== 200){
      throw new WeekviewRequestError(resp.status, 'post');
    }
  }

  function setMarkedState(btn, marked){
    if(marked){ btn.classList.add('is-done'); }
    else { btn.classList.remove('is-done'); }
  }

  async function toggleMark(btn){
    const depId = btn.dataset.departmentId;
    const dtId = btn.dataset.dietTypeId;
    const year = parseInt(btn.dataset.year, 10);
    const week = parseInt(btn.dataset.week, 10);
    const dayIdx = parseInt(btn.dataset.dayIndex, 10);
    const meal = btn.dataset.meal || "lunch";
    const marked = !btn.classList.contains('is-done');
    const siteId = resolveSiteId();
    const payload = {
      year: year,
      week: week,
      department_id: depId,
      diet_type_id: dtId,
      meal: meal,
      weekday_abbr: abbrFor(dayIdx),
      marked: marked,
      site_id: siteId
    };
    await postWithRetry(
      '/api/weekview/specialdiets/mark',
      payload,
      depId,
      year,
      week,
      getCsrfToken(),
      'specialdiet'
    );
    setMarkedState(btn, marked);
    setStatus(marked ? 'Markering sparad.' : 'Markering borttagen.', 'success');
  }

  async function toggleCohortMark(btn){
    const depId = btn.dataset.departmentId;
    const groupId = btn.dataset.groupId;
    const serviceDate = btn.dataset.serviceDate;
    const year = parseInt(btn.dataset.year, 10);
    const week = parseInt(btn.dataset.week, 10);
    const meal = (btn.dataset.meal || 'lunch').toLowerCase();
    const marked = !btn.classList.contains('is-done');
    const siteId = resolveSiteId();
    const payload = {
      site_id: siteId,
      department_id: depId,
      year: year,
      week: week,
      group_id: groupId,
      service_date: serviceDate,
      meal: meal,
      marked: marked
    };
    await postWithRetry(
      '/api/weekview/requirement-groups/mark',
      payload,
      depId,
      year,
      week,
      getCsrfToken(),
      'cohort'
    );
    setMarkedState(btn, marked);
    setStatus(marked ? 'Markering sparad.' : 'Markering borttagen.', 'success');
  }

  function beginPending(btn){
    if(btn.disabled || btn.dataset.weekviewPending === '1'){ return null; }
    const wasDisabled = btn.disabled;
    btn.dataset.weekviewPending = '1';
    btn.disabled = true;
    return wasDisabled;
  }

  function endPending(btn, wasDisabled){
    if(wasDisabled === null){ return; }
    btn.disabled = wasDisabled;
    delete btn.dataset.weekviewPending;
  }

  document.addEventListener('DOMContentLoaded', function(){
    document.addEventListener('click', async function(ev){
      const btn = ev.target && ev.target.closest ? ev.target.closest('.kostcell-btn') : null;
      if(!btn){ return; }
      ev.preventDefault();
      const wasDisabled = beginPending(btn);
      if(wasDisabled === null){ return; }
      const isCohort = btn.dataset.rowKind === 'cohort';
      setStatus('Sparar markering…');
      try {
        if(isCohort){ await toggleCohortMark(btn); }
        else { await toggleMark(btn); }
      } catch(error){
        setStatus(errorMessage(error), 'error');
      } finally {
        endPending(btn, wasDisabled);
        try { btn.blur(); } catch(e) { /* ignore */ }
      }
    });
  });
})();
