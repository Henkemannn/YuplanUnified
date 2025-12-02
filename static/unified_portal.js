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
