async function yuLoginSubmit(ev) {
  ev.preventDefault();
  const email = document.getElementById('email').value.trim().toLowerCase();
  const password = document.getElementById('password').value;
  const btn = document.getElementById('submit');
  const msg = document.getElementById('msg');
  const alertBox = document.getElementById('login-error');
  const alertDetail = document.getElementById('login-error-detail');
  if (msg) msg.textContent = '';
  if (alertBox && alertDetail) { alertBox.hidden = true; alertDetail.textContent = ''; }
  btn.disabled = true;
  btn.setAttribute('aria-busy', 'true');
  btn.classList.add('is-loading');
  try {
    const res = await fetch('/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || data.ok === false) {
      const detail = (data && (data.detail || data.message || data.error)) || 'Inloggning misslyckades';
      if (alertBox && alertDetail) {
        alertDetail.textContent = detail;
        alertBox.hidden = false;
        // Focus the alert so SR users hear it immediately
        if (typeof alertBox.focus === 'function') alertBox.focus();
      } else if (msg) {
        msg.textContent = detail;
      }
      return;
    }
    window.location.href = '/workspace';
  } catch (e) {
    if (alertBox && alertDetail) {
      alertDetail.textContent = 'Nätverksfel – försök igen';
      alertBox.hidden = false;
      if (typeof alertBox.focus === 'function') alertBox.focus();
    } else if (msg) {
      msg.textContent = 'Nätverksfel – försök igen';
    }
  } finally {
  btn.disabled = false;
  btn.removeAttribute('aria-busy');
  btn.classList.remove('is-loading');
  }
}

function yuToggleTheme(mode) {
  const root = document.documentElement;
  if (mode === 'dark') root.setAttribute('data-mode', 'dark');
  else root.setAttribute('data-mode', 'light');
  try {
    localStorage.setItem('yu-theme', mode); // legacy
    localStorage.setItem('yu_mode', mode);  // new
  } catch(_){}
  const lightBtn = document.getElementById('theme-light');
  const darkBtn = document.getElementById('theme-dark');
  if (lightBtn) lightBtn.setAttribute('aria-pressed', String(mode !== 'dark'));
  if (darkBtn) darkBtn.setAttribute('aria-pressed', String(mode === 'dark'));
}

function yuApplySavedTheme() {
  try {
    const t = localStorage.getItem('yu_mode') || localStorage.getItem('yu-theme');
    if (t === 'dark') document.documentElement.setAttribute('data-mode', 'dark');
    else if (t === 'light') document.documentElement.setAttribute('data-mode', 'light');
    const lightBtn = document.getElementById('theme-light');
    const darkBtn = document.getElementById('theme-dark');
    if (lightBtn) lightBtn.setAttribute('aria-pressed', String(t !== 'dark'));
    if (darkBtn) darkBtn.setAttribute('aria-pressed', String(t === 'dark'));
  } catch(_){}
}

function yuToggleBrand(brand) {
  const root = document.documentElement;
  if (!brand || brand === 'teal') root.removeAttribute('data-brand');
  else root.setAttribute('data-brand', brand);
  try {
    localStorage.setItem('yu-brand', brand || 'teal'); // legacy
    localStorage.setItem('yu_brand', brand || 'teal'); // new
  } catch(_){}
  const btns = {
    teal: document.getElementById('brand-teal'),
    ocean: document.getElementById('brand-ocean'),
    emerald: document.getElementById('brand-emerald')
  };
  Object.entries(btns).forEach(([k, el]) => {
    if (el) el.setAttribute('aria-pressed', String((brand || 'teal') === k));
  });
}

function yuApplySavedBrand() {
  try {
    const b = localStorage.getItem('yu_brand') || localStorage.getItem('yu-brand');
    if (b && b !== 'teal') document.documentElement.setAttribute('data-brand', b);
    const btns = {
      teal: document.getElementById('brand-teal'),
      ocean: document.getElementById('brand-ocean'),
      emerald: document.getElementById('brand-emerald')
    };
    const active = b || 'teal';
    Object.entries(btns).forEach(([k, el]) => {
      if (el) el.setAttribute('aria-pressed', String(active === k));
    });
  } catch(_){}
}

  // Removed variant button demo; keep submit button default styling

document.addEventListener('DOMContentLoaded', () => {
  yuApplySavedTheme();
  yuApplySavedBrand();

  const form = document.getElementById('login-form');
  const email = document.getElementById('email');
  const password = document.getElementById('password');
  const errorBox = document.getElementById('login-error');
  const errTitle = document.getElementById('login-error-title');
  const errDetail = document.getElementById('login-error-detail');

  function showErrorPD(pd) {
    if (errTitle) errTitle.textContent = (pd && pd.title) || 'Fel vid inloggning';
    if (errDetail) errDetail.textContent = (pd && pd.detail) || 'Kontrollera dina uppgifter och försök igen.';
    if (errorBox) {
      // Respect reduced-motion: avoid animation class entirely
      const reduce = typeof window !== 'undefined' && window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      errorBox.classList.remove('alert--animate');
      errorBox.hidden = false;
      if (!reduce) {
        // trigger reflow to restart animation cleanly
        // eslint-disable-next-line no-unused-expressions
        errorBox.offsetHeight;
        errorBox.classList.add('alert--animate');
      }
    }

    const firstInvalid = (email && !email.value) ? email : password;
    if (firstInvalid) {
      firstInvalid.setAttribute('aria-invalid', 'true');
      if (errorBox) firstInvalid.setAttribute('aria-describedby', errorBox.id);
    }

    requestAnimationFrame(() => {
      if (errorBox && typeof errorBox.focus === 'function') errorBox.focus();
      setTimeout(() => { if (firstInvalid && typeof firstInvalid.focus === 'function') firstInvalid.focus(); }, 50);
    });
  }

  function clearErrors() {
    if (errorBox) {
      errorBox.hidden = true;
      errorBox.classList.remove('alert--animate');
    }
    [email, password].forEach((el) => {
      if (!el) return;
      el.removeAttribute('aria-invalid');
      el.removeAttribute('aria-describedby');
    });
  }

  form && form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearErrors();
    form.setAttribute('aria-busy', 'true');

    try {
      const body = { email: (email && email.value ? email.value.trim() : ''), password: (password && password.value) || '' };
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(body),
        credentials: 'same-origin'
      });

      if (res.ok) {
        let body = {};
        try { body = await res.json(); } catch(_) {}
        const next = body && body.role === 'superuser' ? '/superuser/dashboard' : '/workspace';
        window.location.assign(next);
        return;
      }

      let pd = {};
      try { pd = await res.json(); } catch (_) {}
      showErrorPD(pd);
    } catch (_) {
      showErrorPD({ title: 'Nätverksfel', detail: 'Kunde inte nå servern. Försök igen.' });
    } finally {
      form.removeAttribute('aria-busy');
    }
  });

  // CapsLock-hint (diskret)
  password && password.addEventListener('keydown', (ev) => {
    const on = ev.getModifierState && ev.getModifierState('CapsLock');
    const hint = document.getElementById('capslock-hint');
    if (!hint) return;
    hint.hidden = !on;
  });

  // Enter-submit från alla fält
  [email, password].forEach((el) => el && el.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter' && form && typeof form.requestSubmit === 'function') form.requestSubmit();
  }));

  const togglePass = document.getElementById('toggle-password');
  if (togglePass && password) {
    togglePass.addEventListener('click', () => {
      const isPwd = password.getAttribute('type') === 'password';
      password.setAttribute('type', isPwd ? 'text' : 'password');
      togglePass.setAttribute('aria-pressed', String(isPwd));
      togglePass.textContent = isPwd ? 'Dölj' : 'Visa';
    });
  }

  const themeLight = document.getElementById('theme-light');
  const themeDark = document.getElementById('theme-dark');
  themeLight && themeLight.addEventListener('click', () => yuToggleTheme('light'));
  themeDark && themeDark.addEventListener('click', () => yuToggleTheme('dark'));
  const brandTeal = document.getElementById('brand-teal');
  const brandOcean = document.getElementById('brand-ocean');
  const brandEmerald = document.getElementById('brand-emerald');
  brandTeal && brandTeal.addEventListener('click', () => yuToggleBrand('teal'));
  brandOcean && brandOcean.addEventListener('click', () => yuToggleBrand('ocean'));
  brandEmerald && brandEmerald.addEventListener('click', () => yuToggleBrand('emerald'));
  // No variant buttons to wire
});
