/**
 * Unified Weekview - Phase 3 JavaScript
 * Handles registration modal, inline toggles, and keyboard navigation
 * CSP-compliant: No inline event handlers
 */

(function() {
  'use strict';

  // State
  let modalElement = null;
  let isModalOpen = false;

  /**
   * Initialize weekview functionality on DOM ready
   */
  function init() {
    modalElement = document.getElementById('registrationModal');
    if (!modalElement) return;

    setupModalListeners();
    setupKeyboardNavigation();
    setupInlineToggles();
    setupDietToggleHandlers();
    checkFlashMessages();
  }

  /**
   * Phase 2: Modal functionality
   */
  function setupModalListeners() {
    // Close button handler
    const closeButtons = document.querySelectorAll('[data-action="close-modal"]');
    closeButtons.forEach(btn => {
      btn.addEventListener('click', closeModal);
    });

    // Click outside to close
    modalElement.addEventListener('click', function(e) {
      if (e.target === modalElement) {
        closeModal();
      }
    });

    // Escape key to close
    document.addEventListener('keydown', function(e) {
      if (e.key === 'Escape' && isModalOpen) {
        closeModal();
      }
    });
  }

  /**
   * Weekview diet mark toggles via API
   * - Optimistic UI: toggle class immediately; revert on error
   * - Uses ETag from lightweight endpoint to set If-Match
   * - Sends CSRF header if meta tag present
   */
  function setupDietToggleHandlers() {
    const pills = document.querySelectorAll('.diet-pill');
    pills.forEach(pill => {
      pill.addEventListener('click', async function(e) {
        e.preventDefault();
        const dietTypeId = this.dataset.dietTypeId;
        const meal = this.dataset.meal; // 'lunch' | 'dinner'
        const year = parseInt(this.dataset.year, 10);
        const week = parseInt(this.dataset.week, 10);
        const departmentId = this.dataset.departmentId;
        const dayOfWeek = parseInt(this.dataset.dayOfWeek, 10);

        if (!dietTypeId || !meal || !departmentId || !year || !week || !dayOfWeek) {
          showToast('Ogiltig data för registrering', 'error');
          return;
        }

        // Capture current state (optimistic toggle)
        const wasMarked = this.classList.contains('diet-marked');
        const desired = !wasMarked;
        // Toggle UI optimistically
        this.classList.toggle('diet-marked', desired);
        this.dataset.marked = desired ? 'true' : 'false';

        try {
          // Fetch current ETag for the department/week
          const etagResp = await fetch(`/api/weekview/etag?department_id=${encodeURIComponent(departmentId)}&year=${year}&week=${week}`, {
            headers: { 'Accept': 'application/json' }
          });
          if (!etagResp.ok) throw new Error('etag');
          const etagData = await etagResp.json();
          const etag = etagData && etagData.etag ? etagData.etag : '';
          if (!etag) throw new Error('etag');

          // CSRF token from meta, if available
          const meta = document.querySelector('meta[name="csrf-token"]');
          const csrfToken = meta ? meta.getAttribute('content') : null;

          const body = {
            year: year,
            week: week,
            department_id: departmentId,
            diet_type_id: dietTypeId,
            meal: meal,
            day_of_week: dayOfWeek,
            marked: desired
          };

          const resp = await fetch('/api/weekview/specialdiets/mark', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
              'If-Match': etag,
              ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
            },
            body: JSON.stringify(body)
          });

          if (resp.ok) {
            showToast('Sparat', 'success');
            // Optionally update ETag on grid container
            const grid = document.querySelector('.week-grid');
            const newEtag = resp.headers.get('ETag');
            if (grid && newEtag) grid.setAttribute('data-etag', newEtag);
          } else {
            // Failure: revert UI and show error
            this.classList.toggle('diet-marked', wasMarked);
            this.dataset.marked = wasMarked ? 'true' : 'false';
            const msg = resp.status === 412 ? 'Kunde inte spara (ETag mismatch)' :
                        resp.status === 403 ? 'Kunde inte spara (behörighet)' : 'Kunde inte spara';
            showToast(msg, 'error');
          }
        } catch (err) {
          // Network/ETag error: revert UI
          this.classList.toggle('diet-marked', wasMarked);
          this.dataset.marked = wasMarked ? 'true' : 'false';
          showToast('Kunde inte spara', 'error');
        }
      });

      pill.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.click();
        }
      });
    });
  }

  /**
   * Open modal with meal data
   */
  function openModal(date, mealType, registered) {
    const mealLabel = mealType === 'lunch' ? 'Lunch' : 'Middag';
    
    // Update modal content
    const subtitle = document.getElementById('modalSubtitle');
    if (subtitle) {
      subtitle.textContent = `${date} - ${mealLabel}`;
    }

    // Update hidden form fields
    const dateField = document.getElementById('modalDate');
    const mealTypeField = document.getElementById('modalMealType');
    const checkbox = document.getElementById('modalRegistered');

    if (dateField) dateField.value = date;
    if (mealTypeField) mealTypeField.value = mealType;
    if (checkbox) checkbox.checked = registered;

    // Show modal
    modalElement.classList.add('active');
    isModalOpen = true;

    // Focus first interactive element
    const firstInput = modalElement.querySelector('input[type="checkbox"]');
    if (firstInput) {
      setTimeout(() => firstInput.focus(), 100);
    }
  }

  /**
   * Close modal
   */
  function closeModal() {
    if (modalElement) {
      modalElement.classList.remove('active');
      isModalOpen = false;
    }
  }

  /**
   * Phase 3: Setup inline toggle functionality
   * Single-click toggles registration without modal
   */
  function setupInlineToggles() {
    const mealCells = document.querySelectorAll('[data-meal-cell]');
    
    mealCells.forEach(cell => {
      cell.addEventListener('click', function(e) {
        // Don't trigger if clicking modal open button
        if (e.target.closest('[data-action="open-modal"]')) {
          e.preventDefault();
          const date = this.dataset.date;
          const mealType = this.dataset.mealType;
          const registered = this.dataset.registered === 'true';
          openModal(date, mealType, registered);
          return;
        }

        // Quick toggle: submit form immediately
        const form = this.querySelector('[data-quick-toggle-form]');
        if (form) {
          form.submit();
        }
      });

      // Keyboard accessibility
      cell.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          this.click();
        }
      });
    });
  }

  /**
   * Phase 3: Keyboard shortcuts for week and day/department navigation
   */
  function setupKeyboardNavigation() {
    document.addEventListener('keydown', function(e) {
      // Don't trigger shortcuts when modal is open or typing in input
      if (isModalOpen || e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        return;
      }

      const prevWeekBtn = document.querySelector('[data-nav="prev-week"]');
      const nextWeekBtn = document.querySelector('[data-nav="next-week"]');
      const header = document.querySelector('.weekview-header');
      const todayBtn = document.querySelector('.weekview-nav-btn.weekview-nav-btn--primary');

      // Arrow Left/Right: Navigate weeks
      if (e.key === 'ArrowLeft' && prevWeekBtn && !e.shiftKey) {
        e.preventDefault();
        prevWeekBtn.click();
      } else if (e.key === 'ArrowRight' && nextWeekBtn && !e.shiftKey) {
        e.preventDefault();
        nextWeekBtn.click();
      }
      // H: scroll to header
      else if ((e.key === 'h' || e.key === 'H') && header) {
        e.preventDefault();
        header.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
      // D: go to today (navigate to current week and focus first meal cell)
      else if ((e.key === 'd' || e.key === 'D')) {
        e.preventDefault();
        if (todayBtn) {
          todayBtn.click();
        }
        const firstCell = document.querySelector('[data-meal-cell]');
        if (firstCell) {
          setTimeout(() => firstCell.focus(), 150);
        }
      }
      
      // Arrow Up/Down: Navigate between meal cells (optional enhancement)
      else if ((e.key === 'ArrowUp' || e.key === 'ArrowDown') && document.activeElement.hasAttribute('data-meal-cell')) {
        e.preventDefault();
        const cells = Array.from(document.querySelectorAll('[data-meal-cell]'));
        const currentIndex = cells.indexOf(document.activeElement);
        
        if (e.key === 'ArrowUp' && currentIndex > 0) {
          cells[currentIndex - 1].focus();
        } else if (e.key === 'ArrowDown' && currentIndex < cells.length - 1) {
          cells[currentIndex + 1].focus();
        }
      }
    });
  }

  /**
   * Phase 2: Show toast notification (for save feedback)
   */
  function showToast(message, type = 'success') {
    // Use unified UI announce if available
    if (window.YuplanUI && window.YuplanUI.announce) {
      window.YuplanUI.announce(message);
    }
    
    // Also show visual toast
    const toast = document.createElement('div');
    toast.className = `yp-toast yp-toast--${type}`;
    toast.textContent = message;
    toast.style.cssText = `
      position: fixed;
      bottom: 2rem;
      right: 2rem;
      background: ${type === 'success' ? 'var(--yp-color-success)' : 'var(--yp-color-danger)'};
      color: white;
      padding: 1rem 1.5rem;
      border-radius: var(--yp-radius);
      box-shadow: var(--yp-shadow-lg);
      z-index: 9999;
      font-weight: 600;
      animation: slideInRight 0.3s ease, fadeOut 0.3s ease 2.7s;
    `;
    
    document.body.appendChild(toast);
    
    setTimeout(() => {
      toast.remove();
    }, 3000);
  }

  /**
   * Check for flash messages and show as toast
   */
  function checkFlashMessages() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(flash => {
      const message = flash.textContent.trim();
      const type = flash.classList.contains('flash-success') ? 'success' : 
                   flash.classList.contains('flash-error') ? 'error' : 'info';
      
      if (message) {
        showToast(message, type);
      }
      
      flash.remove(); // Remove flash message DOM element
    });
  }

  /**
   * Phase 3: Form double-submit protection
   */
  function setupFormProtection() {
    const forms = document.querySelectorAll('form[data-quick-toggle-form]');
    forms.forEach(form => {
      form.addEventListener('submit', function() {
        const submitBtn = this.querySelector('[type="submit"]');
        if (submitBtn) {
          submitBtn.disabled = true;
          setTimeout(() => submitBtn.disabled = false, 2000);
        }
      });
    });
  }

  /**
   * Expose global function for backwards compatibility
   * (Can be removed if all onclick handlers are replaced)
   */
  window.openRegistrationModal = function(element) {
    const date = element.getAttribute('data-date');
    const mealType = element.getAttribute('data-meal-type');
    const registered = element.getAttribute('data-registered') === 'true';
    openModal(date, mealType, registered);
  };

  window.closeRegistrationModal = closeModal;

  // Initialize on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
