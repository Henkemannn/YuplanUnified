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
        setupReportWeeklyAutosubmit();
        
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
    function escapeHtml(value) {
        return String(value || '').replace(/[&<>"']/g, function(character) {
            return {
                '&': '&amp;',
                '<': '&lt;',
                '>': '&gt;',
                '"': '&quot;',
                "'": '&#39;'
            }[character];
        });
    }

    function setupModalHandlers() {
        let activeNeedPickerDialog = null;
        let activeNeedPickerTrigger = null;

        function updateNeedModalChips(dialog) {
            const chipsNode = dialog.querySelector('[data-need-selected-modifiers]');
            const modifierSelect = dialog.querySelector('select[name="modifier_requirement_ids"]');
            const pickerToggle = dialog.querySelector('[data-need-picker-toggle]');
            if (!chipsNode || !modifierSelect) {
                return;
            }
            const selectedOptions = Array.from(modifierSelect.options).filter(function(option) {
                return option.selected && option.value;
            });
            if (!selectedOptions.length) {
                if (pickerToggle) {
                    pickerToggle.textContent = '+ Lägg till kostbehov';
                }
                chipsNode.innerHTML = '';
                return;
            }
            chipsNode.innerHTML = selectedOptions.map(function(option) {
                return '<span class="admin-need-modal__chip">' + escapeHtml(option.textContent || option.value) + '<button type="button" class="admin-need-modal__chip-remove" data-need-chip-remove="' + escapeHtml(option.value) + '" aria-label="Ta bort ' + escapeHtml(option.textContent || option.value) + '">×</button></span>';
            }).join('');
            if (pickerToggle) {
                pickerToggle.textContent = '+ Lägg till kostbehov';
            }
            updateNeedPickerCount(dialog);
            syncNeedPickerSelection(dialog);
        }

        function getNeedPickerNodes(dialog) {
            if (!dialog || !dialog.querySelector) {
                return {
                    pickerNode: null,
                    pickerPanel: null,
                    pickerSearch: null,
                    pickerList: null,
                    pickerCount: null,
                    pickerEmpty: null,
                    pickerToggle: null,
                    modifierSelect: null,
                };
            }
            const pickerNode = dialog.querySelector('[data-need-picker]');
            const pickerPanel = pickerNode ? pickerNode.querySelector('[data-need-picker-panel]') : null;
            const pickerSearch = dialog.querySelector('[data-need-picker-search]');
            const pickerList = dialog.querySelector('[data-need-picker-list]');
            const pickerCount = dialog.querySelector('[data-need-picker-count]');
            const pickerEmpty = dialog.querySelector('[data-need-picker-empty]');
            const pickerToggle = dialog.querySelector('[data-need-picker-toggle]');
            const modifierSelect = dialog.querySelector('select[name="modifier_requirement_ids"]');
            return { pickerNode, pickerPanel, pickerSearch, pickerList, pickerCount, pickerEmpty, pickerToggle, modifierSelect };
        }

        function getNeedRemoveNodes(dialog) {
            if (!dialog || !dialog.querySelector) {
                return {
                    editForm: null,
                    removeForm: null,
                    editState: null,
                    removeState: null,
                    removeStart: null,
                    removeCancel: null,
                    removeConfirm: null,
                    removeLabel: null,
                };
            }
            return {
                editForm: dialog.querySelector('.admin-need-modal__edit-form'),
                removeForm: dialog.querySelector('[data-need-remove-form]'),
                editState: dialog.querySelector('[data-need-edit-state]'),
                removeState: dialog.querySelector('[data-need-remove-state]'),
                removeStart: dialog.querySelector('[data-need-remove-start]'),
                removeCancel: dialog.querySelector('[data-need-remove-cancel]'),
                removeConfirm: dialog.querySelector('[data-need-remove-confirm]'),
                removeLabel: dialog.querySelector('[data-need-remove-label]'),
            };
        }

        function setNeedRemoveState(dialog, active, labelText) {
            const nodes = getNeedRemoveNodes(dialog);
            const isEditMode = !!dialog && dialog.dataset && dialog.dataset.needMode === 'edit' && !!dialog.dataset.needGroupId;
            if (active && !isEditMode) {
                active = false;
            }
            if (dialog && dialog.classList) {
                dialog.classList.toggle('is-need-remove-open', !!active);
            }
            if (nodes.editForm) {
                nodes.editForm.hidden = !!active;
            }
            if (nodes.removeForm) {
                nodes.removeForm.hidden = !active;
            }
            if (nodes.editState) {
                nodes.editState.hidden = !!active;
            }
            if (nodes.removeState) {
                nodes.removeState.hidden = !active;
            }
            if (nodes.removeLabel && labelText) {
                nodes.removeLabel.textContent = labelText;
            }
            if (active && nodes.removeConfirm && typeof nodes.removeConfirm.focus === 'function') {
                nodes.removeConfirm.focus();
            }
        }

        function closeNeedModal(dialog) {
            if (!dialog) {
                return;
            }
            closeNeedPicker(dialog, false);
            setNeedRemoveState(dialog, false, '');
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
            dialog.classList.remove('is-need-remove-open');
            dialog.dataset.needMode = 'create';
            dialog.dataset.needGroupId = '';
        }

        function getNeedPickerOptions(dialog) {
            const nodes = getNeedPickerNodes(dialog);
            if (!nodes.modifierSelect) {
                return [];
            }
            return Array.from(nodes.modifierSelect.options).filter(function(option) {
                return !!option.value;
            });
        }

        function updateNeedPickerCount(dialog) {
            const nodes = getNeedPickerNodes(dialog);
            if (!nodes.pickerCount || !nodes.modifierSelect) {
                return;
            }
            const selectedCount = Array.from(nodes.modifierSelect.options).filter(function(option) {
                return option.selected && !!option.value;
            }).length;
            nodes.pickerCount.textContent = selectedCount + ' valda';
        }

        function syncNeedPickerSelection(dialog) {
            const nodes = getNeedPickerNodes(dialog);
            if (!nodes.pickerList || !nodes.modifierSelect) {
                return;
            }
            const selectedValues = new Set(Array.from(nodes.modifierSelect.options).filter(function(option) {
                return option.selected && !!option.value;
            }).map(function(option) {
                return String(option.value);
            }));
            nodes.pickerList.querySelectorAll('[data-need-picker-option]').forEach(function(optionButton) {
                const optionValue = String(optionButton.getAttribute('data-need-picker-option') || '');
                const isSelected = selectedValues.has(optionValue);
                optionButton.classList.toggle('is-selected', isSelected);
                optionButton.setAttribute('aria-pressed', isSelected ? 'true' : 'false');
            });
            if (nodes.pickerEmpty) {
                const visibleOptions = Array.from(nodes.pickerList.querySelectorAll('[data-need-picker-option]')).filter(function(optionButton) {
                    return !optionButton.hidden;
                });
                nodes.pickerEmpty.hidden = visibleOptions.length > 0;
            }
            updateNeedPickerCount(dialog);
        }

        function renderNeedPickerOptions(dialog) {
            const nodes = getNeedPickerNodes(dialog);
            if (!nodes.pickerList || !nodes.modifierSelect) {
                return;
            }
            nodes.pickerList.innerHTML = '';
            getNeedPickerOptions(dialog).forEach(function(option) {
                const button = document.createElement('button');
                button.type = 'button';
                button.className = 'admin-need-modal__picker-option';
                button.setAttribute('data-need-picker-option', String(option.value));
                button.setAttribute('aria-pressed', option.selected ? 'true' : 'false');
                const labelWrap = document.createElement('span');
                labelWrap.className = 'admin-need-modal__picker-option-label';
                const title = document.createElement('span');
                title.className = 'admin-need-modal__picker-option-title';
                title.textContent = option.textContent || option.value;
                const check = document.createElement('span');
                check.className = 'admin-need-modal__picker-option-check';
                labelWrap.appendChild(title);
                button.appendChild(labelWrap);
                button.appendChild(check);
                nodes.pickerList.appendChild(button);
            });
            updateNeedPickerCount(dialog);
            syncNeedPickerSelection(dialog);
        }

        function filterNeedPickerOptions(dialog, query) {
            const nodes = getNeedPickerNodes(dialog);
            if (!nodes.pickerList) {
                return;
            }
            const normalizedQuery = String(query || '').trim().toLowerCase();
            nodes.pickerList.querySelectorAll('[data-need-picker-option]').forEach(function(optionButton) {
                const optionLabel = String(optionButton.textContent || '').trim().toLowerCase();
                optionButton.hidden = !!normalizedQuery && optionLabel.indexOf(normalizedQuery) === -1;
            });
            if (nodes.pickerEmpty) {
                const visibleOptions = Array.from(nodes.pickerList.querySelectorAll('[data-need-picker-option]')).filter(function(optionButton) {
                    return !optionButton.hidden;
                });
                nodes.pickerEmpty.hidden = visibleOptions.length > 0;
            }
        }

        function positionNeedPicker(dialog) {
            const nodes = getNeedPickerNodes(dialog);
            if (!nodes.pickerNode || !nodes.pickerPanel) {
                return;
            }
            dialog.classList.add('is-need-picker-open');
            nodes.pickerNode.style.position = 'fixed';
            nodes.pickerNode.style.inset = '0';
            nodes.pickerNode.style.display = 'grid';
            nodes.pickerNode.style.placeItems = 'center';
            nodes.pickerNode.style.pointerEvents = 'auto';
            nodes.pickerNode.style.zIndex = '1060';
            nodes.pickerNode.dataset.needPickerPlacement = 'center';
            nodes.pickerNode.hidden = false;
            nodes.pickerNode.removeAttribute('aria-hidden');

            nodes.pickerPanel.style.left = '';
            nodes.pickerPanel.style.top = '';
            nodes.pickerPanel.style.width = '';
            nodes.pickerPanel.style.maxWidth = '';
            nodes.pickerPanel.style.maxHeight = '';
            nodes.pickerPanel.dataset.needPickerPlacement = 'center';
            nodes.pickerPanel.style.visibility = 'visible';
        }

        function openNeedPicker(dialog, trigger) {
            const nodes = getNeedPickerNodes(dialog);
            if (!nodes.pickerNode) {
                return;
            }
            activeNeedPickerDialog = dialog;
            activeNeedPickerTrigger = trigger;
            renderNeedPickerOptions(dialog);
            if (nodes.pickerSearch) {
                nodes.pickerSearch.value = '';
            }
            nodes.pickerNode.hidden = false;
            nodes.pickerNode.setAttribute('aria-hidden', 'false');
            if (nodes.pickerPanel) {
                nodes.pickerPanel.style.visibility = 'hidden';
            }
            requestAnimationFrame(function() {
                if (activeNeedPickerDialog !== dialog) {
                    return;
                }
                positionNeedPicker(dialog);
                if (nodes.pickerSearch && typeof nodes.pickerSearch.focus === 'function') {
                    nodes.pickerSearch.focus();
                }
            });
        }

        function closeNeedPicker(dialog, restoreFocus) {
            const nodes = getNeedPickerNodes(dialog);
            if (!nodes.pickerNode) {
                return;
            }
            dialog.classList.remove('is-need-picker-open');
            nodes.pickerNode.hidden = true;
            nodes.pickerNode.setAttribute('aria-hidden', 'true');
            nodes.pickerNode.style.pointerEvents = '';
            nodes.pickerNode.style.display = '';
            nodes.pickerNode.style.placeItems = '';
            if (nodes.pickerPanel) {
                nodes.pickerPanel.removeAttribute('data-need-picker-placement');
                nodes.pickerPanel.style.left = '';
                nodes.pickerPanel.style.top = '';
                nodes.pickerPanel.style.width = '';
                nodes.pickerPanel.style.maxWidth = '';
                nodes.pickerPanel.style.maxHeight = '';
                nodes.pickerPanel.style.visibility = '';
            }
            if (restoreFocus && nodes.pickerToggle && typeof nodes.pickerToggle.focus === 'function') {
                nodes.pickerToggle.focus();
            }
            if (activeNeedPickerDialog === dialog) {
                activeNeedPickerDialog = null;
                activeNeedPickerTrigger = null;
            }
        }

        function parseVariationNumber(value) {
            const parsed = parseInt(String(value == null ? '' : value).trim() || '0', 10);
            return Number.isFinite(parsed) && parsed >= 0 ? parsed : 0;
        }

        function syncVariationResidentDelta(input) {
            if (!input || !input.name) {
                return;
            }
            const match = /^need_day_(.+)_(\d+)_(lunch|dinner)$/.exec(String(input.name));
            if (!match) {
                return;
            }
            const form = input.closest('#residents-variation-form');
            if (!form) {
                return;
            }
            const weekday = match[2];
            const mealKey = match[3];
            const residentInput = form.querySelector('input[name="day_' + weekday + '_' + mealKey + '"]');
            if (!residentInput) {
                return;
            }
            const previousValue = input.dataset.variationDeltaValue == null
                ? parseVariationNumber(input.value)
                : parseVariationNumber(input.dataset.variationDeltaValue);
            const nextValue = parseVariationNumber(input.value);
            const residentValue = parseVariationNumber(residentInput.value);
            const nextResidentValue = Math.max(0, residentValue + (nextValue - previousValue));
            residentInput.value = String(nextResidentValue);
            input.dataset.variationDeltaValue = String(nextValue);
        }

        function seedVariationResidentDelta(form) {
            if (!form || !form.querySelectorAll) {
                return;
            }
            form.querySelectorAll('input[type="number"][name^="need_day_"]').forEach(function(input) {
                input.dataset.variationDeltaValue = String(parseVariationNumber(input.value));
            });
        }

        function toggleNeedPickerOption(dialog, value) {
            const nodes = getNeedPickerNodes(dialog);
            if (!nodes.modifierSelect) {
                return;
            }
            const option = Array.from(nodes.modifierSelect.options).find(function(candidate) {
                return String(candidate.value) === String(value);
            });
            if (!option || !option.value) {
                return;
            }
            option.selected = !option.selected;
            updateNeedModalChips(dialog);
            syncNeedPickerSelection(dialog);
            filterNeedPickerOptions(dialog, nodes.pickerSearch ? nodes.pickerSearch.value : '');
        }

        function syncNeedModal(dialog, trigger) {
            const form = dialog.querySelector('form');
            const titleNode = dialog.querySelector('[data-need-modal-title]');
            const subtitleNode = dialog.querySelector('[data-need-modal-subtitle]');
            const groupIdInput = dialog.querySelector('input[name="group_id"]');
            const primarySelect = dialog.querySelector('select[name="primary_requirement_id"]');
            const modifierSelect = dialog.querySelector('select[name="modifier_requirement_ids"]');
            const quantityInput = dialog.querySelector('input[name="default_quantity"]');
            const pickerNode = dialog.querySelector('[data-need-picker]');
            const pickerSearch = dialog.querySelector('[data-need-picker-search]');
            const removeNodes = getNeedRemoveNodes(dialog);
            const mode = (trigger.getAttribute('data-need-mode') || (trigger.getAttribute('data-need-group-id') ? 'edit' : 'create') || 'create').toLowerCase();
            const groupLabel = (trigger.getAttribute('data-need-label') || '').trim();
            const groupId = (trigger.getAttribute('data-need-group-id') || '').trim();
            const primaryId = (trigger.getAttribute('data-need-primary-id') || '').trim();
            const modifierIds = (trigger.getAttribute('data-need-modifier-ids') || '').split(',').map(function(item) { return item.trim(); }).filter(Boolean);
            const defaultQuantity = (trigger.getAttribute('data-need-default-quantity') || '1').trim();
            const removeLabel = groupLabel || 'detta kostbehov';

            if (form && typeof form.reset === 'function') {
                form.reset();
            }
            closeNeedPicker(dialog, false);
            dialog.dataset.needMode = mode;
            dialog.dataset.needGroupId = groupId;
            if (dialog && dialog.classList) {
                dialog.classList.remove('is-need-remove-open');
            }
            if (groupIdInput) {
                groupIdInput.value = mode === 'edit' ? groupId : '';
            }
            if (titleNode) {
                titleNode.textContent = mode === 'edit' ? 'Redigera kostbehov' : 'Lägg till kostbehov';
            }
            if (subtitleNode) {
                subtitleNode.textContent = mode === 'edit'
                    ? (groupLabel ? groupLabel : 'Uppdatera det registrerade kostbehovet.')
                    : 'Vilket kostbehov gäller?';
            }
            if (primarySelect) {
                primarySelect.value = primaryId;
                if (!primarySelect.value && primarySelect.options.length) {
                    primarySelect.selectedIndex = 0;
                }
            }
            if (modifierSelect) {
                Array.from(modifierSelect.options).forEach(function(option) {
                    option.selected = modifierIds.includes(String(option.value));
                });
            }
            if (quantityInput) {
                quantityInput.value = defaultQuantity || '1';
            }
            if (pickerNode) {
                pickerNode.hidden = true;
                pickerNode.removeAttribute('data-need-picker-placement');
                pickerNode.setAttribute('aria-hidden', 'true');
                pickerNode.style.pointerEvents = '';
                dialog.classList.remove('is-need-picker-open');
            }
            if (pickerSearch) {
                pickerSearch.value = '';
            }
            const removeGroupIdInput = dialog.querySelector('[data-need-remove-form] input[name="group_id"]');
            if (removeNodes.removeStart) {
                removeNodes.removeStart.hidden = mode !== 'edit';
            }
            if (removeGroupIdInput) {
                removeGroupIdInput.value = mode === 'edit' ? groupId : '';
            }
            dialog.dataset.needRemoveLabel = removeLabel;
            setNeedRemoveState(dialog, false, removeLabel);
            updateNeedModalChips(dialog);
            renderNeedPickerOptions(dialog);
            const firstField = primarySelect || dialog.querySelector('input, select, textarea');
            if (firstField && typeof firstField.focus === 'function') {
                firstField.focus();
            }
        }

        function closeDialog(dialog) {
            if (!dialog) {
                return;
            }
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
        }

        const autoOpenNeedConflict = document.querySelector('[data-auto-open-need-conflict]');
        if (autoOpenNeedConflict) {
            autoOpenNeedConflict.click();
        }

        // Open handler
        document.addEventListener('click', function (event) {
            const trigger = event.target.closest('[data-modal-target]');
            if (!trigger) return;

            const selector = trigger.getAttribute('data-modal-target');
            if (!selector) return;

            const dialog = document.querySelector(selector);
            if (!dialog) return;

            const variationTitle = trigger.getAttribute('data-variation-title');
            const variationFocusGroupId = trigger.getAttribute('data-variation-focus-group-id');
            const titleNode = dialog.querySelector('[data-variation-modal-title]');
            const subtitleNode = dialog.querySelector('[data-variation-modal-subtitle]');
            const focusGroupInput = dialog.querySelector('input[name="variation_focus_group_id"]');
            const residentCountOverride = trigger.getAttribute('data-department-resident-count');

            if (trigger.getAttribute('data-conflict-dismiss') === 'true') {
                const conflictDialog = trigger.closest('dialog.ua-modal');
                if (conflictDialog && conflictDialog.id === 'need-conflict-modal') {
                    closeDialog(conflictDialog);
                }
            }
            if (titleNode && variationTitle) {
                titleNode.textContent = variationTitle;
            }
            if (subtitleNode && variationTitle) {
                subtitleNode.textContent = 'Mån-Sön · Lunch/Kväll';
            }
            if (focusGroupInput) {
                focusGroupInput.value = variationFocusGroupId || '';
            }
            if (residentCountOverride && dialog.id === 'department-edit-modal') {
                const residentInput = dialog.querySelector('#department-edit-resident-count');
                if (residentInput) {
                    residentInput.value = residentCountOverride;
                }
            }

            if (dialog.id === 'need-modal') {
                closeNeedPicker(dialog, false);
                syncNeedModal(dialog, trigger);
            }
            if (dialog.id === 'residents-variation-modal') {
                seedVariationResidentDelta(dialog.querySelector('#residents-variation-form'));
            }

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

            if (dialog.id === 'need-modal') {
                closeNeedModal(dialog);
            } else if (dialog.id === 'need-conflict-modal') {
                closeDialog(dialog);
            } else {
                closeDialog(dialog);
            }

            const titleNode = dialog.querySelector('[data-variation-modal-title]');
            const subtitleNode = dialog.querySelector('[data-variation-modal-subtitle]');
            const focusGroupInput = dialog.querySelector('input[name="variation_focus_group_id"]');
            if (titleNode) {
                titleNode.textContent = 'Varierat boendeantal';
            }
            if (subtitleNode) {
                subtitleNode.textContent = 'Mån-Sön · Lunch/Kväll';
            }
            if (focusGroupInput) {
                focusGroupInput.value = '';
            }
        });

        document.addEventListener('click', function (event) {
            const removeStart = event.target.closest('[data-need-remove-start]');
            if (removeStart) {
                const dialog = removeStart.closest('dialog');
                if (dialog && dialog.dataset.needMode === 'edit' && dialog.dataset.needGroupId) {
                    const labelText = (dialog.dataset.needRemoveLabel || '').trim();
                    setNeedRemoveState(dialog, true, labelText || 'detta kostbehov');
                }
                event.preventDefault();
                event.stopPropagation();
                return;
            }

            const removeCancel = event.target.closest('[data-need-remove-cancel]');
            if (removeCancel) {
                const dialog = removeCancel.closest('dialog');
                if (dialog) {
                    setNeedRemoveState(dialog, false, '');
                }
                event.preventDefault();
                event.stopPropagation();
                return;
            }

            const removeConfirm = event.target.closest('[data-need-remove-confirm]');
            if (removeConfirm) {
                return;
            }
        });

        document.addEventListener('change', function (event) {
            const modifierSelect = event.target;
            if (!modifierSelect || !modifierSelect.matches || !modifierSelect.matches('#need-modal select[name="modifier_requirement_ids"]')) return;
            const dialog = modifierSelect.closest('dialog');
            if (dialog) {
                updateNeedModalChips(dialog);
            }
        });

        document.addEventListener('input', function (event) {
            const target = event.target;
            if (!target || !target.matches || !target.matches('#residents-variation-form input[type="number"][name^="need_day_"]')) {
                return;
            }
            syncVariationResidentDelta(target);
        });

        seedVariationResidentDelta(document.querySelector('#residents-variation-form'));

        document.addEventListener('click', function (event) {
            const pickerOption = event.target.closest('[data-need-picker-option]');
            if (pickerOption) {
                const dialog = pickerOption.closest('dialog');
                const value = pickerOption.getAttribute('data-need-picker-option');
                if (dialog && value) {
                    toggleNeedPickerOption(dialog, value);
                }
                event.preventDefault();
                event.stopPropagation();
                return;
            }

            const chipRemove = event.target.closest('[data-need-chip-remove]');
            if (chipRemove) {
                const dialog = chipRemove.closest('dialog');
                const modifierSelect = dialog ? dialog.querySelector('select[name="modifier_requirement_ids"]') : null;
                if (dialog && modifierSelect) {
                    const value = String(chipRemove.getAttribute('data-need-chip-remove') || '');
                    Array.from(modifierSelect.options).forEach(function(option) {
                        if (String(option.value) === value) {
                            option.selected = false;
                        }
                    });
                    updateNeedModalChips(dialog);
                    syncNeedPickerSelection(dialog);
                }
                event.preventDefault();
                event.stopPropagation();
                return;
            }

            const pickerClose = event.target.closest('[data-need-picker-close]');
            if (pickerClose) {
                const dialog = pickerClose.closest('dialog');
                closeNeedPicker(dialog, true);
                const pickerToggle = dialog ? dialog.querySelector('[data-need-picker-toggle]') : null;
                if (pickerToggle) {
                    pickerToggle.setAttribute('aria-expanded', 'false');
                }
                event.preventDefault();
                event.stopPropagation();
                return;
            }

            const pickerOverlay = event.target.closest('[data-need-picker]');
            if (pickerOverlay && event.target === pickerOverlay) {
                const dialog = pickerOverlay.closest('dialog');
                closeNeedPicker(dialog, true);
                const pickerToggle = dialog ? dialog.querySelector('[data-need-picker-toggle]') : null;
                if (pickerToggle) {
                    pickerToggle.setAttribute('aria-expanded', 'false');
                }
                event.preventDefault();
                event.stopPropagation();
                return;
            }

            const pickerToggle = event.target.closest('[data-need-picker-toggle]');
            if (pickerToggle) {
                const dialog = pickerToggle.closest('dialog');
                const pickerNode = dialog ? dialog.querySelector('[data-need-picker]') : null;
                if (pickerNode) {
                    const shouldOpen = pickerNode.hidden;
                    if (shouldOpen) {
                        pickerToggle.setAttribute('aria-expanded', 'true');
                        openNeedPicker(dialog, pickerToggle);
                    } else {
                        pickerToggle.setAttribute('aria-expanded', 'false');
                        closeNeedPicker(dialog, true);
                    }
                }
                event.preventDefault();
                event.stopPropagation();
                return;
            }

            const openPicker = event.target.closest('[data-need-picker]');
            if (openPicker && event.target === openPicker) {
                const dialog = openPicker.closest('dialog');
                closeNeedPicker(dialog, true);
                const pickerToggle = dialog ? dialog.querySelector('[data-need-picker-toggle]') : null;
                if (pickerToggle) {
                    pickerToggle.setAttribute('aria-expanded', 'false');
                }
                event.preventDefault();
                event.stopPropagation();
                return;
            }
            if (openPicker) {
                event.stopPropagation();
                return;
            }

            document.querySelectorAll('dialog.ua-modal [data-need-picker]').forEach(function(pickerNode) {
                if (pickerNode.hidden) {
                    return;
                }
                const dialog = pickerNode.closest('dialog');
                const toggle = dialog ? dialog.querySelector('[data-need-picker-toggle]') : null;
                if (dialog && !pickerNode.contains(event.target) && !(toggle && toggle.contains(event.target))) {
                    if (toggle) {
                        toggle.setAttribute('aria-expanded', 'false');
                    }
                    closeNeedPicker(dialog, false);
                }
            });
        });

        document.addEventListener('input', function (event) {
            const searchInput = event.target;
            if (!searchInput || !searchInput.matches || !searchInput.matches('[data-need-picker-search]')) return;
            const dialog = searchInput.closest('dialog');
            if (!dialog) return;
            filterNeedPickerOptions(dialog, searchInput.value || '');
        });

        document.addEventListener('keydown', function (event) {
            if (event.key !== 'Escape') {
                return;
            }
            const openPicker = document.querySelector('dialog.ua-modal [data-need-picker]:not([hidden])');
            if (!openPicker) {
                return;
            }
            const dialog = openPicker.closest('dialog');
            if (!dialog) {
                return;
            }
            const toggle = dialog.querySelector('[data-need-picker-toggle]');
            if (toggle) {
                toggle.setAttribute('aria-expanded', 'false');
            }
            closeNeedPicker(dialog, true);
            event.preventDefault();
            event.stopPropagation();
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
            const root = document.querySelector('.ua-root');
            const currentVersion = getMeta('current-site-id') || (root ? root.getAttribute('data-site-context-version') : '') || '';
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
    // Report Weekly Autosubmit (CSP-safe)
    // ========================================================================

    function setupReportWeeklyAutosubmit() {
        const root = document.querySelector('.report-weekly');
        if (!root) return;
        const form = root.querySelector('form.filter-bar');
        if (!form) return;
        const status = form.querySelector('.filter-status');
        let submitting = false;

        const submit = () => {
            if (submitting) return;
            submitting = true;
            if (status) status.classList.add('is-visible');
            if (form.requestSubmit) {
                form.requestSubmit();
            } else {
                form.submit();
            }
        };

        form.addEventListener('submit', () => {
            if (status) status.classList.add('is-visible');
        });

        form.querySelectorAll('[data-autosubmit="1"]').forEach(el => {
            el.addEventListener('change', submit);
        });

        const year = form.querySelector('#year-input');
        if (year) {
            year.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    submit();
                }
            });
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
    // Auto-init on DOM ready
    // ========================================================================
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
    
})();
