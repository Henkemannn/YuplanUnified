(function(){
  const html = document.documentElement;
  const body = document.body;
  const themeBtn = document.getElementById('themeToggle');
  // legacy .chef removed in redesign

  function setTheme(mode){
    body.classList.toggle('theme-dark', mode==='dark');
    body.classList.toggle('theme-light', mode!=='dark');
    themeBtn.setAttribute('aria-pressed', String(mode==='dark'));
    try{ localStorage.setItem('yuplan_theme', mode); }catch{}
  }

  window.addEventListener('DOMContentLoaded', ()=>{
    // Theme init
    const saved = localStorage.getItem('yuplan_theme') || 'light';
    setTheme(saved);
    themeBtn.addEventListener('click', ()=> setTheme(body.classList.contains('theme-dark') ? 'light' : 'dark'));

    // Year
    const y = document.getElementById('year'); if (y) y.textContent = new Date().getFullYear();

    // Reveal on view
    const io = new IntersectionObserver((entries)=>{
      entries.forEach(e=>{ if(e.isIntersecting){ e.target.classList.add('is-visible'); io.unobserve(e.target); } });
    }, {threshold: 0.12});
  document.querySelectorAll('.card, .section__title, .lead, .why__cards .card, .avatar-svg').forEach(el=> io.observe(el));

  // No avatar language flags; avatar is purely decorative now

    // Contact form submit (CSP-friendly)
    const form = document.getElementById('contactForm');
    if (form){
      form.addEventListener('submit', (e)=>{
        e.preventDefault();
        // Basic validity hint
        const email = form.querySelector('input[type="email"]');
        if (email && !email.checkValidity()){
          email.focus();
          email.reportValidity?.();
          return;
        }
        alert(window.i18n ? window.i18n.t('form_thanks') : 'Thanks!');
        form.reset();
      });
    }

    // Segmentation (Kommun / Offshore / Bankett)
    const segData = {
      kommun: {
        mod_menu_2: 'Synliga menyval per avdelning',
        mod_plan_body: 'Dagliga listor per avdelning – specialkost och mängder i synk.',
        mod_rep_body: 'Rapporter per avdelning, måltid och kosttyp (PDF/Excel).',
      },
      offshore: {
        mod_menu_2: 'Synliga menyval per rigg/rotasjon',
        mod_plan_body: 'Planering med turnus, skift och allergener i åtanke.',
        mod_rep_body: 'Rapporter per turnus, skift och enhet.',
      },
      banquet: {
        mod_menu_2: 'Val per gästlista/event',
        mod_plan_body: 'Eventplanering med kapacitet och tidslinjer.',
        mod_rep_body: 'Eventrapporter, plocklistor och produktionsöversikt.',
      },
    };
    function applySeg(kind){
      const d = segData[kind]; if (!d) return;
      // Update a subset of feature texts live to emphasize vertical differences
      const map = [
        ['mod_menu_2', d.mod_menu_2],
        ['mod_plan_body', d.mod_plan_body],
        ['mod_rep_body', d.mod_rep_body],
      ];
      map.forEach(([k,v])=>{
        const el = document.querySelector(`[data-i18n="${k}"]`);
        if (el) el.textContent = v;
      });
    }
    document.querySelectorAll('.seg__tab').forEach(btn=>{
      btn.addEventListener('click', ()=>{
        document.querySelectorAll('.seg__tab').forEach(b=>{
          b.classList.toggle('is-active', b === btn);
          b.setAttribute('aria-selected', String(b===btn));
        });
        applySeg(btn.dataset.seg);
      });
    });
    // Initialize segmentation default
    const activeSeg = document.querySelector('.seg__tab.is-active');
    if (activeSeg) applySeg(activeSeg.dataset.seg);
  });
})();
