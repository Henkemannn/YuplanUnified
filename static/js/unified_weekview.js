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
