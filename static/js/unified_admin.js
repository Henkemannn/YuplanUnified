/**
 * Unified Admin Panel - JavaScript
 * Phase 1: Navigation shell and interactive features
 */

(function() {
    'use strict';
    
    // ========================================================================
    // State
    // ========================================================================
    
    let sidebarOpen = true;
    
    // ========================================================================
    // Initialization
    // ========================================================================
    
    function init() {
        setupSidebarToggle();
        setupFlashClose();
        setupKeyboardShortcuts();
        setupButtonRipple();
        setupSmoothTableHover();
        setupSmoothScroll();
        setupModalHandlers();
        
        // Check mobile on load
        if (window.innerWidth <= 768) {
            sidebarOpen = false;
            closeSidebar();
        }
    }
    
    // ========================================================================
    // Sidebar Toggle
    // ========================================================================
    
    function setupSidebarToggle() {
        const mobileToggle = document.getElementById('mobileMenuToggle');
        const sidebarToggle = document.getElementById('sidebarToggle');
        
        if (mobileToggle) {
            mobileToggle.addEventListener('click', toggleSidebar);
        }
        
        if (sidebarToggle) {
            sidebarToggle.addEventListener('click', toggleSidebar);
        }
        
        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', function(e) {
            if (window.innerWidth <= 768 && sidebarOpen) {
                const sidebar = document.getElementById('adminSidebar');
                const mobileToggle = document.getElementById('mobileMenuToggle');
                
                if (sidebar && 
                    !sidebar.contains(e.target) && 
                    e.target !== mobileToggle &&
                    !mobileToggle.contains(e.target)) {
                    closeSidebar();
                }
            }
        });
    }
    
    // ========================================================================
    // Modal Handlers (data-modal-target / data-modal-close)
    // ========================================================================
    function setupModalHandlers() {
        // Open handler
        document.addEventListener('click', function (event) {
            const trigger = event.target.closest('[data-modal-target]');
            if (!trigger) return;

            const selector = trigger.getAttribute('data-modal-target');
            if (!selector) return;

            const dialog = document.querySelector(selector);
            if (!dialog) return;

            try {
                if (typeof dialog.showModal === 'function') {
                    dialog.showModal();
                    dialog.classList.add('ua-modal-open');
                } else {
                    dialog.setAttribute('open', 'open');
                    dialog.classList.add('ua-modal-open');
                }
            } catch (e) {
                dialog.setAttribute('open', 'open');
                dialog.classList.add('ua-modal-open');
            }
        });

        // Close handler
        document.addEventListener('click', function (event) {
            const closeBtn = event.target.closest('[data-modal-close]');
            if (!closeBtn) return;

            const dialog = closeBtn.closest('dialog.ua-modal');
            if (!dialog) return;

            try {
                if (typeof dialog.close === 'function') {
                    dialog.close();
                } else {
                    dialog.removeAttribute('open');
                }
            } catch (e) {
                dialog.removeAttribute('open');
            }
            dialog.classList.remove('ua-modal-open');
        });
    }

    function toggleSidebar() {
        if (sidebarOpen) {
            closeSidebar();
        } else {
            openSidebar();
        }
    }
    
    function openSidebar() {
        const sidebar = document.getElementById('adminSidebar');
        if (sidebar) {
            sidebar.classList.add('is-open');
            sidebarOpen = true;
        }
    }
    
    function closeSidebar() {
        const sidebar = document.getElementById('adminSidebar');
        if (sidebar) {
            sidebar.classList.remove('is-open');
            sidebarOpen = false;
        }
    }
    
    // ========================================================================
    // Flash Messages
    // ========================================================================
    
    function setupFlashClose() {
        const closeButtons = document.querySelectorAll('.flash-close');
        
        closeButtons.forEach(function(btn) {
            btn.addEventListener('click', function() {
                const flash = btn.closest('.flash');
                if (flash) {
                    flash.style.opacity = '0';
                    flash.style.transform = 'translateY(-10px)';
                    flash.style.transition = 'opacity 200ms ease, transform 200ms ease';
                    
                    setTimeout(function() {
                        flash.remove();
                    }, 200);
                }
            });
        });
        
        // Auto-dismiss success messages after 5 seconds
        const successFlashes = document.querySelectorAll('.flash-success');
        successFlashes.forEach(function(flash) {
            setTimeout(function() {
                const closeBtn = flash.querySelector('.flash-close');
                if (closeBtn) {
                    closeBtn.click();
                }
            }, 5000);
        });
    }
    
    // ========================================================================
    // Keyboard Shortcuts
    // ========================================================================
    
    function setupKeyboardShortcuts() {
        document.addEventListener('keydown', function(e) {
            // Don't trigger shortcuts when typing in input fields
            if (e.target.tagName === 'INPUT' || 
                e.target.tagName === 'TEXTAREA' || 
                e.target.isContentEditable) {
                return;
            }
            
            // ESC - Close sidebar on mobile
            if (e.key === 'Escape' && window.innerWidth <= 768 && sidebarOpen) {
                closeSidebar();
            }
            
            // M - Toggle sidebar on mobile
            if (e.key === 'm' || e.key === 'M') {
                if (window.innerWidth <= 768) {
                    toggleSidebar();
                }
            }
        });
    }
    
    // ========================================================================
    // Utility Functions
    // ========================================================================
    
    function getCsrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : '';
    }
    
    // ========================================================================
    // Button Ripple Effect
    // ========================================================================
    
    function setupButtonRipple() {
        const buttons = document.querySelectorAll('.yp-button, button[class*="yp-button"]');
        
        buttons.forEach(function(button) {
            button.addEventListener('click', function(e) {
                // Create ripple element
                const ripple = document.createElement('span');
                ripple.classList.add('ripple');
                
                // Calculate position
                const rect = button.getBoundingClientRect();
                const size = Math.max(rect.width, rect.height);
                const x = e.clientX - rect.left - size / 2;
                const y = e.clientY - rect.top - size / 2;
                
                // Style ripple
                ripple.style.width = ripple.style.height = size + 'px';
                ripple.style.left = x + 'px';
                ripple.style.top = y + 'px';
                
                // Add to button
                button.style.position = 'relative';
                button.style.overflow = 'hidden';
                button.appendChild(ripple);
                
                // Remove after animation
                setTimeout(function() {
                    ripple.remove();
                }, 600);
            });
        });
    }
    
    // ========================================================================
    // Smooth Table Hover Transitions
    // ========================================================================
    
    function setupSmoothTableHover() {
        const tables = document.querySelectorAll('.yp-table');
        
        tables.forEach(function(table) {
            const rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(function(row) {
                // Add smooth transition
                row.style.transition = 'background-color 200ms ease, transform 100ms ease';
                
                // Add subtle scale on click
                row.addEventListener('mousedown', function() {
                    row.style.transform = 'scale(0.995)';
                });
                
                row.addEventListener('mouseup', function() {
                    row.style.transform = 'scale(1)';
                });
                
                row.addEventListener('mouseleave', function() {
                    row.style.transform = 'scale(1)';
                });
            });
        });
    }
    
    // ========================================================================
    // Smooth Scroll for Long Tables
    // ========================================================================
    
    function setupSmoothScroll() {
        // Smooth scroll for anchor links
        const anchorLinks = document.querySelectorAll('a[href^="#"]');
        
        anchorLinks.forEach(function(link) {
            link.addEventListener('click', function(e) {
                const href = link.getAttribute('href');
                if (href === '#') return;
                
                const target = document.querySelector(href);
                if (target) {
                    e.preventDefault();
                    target.scrollIntoView({
                        behavior: 'smooth',
                        block: 'start'
                    });
                }
            });
        });
        
        // Add "Back to top" functionality if page is long
        if (document.body.scrollHeight > window.innerHeight * 2) {
            addBackToTopButton();
        }
    }
    
    function addBackToTopButton() {
        const button = document.createElement('button');
        button.innerHTML = '↑';
        button.className = 'yp-button yp-button-secondary back-to-top';
        button.setAttribute('aria-label', 'Back to top');
        button.style.cssText = `
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            opacity: 0;
            pointer-events: none;
            transition: opacity 300ms ease, transform 300ms ease;
            z-index: 1000;
            box-shadow: var(--yp-shadow-lg);
        `;
        
        document.body.appendChild(button);
        
        // Show/hide based on scroll
        window.addEventListener('scroll', function() {
            if (window.scrollY > 300) {
                button.style.opacity = '1';
                button.style.pointerEvents = 'auto';
            } else {
                button.style.opacity = '0';
                button.style.pointerEvents = 'none';
            }
        });
        
        // Scroll to top
        button.addEventListener('click', function() {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
    
    // ========================================================================
    // Public API (for future use)
    // ========================================================================
    
    window.UnifiedAdmin = {
        openSidebar: openSidebar,
        closeSidebar: closeSidebar,
        toggleSidebar: toggleSidebar,
        getCsrfToken: getCsrfToken
    };
    
    // ========================================================================
    // Auto-init on DOM ready
    // ========================================================================
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})();
