// Toast + fetch helper ------------------------------------------------------
const Toasts = (() => {
  // Simple dedupe mechanism
  const activeKeys = new Map(); // key -> timeout id
  const root = () => document.getElementById('toast-root');
  function push(msg, {level='error', timeout=6000, actions=[], route=''}={}){
    const key = level+'|'+msg+'|'+route;
    if(activeKeys.has(key)) return {dismiss:()=>{}}; // dedup
    const id = 't'+Math.random().toString(36).slice(2);
    const box = document.createElement('div');
    box.className='toast';
    box.dataset.level=level;
    box.setAttribute('role','alert');
    box.innerHTML = `<button class="toast-close" aria-label="Stäng" data-close>&times;</button><div>${msg}</div>`;
    if(actions.length){
      const actWrap = document.createElement('div');
      actWrap.style.display='flex'; actWrap.style.gap='6px';
      actions.forEach(a=>{
        const b=document.createElement('button'); b.type='button'; b.textContent=a.label; b.addEventListener('click',()=>{ try{a.onClick?.();}finally{ dismiss(); }}); actWrap.appendChild(b);
      });
      box.appendChild(actWrap);
    }
    function dismiss(){ if(box.parentNode) box.parentNode.removeChild(box); if(activeKeys.has(key)){ clearTimeout(activeKeys.get(key)); activeKeys.delete(key);} }
    box.addEventListener('click', e=>{ if(e.target.matches('[data-close]')) dismiss(); });
    root().appendChild(box);
    if(timeout>0){ const tid=setTimeout(dismiss, timeout); activeKeys.set(key, tid); }
    return {dismiss};
  }
  return {push};
})();

async function safeFetch(url, opts={}, {expectJson=true, retryFn}={}){
  let res;
  try {
    res = await fetch(url, opts);
  } catch (e) {
    Toasts.push(`Nätverksfel: ${e.message||e}`, {actions: retryFn? [{label:'Försök igen', onClick: retryFn}]:[], route: url});
    throw e;
  }
  if(!res.ok){
    let bodyText='';
    try { bodyText = await res.text(); } catch {}
    let parsed; try { parsed = JSON.parse(bodyText); } catch {}
    const msg = parsed?.message || parsed?.error || res.status+' '+res.statusText;
    Toasts.push(`Fel (${res.status}): ${msg}`, {actions: retryFn? [{label:'Försök igen', onClick: retryFn}]:[], route: url});
    const err = new Error(msg); err.response = res; throw err;
  }
  if(expectJson){
    try { return await res.json(); } catch (e) { Toasts.push('Kunde inte tolka JSON-svar'); throw e; }
  }
  return res;
}

const jsonHeaders = {'Content-Type':'application/json'};

const API = {
  notes: {
    list: () => safeFetch('/notes/').then(j=>j.notes||[]),
    create: (payload) => safeFetch('/notes/', {method:'POST', headers:jsonHeaders, body:JSON.stringify(payload)}, {retryFn: ()=>API.notes.create(payload)}).then(j=>j.note),
    update: (id, payload) => safeFetch(`/notes/${id}`, {method:'PUT', headers:jsonHeaders, body:JSON.stringify(payload)}, {retryFn: ()=>API.notes.update(id,payload)}).then(j=>j.note),
    remove: (id) => safeFetch(`/notes/${id}`, {method:'DELETE'}, {expectJson:false, retryFn: ()=>API.notes.remove(id)}).then(r=>true)
  },
  tasks: {
    list: () => safeFetch('/tasks/').then(j=>j.tasks||[]),
    create: (payload) => safeFetch('/tasks/', {method:'POST', headers:jsonHeaders, body:JSON.stringify(payload)}, {retryFn: ()=>API.tasks.create(payload)}).then(j=>j.task),
    update: (id, payload) => safeFetch(`/tasks/${id}`, {method:'PUT', headers:jsonHeaders, body:JSON.stringify(payload)}, {retryFn: ()=>API.tasks.update(id,payload)}).then(j=>j.task),
    remove: (id) => safeFetch(`/tasks/${id}`, {method:'DELETE'}, {expectJson:false, retryFn: ()=>API.tasks.remove(id)}).then(r=>true)
  }
};

function h(tag, attrs={}, ...kids){
  const e=document.createElement(tag);
  for(const [k,v] of Object.entries(attrs||{})){
    if(k==='class') e.className=v; else if(k.startsWith('on')&&typeof v==='function') e.addEventListener(k.slice(2),v); else if(v!==false && v!=null) e.setAttribute(k,v===true? '': v);
  }
  kids.flat().forEach(k=>{ if(k==null) return; e.appendChild(typeof k==='string'?document.createTextNode(k):k); });
  return e;
}

async function loadNotes(){
  const list=document.getElementById('notes-list');
  const empty=document.getElementById('notes-empty');
  list.innerHTML='';
  const items = await API.notes.list();
  empty.hidden = items.length>0;
  items.forEach(n=> list.appendChild(renderNote(n)) );
  __NOTES_CACHE = items; // Store loaded notes
}

let __NOTES_CACHE = [];
let __TASKS_CACHE = [];

function applyNotesFilter(){
  const q = (document.getElementById('notes-search').value||'').toLowerCase();
  const list=document.getElementById('notes-list');
  const empty=document.getElementById('notes-empty');
  list.innerHTML='';
  const filtered = __NOTES_CACHE.filter(n=> !q || (n.content||'').toLowerCase().includes(q));
  empty.hidden = filtered.length>0;
  filtered.forEach(n=> list.appendChild(renderNote(n)) );
}

async function loadNotes(){
  __NOTES_CACHE = await API.notes.list();
  applyNotesFilter();
}
function renderNote(n){
  const content = h('div',{contenteditable:true}, n.content||'');
  content.addEventListener('blur', async ()=>{
    const val = content.textContent.trim();
    if(val && val !== n.content){
      n = await API.notes.update(n.id,{content:val});
      row.replaceWith(renderNote(n));
    }
  });
  const del = h('button',{onclick: async ()=>{ if(confirm('Ta bort?')){ const ok=await API.notes.remove(n.id); if(ok) row.remove(); } }},'X');
  const meta = h('span',{class:'pill'}, n.updated_at? new Date(n.updated_at).toLocaleString(): 'ny');
  const row = h('li',{class:'item'}, h('div',{class:'rowline'}, h('strong',{},`Note #${n.id}`), meta), content, h('div',{class:'rowline'}, h('span',{}, n.private_flag? 'Privat':'Publik'), del));
  return row;
}

async function loadTasks(){
  const list=document.getElementById('tasks-list');
  const empty=document.getElementById('tasks-empty');
  list.innerHTML='';
  const items = await API.tasks.list();
  empty.hidden = items.length>0;
  items.forEach(t=> list.appendChild(renderTask(t)) );
  __TASKS_CACHE = items; // Store loaded tasks
}

function derivedStatus(t){
  // Prefer explicit status from API; fallback to legacy done boolean.
  if(t.status) return t.status;
  return t.done ? 'done' : 'todo';
}

function applyTasksFilter(){
  const q=(document.getElementById('tasks-search').value||'').toLowerCase();
  const st=document.getElementById('tasks-status-filter').value;
  const ty=document.getElementById('tasks-type-filter').value;
  const list=document.getElementById('tasks-list');
  const empty=document.getElementById('tasks-empty');
  list.innerHTML='';
  const filtered = __TASKS_CACHE.filter(t=>{
    if(q && !(t.title||'').toLowerCase().includes(q)) return false;
    const status = derivedStatus(t);
    if(st && status !== st) return false;
    if(ty && t.task_type !== ty) return false;
    return true;
  });
  empty.hidden = filtered.length>0;
  filtered.forEach(t=> list.appendChild(renderTask(t)) );
}

async function loadTasks(){
  __TASKS_CACHE = await API.tasks.list();
  applyTasksFilter();
}
function renderTask(t){
  const currentStatus = derivedStatus(t);
  const title = h('div',{contenteditable:true,class: currentStatus==='done'? 'done':''}, t.title||'');
  title.addEventListener('blur', async ()=>{
    const val = title.textContent.trim();
    if(val && val !== t.title){
      t = await API.tasks.update(t.id,{title:val});
      row.replaceWith(renderTask(t));
    }
  });
  // Status pill -> inline select
  const statusColors = {todo:'gray', doing:'dodgerblue', blocked:'orange', done:'green', cancelled:'#777'};
  const pill = h('button',{class:'pill', type:'button', 'aria-haspopup':'listbox', style:`cursor:pointer; background:${statusColors[currentStatus]||'gray'};`}, currentStatus);
  let listbox=null; let savingSpinner=null; let prevStatus=currentStatus; let optimistic=false;

  function closeListbox(focusBack=true){
    if(listbox && listbox.parentNode){ listbox.parentNode.removeChild(listbox); listbox=null; }
    pill.setAttribute('aria-expanded','false');
    if(focusBack) pill.focus();
  }
  function setStatusLabel(s){ pill.textContent=s; pill.style.background = statusColors[s]||'gray'; }

  async function commitStatus(newStatus){
    if(newStatus===prevStatus) return closeListbox();
    optimistic=true; prevStatus=currentStatus; const oldLabel=pill.textContent;
    setStatusLabel(newStatus); pill.disabled=true; pill.setAttribute('aria-busy','true');
  savingSpinner = h('span',{class:'spinner','aria-hidden':'true'}); pill.appendChild(savingSpinner);
    try{
      t = await API.tasks.update(t.id,{status:newStatus});
      // replace row with fresh render
      row.replaceWith(renderTask(t));
    }catch(e){
      setStatusLabel(prevStatus); Toasts.push(e.message||'Status update failed', {level:'error'});
    }finally{
      optimistic=false; pill.disabled=false; pill.removeAttribute('aria-busy'); if(savingSpinner&&savingSpinner.parentNode) savingSpinner.parentNode.removeChild(savingSpinner);
      closeListbox();
    }
  }
  function openListbox(){
    if(listbox) return;
    listbox = h('ul',{role:'listbox',class:'status-listbox', style:'list-style:none; margin:4px 0 0; padding:4px; background:#222; border:1px solid #555; display:flex; gap:4px; flex-wrap:wrap;'});
    const options=['todo','doing','blocked','done','cancelled'];
    options.forEach(opt=>{
      const optEl = h('li',{role:'option','data-value':opt, tabindex:'-1', style:`padding:4px 8px; border-radius:4px; background:${statusColors[opt]}; color:#fff; cursor:pointer; font-size:12px;`}, opt);
      if(opt===currentStatus) optEl.setAttribute('aria-selected','true');
      optEl.addEventListener('click', ()=>commitStatus(opt));
      listbox.appendChild(optEl);
    });
    pill.after(listbox);
    // focus first selected or first
    const sel = listbox.querySelector('[aria-selected]') || listbox.firstChild; sel && sel.focus();
  }
  pill.addEventListener('click', ()=>{ const opened = !!listbox; if(!opened) { openListbox(); pill.setAttribute('aria-expanded','true'); } else { closeListbox(); } });
  pill.addEventListener('keydown', e=>{
    if(e.key==='Enter' || e.key===' '){ e.preventDefault(); const opened=!!listbox; if(!opened) openListbox(); pill.setAttribute('aria-expanded', String(!opened)); }
  });
  document.addEventListener('keydown', e=>{
    if(!listbox) return;
    const focusable = Array.from(listbox.querySelectorAll('[role=option]'));
    const idx = focusable.indexOf(document.activeElement);
    if(['ArrowRight','ArrowDown'].includes(e.key)){ e.preventDefault(); const n=focusable[(idx+1)%focusable.length]; n && n.focus(); }
    else if(['ArrowLeft','ArrowUp'].includes(e.key)){ e.preventDefault(); const n=focusable[(idx-1+focusable.length)%focusable.length]; n && n.focus(); }
    else if(e.key==='Enter'){ e.preventDefault(); const val=document.activeElement?.dataset.value; if(val) commitStatus(val); }
    else if(e.key==='Escape'){ e.preventDefault(); closeListbox(); }
  });
  document.addEventListener('click', e=>{ if(listbox && !listbox.contains(e.target) && e.target!==pill){ pill.setAttribute('aria-expanded','false'); closeListbox(false);} });

  const del = h('button',{onclick: async ()=>{ if(confirm('Ta bort?')){ const ok=await API.tasks.remove(t.id); if(ok) row.remove(); } }},'X');
  const row = h('li',{class:'item'}, h('div',{class:'rowline'}, h('strong',{},`Task #${t.id}`), pill), title, h('div',{class:'actions'}, del));
  return row;
}

function bindCreate(){
  document.getElementById('note-create').addEventListener('click', async ()=>{
    const content = document.getElementById('note-content');
    const priv = document.getElementById('note-private');
    const val = content.value.trim();
    if(!val) return;
    const created = await API.notes.create({content:val, private_flag: priv.checked});
    content.value=''; priv.checked=false;
    __NOTES_CACHE.unshift(created);
    applyNotesFilter();
  });
  document.getElementById('task-create').addEventListener('click', async ()=>{
    const title = document.getElementById('task-title');
    const type = document.getElementById('task-type');
    const priv = document.getElementById('task-private');
    const val = title.value.trim();
    if(!val) return;
    const created = await API.tasks.create({title:val, task_type:type.value, private_flag: priv.checked});
    title.value=''; priv.checked=false; type.value='prep';
    __TASKS_CACHE.unshift(created);
    applyTasksFilter();
  });
}

(async function init(){
  await Promise.all([loadNotes(), loadTasks()]);
  bindCreate();
  // Wire note filters
  document.getElementById('notes-search').addEventListener('input', applyNotesFilter);
  document.getElementById('notes-clear').addEventListener('click', ()=>{ document.getElementById('notes-search').value=''; applyNotesFilter(); });
  // Wire task filters
  document.getElementById('tasks-search').addEventListener('input', applyTasksFilter);
  document.getElementById('tasks-status-filter').addEventListener('change', applyTasksFilter);
  document.getElementById('tasks-type-filter').addEventListener('change', applyTasksFilter);
  document.getElementById('tasks-clear').addEventListener('click', ()=>{ document.getElementById('tasks-search').value=''; document.getElementById('tasks-status-filter').value=''; document.getElementById('tasks-type-filter').value=''; applyTasksFilter(); });
})();
