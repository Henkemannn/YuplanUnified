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
        setupSiteContextWarning();
        setupSiteContextVersionSync();
        setupAdminDepartmentsCreateForm();
        
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

            // Populate menu modal if requested
            if (trigger.classList.contains('js-open-menu-modal')) {
                try {
                    const year = parseInt(trigger.getAttribute('data-year') || '0', 10);
                    const week = parseInt(trigger.getAttribute('data-week') || '0', 10);
                    const day = parseInt(trigger.getAttribute('data-day') || '0', 10);
                    const dayNames = ['Mån','Tis','Ons','Tors','Fre','Lör','Sön'];
                    const titleDayEl = dialog.querySelector('.js-menu-day-name');
                    if (titleDayEl && day >= 1 && day <= 7) {
                        titleDayEl.textContent = dayNames[day - 1];
                    }
                    const url = `/api/menu/day?year=${encodeURIComponent(year)}&week=${encodeURIComponent(week)}&day=${encodeURIComponent(day)}`;
                    fetch(url, { headers: { 'Accept': 'application/json' } })
                        .then(r => r.ok ? r.json() : Promise.reject(new Error('bad_response')))
                        .then(j => {
                            const lunch = (j && j.lunch) || { alt1_text: '', alt2_text: '', dessert: '' };
                            const dinner = (j && j.dinner) || { alt1_text: '', alt2_text: '', dessert: '' };
                            const setText = (sel, txt) => {
                                const el = dialog.querySelector(sel);
                                if (el) el.textContent = (txt && String(txt).trim()) ? String(txt) : '—';
                            };
                            const toggleRow = (rowSel, val) => {
                                const row = dialog.querySelector(rowSel);
                                if (!row) return;
                                const has = (val && String(val).trim().length > 0);
                                row.style.display = has ? '' : 'none';
                            };
                            setText('.js-menu-lunch-alt1', lunch.alt1_text || '');
                            setText('.js-menu-lunch-alt2', lunch.alt2_text || '');
                            setText('.js-menu-lunch-dessert', lunch.dessert || '');
                            setText('.js-menu-dinner-alt1', dinner.alt1_text || '');
                            setText('.js-menu-dinner-alt2', dinner.alt2_text || '');
                            setText('.js-menu-dinner-dessert', dinner.dessert || '');
                            // Hide optional rows when empty
                            toggleRow('.js-row-lunch-alt2', lunch.alt2_text || '');
                            toggleRow('.js-row-lunch-dessert', lunch.dessert || '');
                            toggleRow('.js-row-dinner-alt2', dinner.alt2_text || '');
                            toggleRow('.js-row-dinner-dessert', dinner.dessert || '');
                        })
                        .catch(() => {
                            // Leave placeholders if fetch fails
                        });
                } catch (e) {
                    // no-op
                }
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

    function getMeta(name) {
        const m = document.querySelector(`meta[name="${name}"]`);
        return m ? m.getAttribute('content') : '';
    }

    function setupSiteContextWarning() {
        try {
            const current = getMeta('current-site-id');
            const url = new URL(window.location.href);
            const qSite = (url.searchParams.get('site_id') || '').trim();
            const root = document.querySelector('.ua-root');
            const pageSite = root ? (root.getAttribute('data-page-site-id') || '').trim() : '';
            const expected = qSite || pageSite;
            if (expected && current && expected !== current) {
                // If server already rendered a banner, skip duplicating
                if (document.getElementById('site-context-banner')) return;
                const banner = document.createElement('div');
                banner.id = 'site-context-banner';
                banner.className = 'ua-flash ua-flash-warning';
                banner.setAttribute('role', 'alert');
                banner.style.margin = '8px 16px';
                banner.innerHTML = `Du har bytt arbetsplats i en annan flik. Ladda om för att se aktuell arbetsplats.
                  <button type="button" class="ua-btn ua-btn-small" style="margin-left:12px;">Ladda om</button>`;
                const btn = banner.querySelector('button');
                if (btn) btn.addEventListener('click', () => location.reload());
                const main = document.querySelector('.ua-main');
                if (main) main.prepend(banner);
            }
        } catch (e) {
            // no-op
        }
    }

    // Cross-tab site context change detection using localStorage
    function setupSiteContextVersionSync() {
        try {
            const body = document.body;
            const root = document.querySelector('.ua-root');
            // Prefer explicit version datum over site_id meta
            const currentVersion = (body && body.getAttribute('data-site-context-version'))
                || (root ? root.getAttribute('data-site-context-version') : '')
                || getMeta('current-site-id')
                || '';
            // Persist current version so other tabs can react
            if (currentVersion) {
                const prev = localStorage.getItem('site_context_version');
                if (prev !== currentVersion) {
                    localStorage.setItem('site_context_version', currentVersion);
                }
            }
            // Listen for changes from other tabs
            window.addEventListener('storage', function(e) {
                if (e.key !== 'site_context_version') return;
                const newVal = (e.newValue || '').trim();
                if (!newVal || newVal === currentVersion) return;
                // Show non-intrusive banner prompting reload (no auto-switch)
                if (document.getElementById('site-context-banner')) return;
                const banner = document.createElement('div');
                banner.id = 'site-context-banner';
                banner.className = 'ua-flash ua-flash-warning';
                banner.setAttribute('role', 'alert');
                banner.style.margin = '8px 16px';
                banner.innerHTML = `Aktiv arbetsplats har ändrats i en annan flik. Ladda om sidan för att visa rätt data.
                  <button type="button" class="ua-btn ua-btn-small" style="margin-left:12px;">Ladda om</button>`;
                const btn = banner.querySelector('button');
                if (btn) btn.addEventListener('click', () => location.reload());
                const main = document.querySelector('.ua-main');
                if (main) main.prepend(banner);
            });
        } catch (e) {
            // no-op
        }
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
    // Departments Create Form (CSP-safe toggles)
    // ========================================================================
    function setupAdminDepartmentsCreateForm() {
        const form = document.querySelector('form.department-form#department-create-form');
        const createModal = document.getElementById('residents-variation-modal-create');
        if (!form) return; // Only on create/edit page

        // Toggle fixed/variable required state without inline styles
        function updateMode() {
            const checked = form.querySelector('input[name="resident_count_mode_choice"]:checked');
            const mode = checked ? checked.value : 'fixed';
            const fixedInput = form.querySelector('.js-fixed-input');
            if (fixedInput) {
                if (mode === 'fixed') {
                    fixedInput.removeAttribute('disabled');
                    fixedInput.setAttribute('required', 'required');
                } else {
                    fixedInput.removeAttribute('required');
                }
            }
        }

        // Toggle week selector visibility by class + disable inputs
        function updateWeekScope() {
            if (!createModal) return;
            const scopeInput = createModal.querySelector('input[name="variation_scope_create"]:checked');
            const scope = scopeInput ? scopeInput.value : 'forever';
            const sel = createModal.querySelector('.js-week-selector');
            if (!sel) return;
            const isWeek = scope === 'week';
            sel.classList.toggle('is-hidden', !isWeek);
            sel.setAttribute('aria-hidden', isWeek ? 'false' : 'true');
            sel.querySelectorAll('input, select').forEach(el => {
                if (isWeek) el.removeAttribute('disabled');
                else el.setAttribute('disabled', 'disabled');
            });
        }

        // Bind events
        form.addEventListener('change', function (ev) {
            if (ev.target && ev.target.name === 'resident_count_mode_choice') {
                updateMode();
            }
        });
        if (createModal) {
            createModal.addEventListener('change', function (ev) {
                if (ev.target && ev.target.name === 'variation_scope_create') {
                    updateWeekScope();
                }
            });
        }

        // Initial state
        updateMode();
        updateWeekScope();
    }
    
    // ========================================================================
    // Auto-init on DOM ready
    // ========================================================================
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})();
