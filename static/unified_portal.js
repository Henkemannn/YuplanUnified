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
    if (e.key.toLowerCase() === 't') {
      // Scroll to today's card
      const todayCard = cards.find(c => c.dataset.isToday === 'true');
      if (todayCard) {
        todayCard.scrollIntoView({behavior:'smooth', block:'start'});
        todayCard.classList.add('flash-today');
        setTimeout(() => todayCard.classList.remove('flash-today'), 1200);
      }
    }
  });
});
