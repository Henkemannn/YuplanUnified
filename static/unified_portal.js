document.addEventListener("DOMContentLoaded", () => {
  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
    const cards = Array.from(document.querySelectorAll('.portal-day-card'));
    if (e.key === "ArrowLeft") {
      // Navigate to previous week if link exists in footer (heuristic)
      const prevLink = document.querySelector('.portal-actions a[href*="week="]');
      if (prevLink) prevLink.focus();
    }
    if (e.key === "ArrowRight") {
      // Focus next action button
      const actions = Array.from(document.querySelectorAll('.portal-actions a'));
      if (actions.length > 1) actions[1].focus();
    }
      if (e.key === 't' || e.key === 'T') {
        const todayCard = document.querySelector('.portal-day-card[data-is-today="true"]');
        if (todayCard) {
          try { todayCard.scrollIntoView({ behavior: 'smooth', block: 'center' }); } catch (_) {}
        }
      }
  });
});
function openMealDetails(dayKey, mealType) {
  try {
    const container = document.querySelector('main.portal-container');
    const siteId = container?.dataset.siteId || '';
    const departmentId = container?.dataset.departmentId || '';
    const year = container?.dataset.year || '';
    const week = container?.dataset.week || '';
    const date = dayKey;
    const url = `/ui/planera/day?site_id=${encodeURIComponent(siteId)}&department_id=${encodeURIComponent(departmentId)}&date=${encodeURIComponent(date)}&meal=${encodeURIComponent(mealType)}&year=${encodeURIComponent(year)}&week=${encodeURIComponent(week)}`;
    window.location.href = url;
  } catch (e) {
    console.error('Failed to navigate to meal details', e);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const mealBlocks = document.querySelectorAll('.meal-block[role="button"]');
  mealBlocks.forEach((el) => {
    const day = el.getAttribute('data-day-key') || el.getAttribute('data-day');
    const meal = el.getAttribute('data-meal');
    el.addEventListener('click', () => openMealDetails(day, meal));
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        openMealDetails(day, meal);
      }
    });
  });
});

// Kitchen grid: lightweight menu popup for .veckovy-menu-icon
document.addEventListener('DOMContentLoaded', () => {
  // Only activate if grid is present and menu data exists
  const hasGrid = document.querySelector('.veckovy-grid');
  if (!hasGrid || typeof window.VECKOVY_MENU_DATA === 'undefined') return;

  function buildMenuDialog(dayKey, openerBtn) {
    const data = window.VECKOVY_MENU_DATA[dayKey] || {};
    const overlay = document.createElement('div');
    overlay.className = 'veckovy-menu-overlay';
    overlay.setAttribute('role', 'presentation');

    const dialog = document.createElement('div');
    dialog.className = 'veckovy-menu-dialog';
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('tabindex', '-1');

    const title = document.createElement('h3');
    const weekday = data.weekday || '';
    const date = data.date || dayKey;
    title.textContent = `Meny – ${weekday} (${date})`;

    const list = document.createElement('div');
    list.className = 'veckovy-menu-list';

    function row(label, value) {
      const r = document.createElement('div');
      r.className = 'veckovy-menu-row';
      const l = document.createElement('span');
      l.className = 'veckovy-menu-label';
      l.textContent = label;
      const v = document.createElement('span');
      v.className = 'veckovy-menu-value';
      v.textContent = value || '-';
      r.appendChild(l); r.appendChild(v);
      return r;
    }

    list.appendChild(row('Alt 1', data.alt1));
    list.appendChild(row('Alt 2', data.alt2));
    list.appendChild(row('Kvällsmat', data.dinner));
    list.appendChild(row('Dessert', data.dessert));

    const actions = document.createElement('div');
    actions.className = 'veckovy-menu-actions';
    const closeBtn = document.createElement('button');
    closeBtn.type = 'button';
    closeBtn.className = 'veckovy-menu-close';
    closeBtn.textContent = 'Stäng';

    actions.appendChild(closeBtn);

    dialog.appendChild(title);
    dialog.appendChild(list);
    dialog.appendChild(actions);
    overlay.appendChild(dialog);

    function closeDialog() {
      try { document.body.removeChild(overlay); } catch (_) {}
      if (openerBtn) openerBtn.focus();
      document.removeEventListener('keydown', onKey);
    }

    function onKey(e) {
      if (e.key === 'Escape') closeDialog();
      if (e.key === 'Tab') {
        // Basic focus trap: keep focus within dialog
        const focusables = dialog.querySelectorAll('button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])');
        if (!focusables.length) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
      }
    }

    overlay.addEventListener('click', (e) => { if (e.target === overlay) closeDialog(); });
    closeBtn.addEventListener('click', closeDialog);
    document.addEventListener('keydown', onKey);

    document.body.appendChild(overlay);
    // Move focus to dialog
    setTimeout(() => { try { dialog.focus(); } catch (_) {} }, 0);
  }

  document.querySelectorAll('.veckovy-menu-icon').forEach((btn) => {
    btn.addEventListener('click', () => {
      const dayKey = btn.getAttribute('data-day-key') || btn.getAttribute('data-day');
      buildMenuDialog(dayKey, btn);
    });
  });
});

/* Minimal styles injected by CSS file; ensure classes exist:
   .veckovy-menu-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.35); display: flex; align-items: center; justify-content: center; z-index: 1000; }
   .veckovy-menu-dialog { background: #fff; max-width: 480px; width: 90%; padding: 16px; border-radius: 8px; box-shadow: 0 8px 24px rgba(0,0,0,0.2); }
   .veckovy-menu-row { display:flex; justify-content: space-between; margin: 6px 0; }
   .veckovy-menu-actions { margin-top: 12px; text-align: right; }
*/
