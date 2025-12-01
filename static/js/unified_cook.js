/**
 * Unified Cook Dashboard - Phase 4
 * Interactive enhancements for kitchen staff tablet interface
 */

(function() {
    'use strict';

    // =========================================================================
    // Initialization
    // =========================================================================

    document.addEventListener('DOMContentLoaded', function() {
        initSmoothScroll();
        initKeyboardShortcuts();
        initAutoFocus();
        initButtonRipple();
        initAutoRefresh();
    });

    // =========================================================================
    // Smooth Scroll
    // =========================================================================

    function initSmoothScroll() {
        const links = document.querySelectorAll('a[href^="#"]');
        
        links.forEach(link => {
            link.addEventListener('click', function(e) {
                const href = this.getAttribute('href');
                if (href === '#') return;
                
                e.preventDefault();
                const target = document.querySelector(href);
                
                if (target) {
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                    
                    // Focus target for accessibility
                    target.focus({ preventScroll: true });
                }
            });
        });
    }

    // =========================================================================
    // Keyboard Shortcuts
    // =========================================================================

    function initKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Skip if user is typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
                return;
            }

            const key = e.key.toLowerCase();

            switch(key) {
                case 'l':
                    // Jump to lunch section
                    e.preventDefault();
                    scrollToSection('lunchSection');
                    break;
                
                case 'k':
                    // Jump to dinner section (if exists)
                    e.preventDefault();
                    scrollToSection('dinnerSection');
                    break;
                
                case 'v':
                    // Open weekview
                    e.preventDefault();
                    const weekviewLink = document.querySelector('a[href*="weekview"]');
                    if (weekviewLink) {
                        weekviewLink.click();
                    }
                    break;
                
                case 'r':
                    // Refresh page
                    e.preventDefault();
                    window.location.reload();
                    break;
                
                case '?':
                    // Show keyboard shortcuts help
                    e.preventDefault();
                    showKeyboardHelp();
                    break;
            }
        });
    }

    function scrollToSection(sectionId) {
        const section = document.getElementById(sectionId);
        if (section) {
            section.scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
            
            // Add highlight effect
            section.style.transition = 'all 0.3s ease';
            section.style.transform = 'scale(1.02)';
            section.style.boxShadow = '0 20px 25px -5px rgb(0 0 0 / 0.2)';
            
            setTimeout(() => {
                section.style.transform = '';
                section.style.boxShadow = '';
            }, 600);
        }
    }

    function showKeyboardHelp() {
        const helpText = `
Tangentbordsgenvägar:
━━━━━━━━━━━━━━━━━━━━
L - Gå till lunch
K - Gå till kvällsmat
V - Öppna veckovy
R - Uppdatera sida
? - Visa denna hjälp
        `.trim();
        
        alert(helpText);
    }

    // =========================================================================
    // Auto Focus
    // =========================================================================

    function initAutoFocus() {
        // Auto-focus first meal card for keyboard navigation
        const firstMealCard = document.querySelector('.meal-card');
        if (firstMealCard) {
            // Make it focusable
            if (!firstMealCard.hasAttribute('tabindex')) {
                firstMealCard.setAttribute('tabindex', '0');
            }
        }

        // Make all cards keyboard accessible
        const allCards = document.querySelectorAll('.meal-card, .department-card');
        allCards.forEach(card => {
            if (!card.hasAttribute('tabindex')) {
                card.setAttribute('tabindex', '0');
            }
        });
    }

    // =========================================================================
    // Button Ripple Effect
    // =========================================================================

    function initButtonRipple() {
        const buttons = document.querySelectorAll('.yp-button, .action-button');
        
        buttons.forEach(button => {
            button.addEventListener('click', function(e) {
                const ripple = document.createElement('span');
                ripple.classList.add('ripple');
                
                const rect = this.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;
                
                ripple.style.width = ripple.style.height = size + 'px';
                ripple.style.left = x + 'px';
                ripple.style.top = y + 'px';
                
                this.appendChild(ripple);
                
                setTimeout(() => {
                    ripple.remove();
                }, 600);
            });
        });
    }

    // =========================================================================
    // Auto Refresh (Optional)
    // =========================================================================

    function initAutoRefresh() {
        // Check if auto-refresh is enabled (stored in localStorage)
        const autoRefreshEnabled = localStorage.getItem('cookDashboardAutoRefresh') === 'true';
        const refreshInterval = parseInt(localStorage.getItem('cookDashboardRefreshInterval') || '300000'); // Default 5 minutes

        if (autoRefreshEnabled) {
            let refreshTimer = setInterval(() => {
                window.location.reload();
            }, refreshInterval);

            // Add visual indicator
            addRefreshIndicator(refreshInterval);

            // Allow user to cancel
            window.addEventListener('beforeunload', () => {
                clearInterval(refreshTimer);
            });
        }

        // Add toggle button (hidden by default, can be enabled via console)
        if (window.location.search.includes('debug')) {
            addRefreshToggle();
        }
    }

    function addRefreshIndicator(interval) {
        const indicator = document.createElement('div');
        indicator.style.cssText = `
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: rgba(37, 99, 235, 0.9);
            color: white;
            padding: 8px 16px;
            border-radius: 20px;
            font-size: 0.875rem;
            z-index: 1000;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1);
        `;
        indicator.textContent = `Auto-uppdatering: ${interval / 60000} min`;
        document.body.appendChild(indicator);
    }

    function addRefreshToggle() {
        const toggle = document.createElement('button');
        toggle.textContent = '🔄 Auto-uppdatering';
        toggle.className = 'yp-button yp-button-secondary';
        toggle.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
        `;
        
        toggle.addEventListener('click', () => {
            const enabled = localStorage.getItem('cookDashboardAutoRefresh') === 'true';
            localStorage.setItem('cookDashboardAutoRefresh', !enabled);
            window.location.reload();
        });
        
        document.body.appendChild(toggle);
    }

    // =========================================================================
    // Utility Functions
    // =========================================================================

    // Add smooth transitions to all interactive elements
    function enhanceInteractivity() {
        const interactiveElements = document.querySelectorAll('.meal-card, .department-card, .action-button');
        
        interactiveElements.forEach(el => {
            el.style.transition = 'all 0.3s ease';
        });
    }

    // Initialize on load
    enhanceInteractivity();

    // =========================================================================
    // Public API (for debugging)
    // =========================================================================

    window.CookDashboard = {
        scrollToLunch: () => scrollToSection('lunchSection'),
        scrollToDinner: () => scrollToSection('dinnerSection'),
        enableAutoRefresh: (minutes) => {
            localStorage.setItem('cookDashboardAutoRefresh', 'true');
            localStorage.setItem('cookDashboardRefreshInterval', (minutes * 60000).toString());
            window.location.reload();
        },
        disableAutoRefresh: () => {
            localStorage.setItem('cookDashboardAutoRefresh', 'false');
            window.location.reload();
        },
        showHelp: showKeyboardHelp
    };

})();
