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
    let departmentQuickOverviewRequestId = 0;
    
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
        setupDepartmentCreateForm();
        setupResidenceCreateModal();
        setupUnifiedAdminUsersForm();
        setupDepartmentReorderControls();
        setupDepartmentListOverflowMenus();
        setupDepartmentQuickOverview();
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

        function getDepartmentDeleteNodes(dialog) {
            if (!dialog || !dialog.querySelector) {
                return {
                    form: null,
                    title: null,
                    nameText: null,
                    input: null,
                    confirmButton: null,
                };
            }
            return {
                form: dialog.querySelector('[data-department-delete-form]'),
                title: dialog.querySelector('[data-department-delete-title]'),
                nameText: dialog.querySelector('[data-department-delete-name-text]'),
                input: dialog.querySelector('[data-department-delete-confirm-input]'),
                confirmButton: dialog.querySelector('[data-department-delete-confirm-button]'),
            };
        }

        function resetDepartmentDeleteModal(dialog) {
            const nodes = getDepartmentDeleteNodes(dialog);
            if (nodes.form) {
                nodes.form.action = '';
            }
            if (nodes.title) {
                nodes.title.textContent = 'Ta bort avdelning?';
            }
            if (nodes.nameText) {
                nodes.nameText.textContent = '';
            }
            if (nodes.input) {
                nodes.input.value = '';
                nodes.input.setAttribute('placeholder', 'Skriv avdelningens namn');
            }
            if (nodes.confirmButton) {
                nodes.confirmButton.disabled = true;
            }
            if (dialog) {
                dialog.dataset.departmentDeleteName = '';
                dialog.dataset.departmentDeleteUrl = '';
            }
        }

        function syncDepartmentDeleteConfirmation(dialog) {
            const nodes = getDepartmentDeleteNodes(dialog);
            const expected = String(dialog && dialog.dataset ? dialog.dataset.departmentDeleteName || '' : '');
            const inputValue = String(nodes.input && nodes.input.value ? nodes.input.value : '').trim();
            if (nodes.confirmButton) {
                nodes.confirmButton.disabled = !expected || inputValue !== expected;
            }
        }

        function seedDepartmentDeleteModal(dialog, trigger) {
            const nodes = getDepartmentDeleteNodes(dialog);
            const deptName = String(trigger.getAttribute('data-department-delete-name') || '').trim();
            const deleteTitle = String(trigger.getAttribute('data-department-delete-title') || '').trim();
            const deleteUrl = String(trigger.getAttribute('data-department-delete-url') || '').trim();
            if (!deptName || !deleteUrl) {
                return;
            }
            if (nodes.form) {
                nodes.form.action = deleteUrl;
            }
            if (nodes.title) {
                nodes.title.textContent = deleteTitle || ('Ta bort ' + deptName + '?');
            }
            if (nodes.nameText) {
                nodes.nameText.textContent = 'Avdelning: ' + deptName;
            }
            if (nodes.input) {
                nodes.input.value = '';
                nodes.input.setAttribute('placeholder', deptName);
            }
            if (dialog) {
                dialog.dataset.departmentDeleteName = deptName;
                dialog.dataset.departmentDeleteUrl = deleteUrl;
            }
            syncDepartmentDeleteConfirmation(dialog);
            window.setTimeout(function() {
                if (nodes.input && typeof nodes.input.focus === 'function') {
                    nodes.input.focus();
                }
            }, 0);
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
            if (dialog.id === 'department-delete-modal') {
                seedDepartmentDeleteModal(dialog, trigger);
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
            if (dialog && dialog.id === 'department-delete-modal') {
                resetDepartmentDeleteModal(dialog);
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

            const deleteConfirm = event.target.closest('[data-department-delete-confirm-input]');
            if (deleteConfirm) {
                const dialog = deleteConfirm.closest('#department-delete-modal');
                if (dialog) {
                    syncDepartmentDeleteConfirmation(dialog);
                }
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

        document.addEventListener('input', function(event) {
            const input = event.target;
            if (!input || !input.matches || !input.matches('[data-department-delete-confirm-input]')) {
                return;
            }
            const dialog = input.closest('#department-delete-modal');
            if (dialog) {
                syncDepartmentDeleteConfirmation(dialog);
            }
        });

        document.addEventListener('submit', function(event) {
            const form = event.target && event.target.closest ? event.target.closest('[data-department-delete-form]') : null;
            if (!form) {
                return;
            }
            const dialog = form.closest('#department-delete-modal');
            if (!dialog) {
                return;
            }
            const nodes = getDepartmentDeleteNodes(dialog);
            const expected = String(dialog.dataset.departmentDeleteName || '');
            const actual = String(nodes.input && nodes.input.value ? nodes.input.value : '').trim();
            if (!expected || actual !== expected) {
                event.preventDefault();
                if (nodes.confirmButton) {
                    nodes.confirmButton.disabled = true;
                }
                if (nodes.input && typeof nodes.input.focus === 'function') {
                    nodes.input.focus();
                }
            }
        });

        const deleteDialog = document.getElementById('department-delete-modal');
        if (deleteDialog) {
            deleteDialog.addEventListener('close', function() {
                resetDepartmentDeleteModal(deleteDialog);
            });
        }
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
        if (meta) {
            return meta.getAttribute('content') || '';
        }
        const match = document.cookie ? document.cookie.match(/(?:^|; )csrf_token=([^;]+)/) : null;
        return match ? decodeURIComponent(match[1]) : '';
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

    function setupDepartmentReorderControls() {
        const listRoot = document.querySelector('.admin-departments[data-department-reorder-url]');
        if (!listRoot) {
            return;
        }

        const rowsSelector = '.admin-departments__row[data-department-row]';
        const handleSelector = '[data-department-drag-handle]';
        const reorderUrl = listRoot.getAttribute('data-department-reorder-url') || '';
        const listNode = listRoot.querySelector('.admin-departments__list');
        if (!listNode || !reorderUrl) {
            return;
        }

        let activeDrag = null;
        let saving = false;

        function getRows() {
            return Array.from(listNode.querySelectorAll(rowsSelector));
        }

        function getRowIds() {
            return getRows().map(function(row) {
                return row.getAttribute('data-department-id') || '';
            }).filter(Boolean);
        }

        function rowsMatch(a, b) {
            if (!a || !b || a.length !== b.length) {
                return false;
            }
            for (let index = 0; index < a.length; index += 1) {
                if (a[index] !== b[index]) {
                    return false;
                }
            }
            return true;
        }

        function setRowDragging(row, isDragging) {
            if (!row) {
                return;
            }
            row.classList.toggle('is-dragging', !!isDragging);
            row.setAttribute('aria-grabbed', isDragging ? 'true' : 'false');
        }

        function insertRowAt(row, targetRow, beforeTarget) {
            if (!row || !targetRow || row === targetRow) {
                return;
            }
            if (beforeTarget) {
                listNode.insertBefore(row, targetRow);
                return;
            }
            if (targetRow.nextElementSibling) {
                listNode.insertBefore(row, targetRow.nextElementSibling);
            } else {
                listNode.appendChild(row);
            }
        }

        function resetRowOrder(rowIds) {
            const currentRows = getRows();
            const rowsById = {};
            currentRows.forEach(function(row) {
                const id = row.getAttribute('data-department-id') || '';
                if (id) {
                    rowsById[id] = row;
                }
            });
            rowIds.forEach(function(id) {
                const row = rowsById[id];
                if (row) {
                    listNode.appendChild(row);
                }
            });
        }

        function showError(message) {
            const flash = document.createElement('div');
            flash.className = 'ua-flash ua-flash-error';
            flash.setAttribute('role', 'alert');
            flash.textContent = message || 'Kunde inte spara ordningen.';
            const page = listRoot.querySelector('.admin-departments__page-header');
            if (page && page.parentNode) {
                page.parentNode.insertBefore(flash, page.nextSibling);
            } else {
                listRoot.insertBefore(flash, listRoot.firstChild);
            }
        }

        async function persistOrder(initialRowIds) {
            if (saving) {
                return;
            }
            const currentRowIds = getRowIds();
            if (!currentRowIds.length || rowsMatch(currentRowIds, initialRowIds)) {
                return;
            }
            saving = true;
            listRoot.classList.add('is-saving-reorder');
            try {
                const csrfToken = getCsrfToken();
                const response = await fetch(reorderUrl, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: Object.assign({
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    }, csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
                    body: JSON.stringify({
                        department_ids: currentRowIds
                    })
                });
                if (!response.ok) {
                    let message = 'Kunde inte spara ordningen.';
                    try {
                        const payload = await response.json();
                        if (payload && payload.message) {
                            message = String(payload.message);
                        }
                    } catch (error) {
                        // fall back to default message
                    }
                    resetRowOrder(initialRowIds);
                    showError(message);
                    window.setTimeout(function() {
                        window.location.reload();
                    }, 1200);
                    return;
                }
            } catch (error) {
                resetRowOrder(initialRowIds);
                showError('Kunde inte spara ordningen.');
                window.setTimeout(function() {
                    window.location.reload();
                }, 1200);
                return;
            } finally {
                saving = false;
                listRoot.classList.remove('is-saving-reorder');
            }
        }

        function beginDrag(handle, event) {
            if (!handle || !event) {
                return;
            }
            const row = handle.closest(rowsSelector);
            if (!row) {
                return;
            }

            const pointerId = event.pointerId;
            const startPoint = { x: event.clientX, y: event.clientY };
            const initialRowIds = getRowIds();

            activeDrag = {
                handle: handle,
                row: row,
                pointerId: pointerId,
                startPoint: startPoint,
                started: false,
                initialRowIds: initialRowIds
            };

            if (handle.setPointerCapture) {
                try {
                    handle.setPointerCapture(pointerId);
                } catch (error) {
                    // no-op
                }
            }
        }

        function updateDrag(event) {
            if (!activeDrag || event.pointerId !== activeDrag.pointerId) {
                return;
            }

            const row = activeDrag.row;
            const deltaX = Math.abs(event.clientX - activeDrag.startPoint.x);
            const deltaY = Math.abs(event.clientY - activeDrag.startPoint.y);
            const shouldStart = !activeDrag.started && (deltaX > 4 || deltaY > 4);
            if (!activeDrag.started && !shouldStart) {
                return;
            }

            if (!activeDrag.started) {
                activeDrag.started = true;
                setRowDragging(row, true);
                listRoot.classList.add('is-reordering');
            }

            event.preventDefault();
            const element = document.elementFromPoint(event.clientX, event.clientY);
            const targetRow = element && element.closest ? element.closest(rowsSelector) : null;
            if (!targetRow || targetRow === row || !listNode.contains(targetRow)) {
                return;
            }

            const rect = targetRow.getBoundingClientRect();
            const beforeTarget = event.clientY < (rect.top + rect.height / 2);
            insertRowAt(row, targetRow, beforeTarget);
        }

        function finishDrag(event) {
            if (!activeDrag || event.pointerId !== activeDrag.pointerId) {
                return;
            }

            const drag = activeDrag;
            activeDrag = null;
            setRowDragging(drag.row, false);
            listRoot.classList.remove('is-reordering');

            if (drag.handle && drag.handle.releasePointerCapture) {
                try {
                    drag.handle.releasePointerCapture(drag.pointerId);
                } catch (error) {
                    // no-op
                }
            }

            if (drag.started) {
                void persistOrder(drag.initialRowIds);
            }
        }

        document.addEventListener('pointermove', updateDrag, { passive: false });
        document.addEventListener('pointerup', finishDrag);
        document.addEventListener('pointercancel', finishDrag);

        document.addEventListener('pointerdown', function(event) {
            const handle = event.target.closest(handleSelector);
            if (!handle || !listNode.contains(handle)) {
                return;
            }
            const row = handle.closest(rowsSelector);
            if (!row) {
                return;
            }
            if (event.button !== 0 && event.pointerType !== 'touch') {
                return;
            }
            beginDrag(handle, event);
        });

        document.addEventListener('keydown', function(event) {
            const handle = event.target.closest(handleSelector);
            if (!handle || !listNode.contains(handle)) {
                return;
            }
            if (event.key !== 'ArrowUp' && event.key !== 'ArrowDown') {
                return;
            }
            const row = handle.closest(rowsSelector);
            if (!row) {
                return;
            }
            const previousOrder = getRowIds();
            const sibling = event.key === 'ArrowUp' ? row.previousElementSibling : row.nextElementSibling;
            if (!sibling || !sibling.matches || !sibling.matches(rowsSelector)) {
                return;
            }
            event.preventDefault();
            if (event.key === 'ArrowUp') {
                listNode.insertBefore(row, sibling);
            } else if (sibling.nextElementSibling) {
                listNode.insertBefore(row, sibling.nextElementSibling);
            } else {
                listNode.appendChild(row);
            }
            handle.focus();
            void persistOrder(previousOrder);
        });
    }

    function setupDepartmentListOverflowMenus() {
        const menus = Array.from(document.querySelectorAll('.admin-departments__overflow'));
        if (!menus.length) {
            return;
        }

        function closeMenu(menu, restoreFocus) {
            if (!menu || !menu.hasAttribute('open')) {
                return;
            }
            menu.removeAttribute('open');
            menu.classList.remove('is-overflow-open');
            const row = menu.closest('.admin-departments__row');
            if (row) {
                row.classList.remove('is-overflow-open');
            }
            if (restoreFocus) {
                const summary = menu.querySelector('summary');
                if (summary && typeof summary.focus === 'function') {
                    summary.focus();
                }
            }
        }

        function closeOtherMenus(activeMenu) {
            menus.forEach(function(menu) {
                if (menu !== activeMenu) {
                    closeMenu(menu, false);
                }
            });
        }

        menus.forEach(function(menu) {
            const summary = menu.querySelector('summary');
            if (!summary) {
                return;
            }

            summary.addEventListener('click', function(event) {
                event.stopPropagation();
            });

            menu.addEventListener('toggle', function() {
                if (menu.open) {
                    menu.classList.add('is-overflow-open');
                    const row = menu.closest('.admin-departments__row');
                    if (row) {
                        row.classList.add('is-overflow-open');
                    }
                    closeOtherMenus(menu);
                } else {
                    menu.classList.remove('is-overflow-open');
                    const row = menu.closest('.admin-departments__row');
                    if (row) {
                        row.classList.remove('is-overflow-open');
                    }
                }
            });
        });

        document.addEventListener('pointerdown', function(event) {
            const openMenu = menus.find(function(menu) {
                return menu.open;
            });
            if (!openMenu) {
                return;
            }
            if (openMenu.contains(event.target)) {
                return;
            }
            closeMenu(openMenu, false);
        });

        document.addEventListener('keydown', function(event) {
            if (event.key !== 'Escape') {
                return;
            }
            const openMenu = menus.find(function(menu) {
                return menu.open;
            });
            if (!openMenu) {
                return;
            }
            closeMenu(openMenu, true);
            event.preventDefault();
            event.stopPropagation();
        });
    }

    function setupDepartmentCreateForm() {
        const form = document.querySelector('form.department-form');
        if (!form || !form.querySelector) return;

        const modeOptions = form.querySelectorAll('[data-resident-count-mode-option]');
        const fixedPanel = form.querySelector('[data-resident-count-fixed-panel]');
        const countInput = form.querySelector('[data-resident-count-input]');
        const helper = form.querySelector('[data-resident-count-helper]');
        const modeCards = form.querySelectorAll('[data-resident-count-mode-card]');

        if (!modeOptions.length || !fixedPanel || !countInput || !helper) return;

        function syncResidentCountMode() {
            const selected = form.querySelector('[data-resident-count-mode-option]:checked');
            const isFixed = !selected || selected.value === 'fixed';
            const selectedValue = selected ? selected.value : 'fixed';

            fixedPanel.hidden = !isFixed;
            helper.hidden = isFixed;
            countInput.disabled = !isFixed;
            countInput.required = isFixed;
            if (isFixed && !countInput.value) {
                countInput.value = '0';
            }
            modeCards.forEach(function(card) {
                const input = card.querySelector('[data-resident-count-mode-option]');
                card.classList.toggle('is-selected', !!input && input.value === selectedValue);
            });
        }

        modeOptions.forEach(function(option) {
            option.addEventListener('change', syncResidentCountMode);
        });

        syncResidentCountMode();
    }

    function setupResidenceCreateModal() {
        const dialog = document.getElementById('residence-create-modal');
        if (!dialog) return;

        const form = dialog.querySelector('form[action*="/ui/admin/residences/new"]');
        const input = dialog.querySelector('input[name="name"]');
        const status = dialog.querySelector('[data-residence-create-status]');
        if (!form || !input) return;

        function setStatus(message, kind) {
            if (!status) return;
            status.textContent = message || '';
            status.hidden = !message;
            status.dataset.state = kind || 'neutral';
        }

        function getResidenceSelects() {
            return Array.prototype.slice.call(document.querySelectorAll('select[name="residence_id"]'));
        }

        function ensureResidenceOption(residence) {
            if (!residence || !residence.id) return;
            const selects = getResidenceSelects();
            selects.forEach(function(select) {
                let option = Array.prototype.slice.call(select.options).find(function(opt) {
                    return String(opt.value) === String(residence.id);
                });
                if (!option) {
                    option = document.createElement('option');
                    option.value = String(residence.id);
                    option.textContent = String(residence.name || '');
                    select.appendChild(option);
                } else if (!option.textContent) {
                    option.textContent = String(residence.name || '');
                }
                select.value = String(residence.id);
                select.dispatchEvent(new Event('change', { bubbles: true }));
            });
        }

        async function submitInline(event) {
            if (!window.fetch || !window.FormData) {
                return;
            }
            event.preventDefault();
            setStatus('', 'neutral');
            const submitButton = form.querySelector('button[type="submit"]');
            const originalText = submitButton ? submitButton.textContent : '';
            if (submitButton) submitButton.disabled = true;
            try {
                const response = await fetch(form.action, {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'X-Requested-With': 'XMLHttpRequest',
                        'Accept': 'application/json'
                    },
                    body: new FormData(form)
                });
                const payload = await response.json().catch(function() {
                    return null;
                });
                if (!response.ok || !payload || !payload.ok) {
                    setStatus((payload && payload.message) ? String(payload.message) : 'Kunde inte skapa boende.', 'error');
                    return;
                }
                ensureResidenceOption(payload.residence || {});
                setStatus('', 'neutral');
                try {
                    dialog.close();
                } catch (closeError) {
                    dialog.removeAttribute('open');
                }
                if (input) input.value = '';
            } catch (error) {
                setStatus('Kunde inte skapa boende.', 'error');
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                    submitButton.textContent = originalText;
                }
            }
        }

        form.addEventListener('submit', submitInline);
        dialog.addEventListener('close', function() {
            setStatus('', 'neutral');
        });
    }

    function setupUnifiedAdminUsersForm() {
        const form = document.querySelector('.admin-users-form');
        if (!form) return;

        const roleSelect = form.querySelector('#role');
        const departmentField = form.querySelector('#department-field');
        if (!roleSelect || !departmentField) return;

        const departmentSelect = form.querySelector('#department_id');

        function syncDepartmentField() {
            const needsDepartment = roleSelect.value === 'unit_portal';
            departmentField.style.display = needsDepartment ? '' : 'none';
            if (departmentSelect) {
                departmentSelect.required = needsDepartment;
                if (!needsDepartment) {
                    departmentSelect.value = '';
                }
            }
        }

        roleSelect.addEventListener('change', syncDepartmentField);
        syncDepartmentField();
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

    function setupDepartmentQuickOverview() {
        const list = document.querySelector('.admin-departments__list');
        const panel = document.querySelector('[data-department-quick-overview-panel]');
        if (!list || !panel) {
            return;
        }

        function clearSelectedRow() {
            const selectedRows = list.querySelectorAll('[data-department-row].is-selected');
            selectedRows.forEach(function(row) {
                row.classList.remove('is-selected');
            });
            const selectedButtons = list.querySelectorAll('[data-department-quick-overview-trigger][aria-pressed="true"]');
            selectedButtons.forEach(function(button) {
                button.setAttribute('aria-pressed', 'false');
            });
        }

        function selectRow(trigger) {
            clearSelectedRow();
            const row = trigger && trigger.closest ? trigger.closest('[data-department-row]') : null;
            if (row) {
                row.classList.add('is-selected');
            }
            if (trigger) {
                trigger.setAttribute('aria-pressed', 'true');
            }
        }

        function renderLoading() {
            panel.setAttribute('aria-busy', 'true');
            panel.innerHTML = '<div class="admin-departments__inspector-shell"><div class="admin-departments__inspector-head"><h2 class="app-shell__card-title admin-departments__inspector-title">Snabböversikt</h2><p class="admin-departments__inspector-subtitle">Laddar vald avdelning…</p></div><p class="admin-departments__inspector-copy">Ett ögonblick.</p></div>';
        }

        function renderError(message) {
            panel.setAttribute('aria-busy', 'false');
            panel.innerHTML = '<div class="admin-departments__inspector-shell"><div class="admin-departments__inspector-head"><h2 class="app-shell__card-title admin-departments__inspector-title">Snabböversikt</h2><p class="admin-departments__inspector-subtitle">Kunde inte läsa avdelningen.</p></div><p class="admin-departments__inspector-copy">' + escapeHtml(message) + '</p></div>';
        }

        function setupAccordionState() {
            const accordions = Array.prototype.slice.call(panel.querySelectorAll('[data-department-quick-overview-accordion]'));
            if (!accordions.length) {
                return;
            }

            accordions.forEach(function(accordion) {
                accordion.open = false;
            });

            accordions.forEach(function(accordion) {
                accordion.addEventListener('toggle', function() {
                    if (!accordion.open) {
                        return;
                    }
                    accordions.forEach(function(other) {
                        if (other !== accordion) {
                            other.open = false;
                        }
                    });
                });
            });
        }

        async function loadQuickOverview(trigger) {
            const row = trigger && trigger.closest ? trigger.closest('[data-department-row]') : null;
            const url = row ? String(row.getAttribute('data-department-quick-overview-url') || '').trim() : '';
            if (!url) {
                renderError('Snabböversikt saknar adress.');
                return;
            }

            const requestId = ++departmentQuickOverviewRequestId;
            selectRow(trigger);
            renderLoading();

            try {
                const response = await fetch(url, {
                    method: 'GET',
                    headers: {
                        'X-Requested-With': 'fetch',
                        'Accept': 'text/html'
                    }
                });
                if (requestId !== departmentQuickOverviewRequestId) {
                    return;
                }
                if (!response.ok) {
                    if (response.status === 403) {
                        throw new Error('Du har inte åtkomst till den här avdelningen.');
                    }
                    if (response.status === 404) {
                        throw new Error('Avdelningen kunde inte hittas.');
                    }
                    throw new Error('Kunde inte läsa snabböversikten.');
                }
                const html = await response.text();
                if (requestId !== departmentQuickOverviewRequestId) {
                    return;
                }
                panel.setAttribute('aria-busy', 'false');
                panel.innerHTML = html;
                setupAccordionState();
            } catch (error) {
                if (requestId !== departmentQuickOverviewRequestId) {
                    return;
                }
                renderError(error && error.message ? error.message : 'Kunde inte läsa snabböversikten.');
            }
        }

        list.addEventListener('click', function(event) {
            const trigger = event.target && event.target.closest ? event.target.closest('[data-department-quick-overview-trigger]') : null;
            if (!trigger || !list.contains(trigger)) {
                return;
            }
            event.preventDefault();
            event.stopPropagation();
            loadQuickOverview(trigger);
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

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', setupUnifiedAdminUsersForm);
    } else {
        setupUnifiedAdminUsersForm();
    }
    
})();
