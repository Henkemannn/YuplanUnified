// Feature Flags: list and toggle without reload (uses CSRF header)
(function(){
  function readCookie(n){ return (document.cookie.split('; ').find(r=>r.startsWith(n+'='))||'').split('=')[1]||''; }
  function csrf(){ const m=document.querySelector('meta[name="csrf-token"]'); return (m&&m.content)||readCookie('csrf_token')||''; }
  async function load(){
    const ul = document.getElementById('ff-list'); if(!ul) return;
    ul.innerHTML = '';
    try{
      const r = await fetch('/api/superuser/feature-flags', { credentials:'same-origin' });
      const j = await r.json();
      (j.items||[]).forEach(it=>{
        const li = document.createElement('li');
        li.dataset.key = it.key;
        const btn = document.createElement('button');
        btn.className = 'yu-btn yu-btn--soft';
        btn.setAttribute('data-testid', `ff-toggle-${it.key}`);
        btn.setAttribute('aria-pressed', String(!!it.enabled));
        btn.textContent = `${it.key}: ${it.enabled ? 'På' : 'Av'}`;
        btn.addEventListener('click', async ()=>{
          btn.disabled = true;
          try{
            const res = await fetch(`/api/superuser/feature-flags/${encodeURIComponent(it.key)}:toggle`, {
              method:'POST',
              headers: { 'X-CSRF-Token': csrf() },
              credentials:'same-origin'
            });
            const out = await res.json().catch(()=>({}));
            const on = !!out.enabled;
            btn.setAttribute('aria-pressed', String(on));
            btn.textContent = `${it.key}: ${on ? 'På' : 'Av'}`;
          } finally {
            btn.disabled = false;
          }
        });
        li.appendChild(btn);
        ul.appendChild(li);
      });
    } catch(_) {
      // noop
    }
  }
  document.addEventListener('DOMContentLoaded', load);
})();
