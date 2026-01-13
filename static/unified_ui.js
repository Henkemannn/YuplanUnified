/**
 * Yuplan Unified - Global Interaction Patterns
 * Phase 1: Foundation - Modal focus, keyboard shortcuts, touch interactions
 * 
 * This file provides common interactive behaviors across all modules.
 * No inline JS - all event binding via addEventListener.
 */

(function() {
    'use strict';
    
    // ========================================================================
    // INITIALIZATION
    // ========================================================================
    
    /**
     * Initialize all unified UI interactions when DOM is ready
     */
    function initUnifiedUI() {
        initModalAutofocus();
        initKeyboardShortcuts();
        initTouchInteractions();
        initButtonRipple();
        initAccessibility();
    }
    
    // ========================================================================
    // MODAL AUTO-FOCUS
    // ========================================================================
    
    /**
     * Auto-focus first input in modals when they appear
     */
    function initModalAutofocus() {
        // Watch for modals with [data-modal] attribute
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                mutation.addedNodes.forEach((node) => {
                    if (node.nodeType === 1 && node.hasAttribute && node.hasAttribute('data-modal')) {
                        focusFirstInput(node);
                    }
                });
            });
        });
        
        observer.observe(document.body, {
            childList: true,
            subtree: true
        });
        
        // Also handle existing modals
        document.querySelectorAll('[data-modal]').forEach(modal => {
            focusFirstInput(modal);
        });
    }
    
    /**
     * Focus the first focusable input in a container
     */
    function focusFirstInput(container) {
        const focusable = container.querySelector(
            'input:not([type="hidden"]):not([disabled]), ' +
            'textarea:not([disabled]), ' +
            'select:not([disabled]), ' +
            'button:not([disabled])'
        );
        
        if (focusable) {
            // Delay focus to ensure modal is fully rendered
            setTimeout(() => {
                focusable.focus();
            }, 100);
        }
    }
    
    // ========================================================================
    // KEYBOARD SHORTCUTS
    // ========================================================================
    
    /**
     * Global keyboard shortcuts foundation
     * Modules can extend this by adding to keyboardShortcuts map
     */
    const keyboardShortcuts = new Map();
    
    function initKeyboardShortcuts() {
        // Register default shortcuts
        registerShortcut('Escape', handleEscape);
        registerShortcut('?', handleHelpShortcut);
        
        // Listen for keyboard events
        document.addEventListener('keydown', (e) => {
            // Don't trigger shortcuts when typing in inputs
            if (e.target.matches('input, textarea, select')) {
                // Except for Escape key
                if (e.key !== 'Escape') {
                    return;
                }
            }
            
            const key = e.shiftKey ? `Shift+${e.key}` : e.key;
            const handler = keyboardShortcuts.get(key);
            
            if (handler) {
                e.preventDefault();
                handler(e);
            }
        });
    }
    
    /**
     * Register a keyboard shortcut
     * @param {string} key - Key combination (e.g., 'Escape', 'Shift+?')
     * @param {function} handler - Function to call when key is pressed
     */
    function registerShortcut(key, handler) {
        keyboardShortcuts.set(key, handler);
    }
    
    /**
     * Expose registerShortcut globally for modules to use
     */
    window.YuplanUI = window.YuplanUI || {};
    window.YuplanUI.registerShortcut = registerShortcut;
    
    /**
     * Handle Escape key - close modals, dropdowns, etc.
     */
    function handleEscape(e) {
        // Close any open modals
        const modal = document.querySelector('[data-modal][data-open="true"]');
        if (modal) {
            const closeBtn = modal.querySelector('[data-modal-close]');
            if (closeBtn) {
                closeBtn.click();
            }
        }
        
        // Close any open dropdowns
        const dropdown = document.querySelector('[data-dropdown][data-open="true"]');
        if (dropdown) {
            dropdown.removeAttribute('data-open');
        }
    }
    
    /**
     * Handle help shortcut (Shift+?)
     */
    function handleHelpShortcut(e) {
        // Future: Show keyboard shortcuts help modal
        console.log('Keyboard shortcuts help (to be implemented)');
    }
    
    // ========================================================================
    // TOUCH INTERACTIONS
    // ========================================================================
    
    /**
     * Enhance touch interactions for tablet devices
     */
    function initTouchInteractions() {
        // Detect touch device
        const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
        
        if (isTouch) {
            document.body.classList.add('yp-touch-device');
            
            // Add touch-specific behaviors
            enhanceTouchTargets();
            preventDoubleTapZoom();
        }
    }
    
    /**
     * Ensure all interactive elements meet minimum touch target size
     */
    function enhanceTouchTargets() {
        const minSize = 44; // 44px minimum per accessibility guidelines
        
        document.querySelectorAll('.yp-btn, a, button, input, select').forEach(el => {
            const rect = el.getBoundingClientRect();
            if (rect.height < minSize || rect.width < minSize) {
                el.style.minHeight = `${minSize}px`;
                if (el.matches('button, .yp-btn')) {
                    el.style.minWidth = `${minSize}px`;
                }
            }
        });
    }
    
    /**
     * Prevent double-tap zoom on buttons (improves UX)
     */
    function preventDoubleTapZoom() {
        let lastTouchEnd = 0;
        
        document.addEventListener('touchend', (e) => {
            const now = Date.now();
            if (now - lastTouchEnd <= 300) {
                if (e.target.matches('button, .yp-btn, a')) {
                    e.preventDefault();
                }
            }
            lastTouchEnd = now;
        }, { passive: false });
    }
    
    // ========================================================================
    // BUTTON RIPPLE EFFECT (Optional, subtle enhancement)
    // ========================================================================
    
    /**
     * Add material-design-style ripple effect to buttons
     */
    function initButtonRipple() {
        // Only add ripple on non-touch devices (can be laggy on tablets)
        const isTouch = ('ontouchstart' in window) || (navigator.maxTouchPoints > 0);
        if (isTouch) return;
        
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.yp-btn, button');
            if (!btn || btn.hasAttribute('data-no-ripple')) return;
            
            createRipple(btn, e);
        });
    }
    
    /**
     * Create and animate ripple effect
     */
    function createRipple(button, event) {
        const ripple = document.createElement('span');
        const rect = button.getBoundingClientRect();
        
        const diameter = Math.max(rect.width, rect.height);
        const radius = diameter / 2;
        
        ripple.style.width = ripple.style.height = `${diameter}px`;
        ripple.style.left = `${event.clientX - rect.left - radius}px`;
        ripple.style.top = `${event.clientY - rect.top - radius}px`;
        ripple.classList.add('yp-ripple');
        
        const existingRipple = button.querySelector('.yp-ripple');
        if (existingRipple) {
            existingRipple.remove();
        }
        
        // Ensure button has position context
        if (getComputedStyle(button).position === 'static') {
            button.style.position = 'relative';
        }
        button.style.overflow = 'hidden';
        
        button.appendChild(ripple);
        
        // Remove ripple after animation
        setTimeout(() => {
            ripple.remove();
        }, 600);
    }
    
    // Add ripple CSS dynamically
    const rippleStyle = document.createElement('style');
    rippleStyle.textContent = `
        .yp-ripple {
            position: absolute;
            border-radius: 50%;
            background-color: rgba(255, 255, 255, 0.6);
            transform: scale(0);
            animation: yp-ripple-animation 0.6s ease-out;
            pointer-events: none;
        }
        
        @keyframes yp-ripple-animation {
            to {
                transform: scale(4);
                opacity: 0;
            }
        }
    `;
    document.head.appendChild(rippleStyle);
    
    // ========================================================================
    // ACCESSIBILITY ENHANCEMENTS
    // ========================================================================
    
    /**
     * Enhance accessibility features
     */
    function initAccessibility() {
        // Add keyboard navigation for custom components
        enhanceKeyboardNavigation();
        
        // Add ARIA labels where missing
        addMissingAriaLabels();
        
        // Announce dynamic content changes to screen readers
        setupLiveRegions();
    }
    
    /**
     * Enhance keyboard navigation for custom components
     */
    function enhanceKeyboardNavigation() {
        // Tab through button groups
        document.querySelectorAll('.yp-btn-group').forEach(group => {
            const buttons = group.querySelectorAll('.yp-btn, button');
            buttons.forEach((btn, index) => {
                btn.addEventListener('keydown', (e) => {
                    if (e.key === 'ArrowRight' && buttons[index + 1]) {
                        e.preventDefault();
                        buttons[index + 1].focus();
                    } else if (e.key === 'ArrowLeft' && buttons[index - 1]) {
                        e.preventDefault();
                        buttons[index - 1].focus();
                    }
                });
            });
        });
    }
    
    /**
     * Add missing ARIA labels for better screen reader support
     */
    function addMissingAriaLabels() {
        // Add aria-label to icon-only buttons
        document.querySelectorAll('.yp-btn:not([aria-label])').forEach(btn => {
            const text = btn.textContent.trim();
            if (!text && !btn.hasAttribute('aria-label')) {
                const title = btn.getAttribute('title');
                if (title) {
                    btn.setAttribute('aria-label', title);
                }
            }
        });
        
        // Add role="status" to badges
        document.querySelectorAll('.yp-badge:not([role])').forEach(badge => {
            badge.setAttribute('role', 'status');
        });
    }
    
    /**
     * Setup live regions for dynamic content announcements
     */
    function setupLiveRegions() {
        // Create a global live region for announcements
        if (!document.getElementById('yp-live-region')) {
            const liveRegion = document.createElement('div');
            liveRegion.id = 'yp-live-region';
            liveRegion.setAttribute('role', 'status');
            liveRegion.setAttribute('aria-live', 'polite');
            liveRegion.setAttribute('aria-atomic', 'true');
            liveRegion.className = 'yp-sr-only';
            document.body.appendChild(liveRegion);
        }
    }
    
    /**
     * Announce message to screen readers
     * @param {string} message - Message to announce
     */
    function announce(message) {
        const liveRegion = document.getElementById('yp-live-region');
        if (liveRegion) {
            liveRegion.textContent = message;
            // Clear after announcement
            setTimeout(() => {
                liveRegion.textContent = '';
            }, 1000);
        }
    }
    
    // Expose announce globally
    window.YuplanUI = window.YuplanUI || {};
    window.YuplanUI.announce = announce;
    
    // ========================================================================
    // UTILITY FUNCTIONS
    // ========================================================================
    
    /**
     * Debounce function for performance
     */
    function debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
    
    /**
     * Throttle function for performance
     */
    function throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }
    
    // Expose utilities globally
    window.YuplanUI = window.YuplanUI || {};
    window.YuplanUI.debounce = debounce;
    window.YuplanUI.throttle = throttle;
    
    // ========================================================================
    // INITIALIZE ON DOM READY
    // ========================================================================
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initUnifiedUI);
    } else {
        initUnifiedUI();
    }
    
})();
