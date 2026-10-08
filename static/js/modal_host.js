(function () {
  'use strict';

  function toArray(value) {
    if (Array.isArray(value)) {
      return value.slice();
    }
    if (value === undefined || value === null || value === '') {
      return [];
    }
    return [value];
  }

  function isElement(value) {
    return Boolean(value && value.nodeType === 1);
  }

  function resolveElement(root, selector) {
    if (!isElement(root) || !selector) {
      return null;
    }
    try {
      return root.querySelector(selector);
    } catch (error) {
      return null;
    }
  }

  function create(root, options) {
    if (!isElement(root)) {
      throw new Error('YuplanModalHost.create requires a root element.');
    }

    const config = {
      bodyClass: 'yp-modal-open',
      mode: 'shell-owned-card',
      openClass: 'is-open',
      backdropSelector: null,
      panelSelector: null,
      frameSelector: null,
      closeOnBackdrop: true,
      closeOnEscape: true,
      resetFrameSrc: 'about:blank',
      restoreFocus: true,
      listenForMessages: true,
      closeMessageTypes: [],
      shouldCloseOnMessage: null,
      ...options,
    };

    const state = {
      root,
      backdrop: resolveElement(root, config.backdropSelector),
      panel: resolveElement(root, config.panelSelector),
      frame: resolveElement(root, config.frameSelector),
      bodyClass: String(config.bodyClass || 'yp-modal-open'),
      mode: String(config.mode || 'shell-owned-card'),
      openClass: String(config.openClass || 'is-open'),
      closeOnBackdrop: Boolean(config.closeOnBackdrop),
      closeOnEscape: Boolean(config.closeOnEscape),
      resetFrameSrc: config.resetFrameSrc,
      restoreFocus: Boolean(config.restoreFocus),
      listenForMessages: Boolean(config.listenForMessages),
      closeMessageTypes: toArray(config.closeMessageTypes).map(String),
      shouldCloseOnMessage: typeof config.shouldCloseOnMessage === 'function' ? config.shouldCloseOnMessage : null,
      lastActiveElement: null,
      isOpen: false,
      destroyed: false,
    };

    function setMode(nextMode) {
      const normalizedMode = String(nextMode || state.mode || 'shell-owned-card') === 'child-owned-card'
        ? 'child-owned-card'
        : 'shell-owned-card';
      state.mode = normalizedMode;
      root.dataset.modalHostMode = normalizedMode;
      return normalizedMode;
    }

    function rememberFocus(trigger) {
      if (isElement(trigger)) {
        state.lastActiveElement = trigger;
        return;
      }
      if (isElement(document.activeElement)) {
        state.lastActiveElement = document.activeElement;
        return;
      }
      state.lastActiveElement = null;
    }

    function syncOpenState(isOpen) {
      root.hidden = !isOpen;
      root.setAttribute('aria-hidden', isOpen ? 'false' : 'true');
      root.classList.toggle(state.openClass, isOpen);
      document.body.classList.toggle(state.bodyClass, isOpen);
      state.isOpen = isOpen;
    }

    function resetFrame() {
      if (!state.frame || state.resetFrameSrc === false || state.resetFrameSrc === null || state.resetFrameSrc === undefined) {
        return;
      }
      try {
        state.frame.src = String(state.resetFrameSrc || 'about:blank');
      } catch (error) {
        // Ignore frame reset failures in restricted environments.
      }
    }

    function handleMessage(event) {
      if (!state.listenForMessages || !state.frame || !state.frame.contentWindow) {
        return false;
      }
      if (event.origin !== window.location.origin || event.source !== state.frame.contentWindow) {
        return false;
      }

      const payload = event.data || {};
      if (state.shouldCloseOnMessage && state.shouldCloseOnMessage(payload, event, api)) {
        close();
        return true;
      }

      const messageType = String(payload.type || '');
      if (state.closeMessageTypes.indexOf(messageType) !== -1) {
        close();
        return true;
      }

      return false;
    }

    function handleKeydown(event) {
      if (!state.closeOnEscape || !state.isOpen) {
        return;
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        close();
      }
    }

    function handleBackdropClick(event) {
      if (!state.closeOnBackdrop || !state.isOpen) {
        return;
      }
      if (event.target === state.backdrop) {
        close();
      }
    }

    function open(nextOptions) {
      const opts = nextOptions || {};
      if (opts.bodyClass) {
        state.bodyClass = String(opts.bodyClass);
      }
      if (opts.mode) {
        setMode(opts.mode);
      } else {
        setMode(state.mode);
      }
      if (opts.resetFrameSrc !== undefined) {
        state.resetFrameSrc = opts.resetFrameSrc;
      }
      if (opts.closeMessageTypes !== undefined) {
        state.closeMessageTypes = toArray(opts.closeMessageTypes).map(String);
      }
      if (typeof opts.shouldCloseOnMessage === 'function') {
        state.shouldCloseOnMessage = opts.shouldCloseOnMessage;
      }
      if (opts.trigger) {
        rememberFocus(opts.trigger);
      } else if (!state.lastActiveElement) {
        rememberFocus(document.activeElement);
      }

      if (opts.src !== undefined && state.frame) {
        try {
          state.frame.src = String(opts.src || '');
        } catch (error) {
          // Ignore frame assignment failures in restricted environments.
        }
      }

      syncOpenState(true);

      if (state.panel && typeof state.panel.focus === 'function' && opts.focusPanel !== false) {
        try {
          state.panel.focus();
        } catch (error) {
          // Ignore focus failures in restricted browsers.
        }
      }

      return api;
    }

    function close(nextOptions) {
      const opts = nextOptions || {};
      resetFrame();
      syncOpenState(false);

      const shouldRestoreFocus = opts.restoreFocus !== false && state.restoreFocus;
      if (shouldRestoreFocus && state.lastActiveElement && typeof state.lastActiveElement.focus === 'function') {
        try {
          state.lastActiveElement.focus();
        } catch (error) {
          // Ignore focus restore failures in restricted browsers.
        }
      }
      state.lastActiveElement = null;

      return api;
    }

    function destroy() {
      if (state.destroyed) {
        return;
      }
      state.destroyed = true;
      if (state.closeOnEscape) {
        document.removeEventListener('keydown', handleKeydown);
      }
      if (state.closeOnBackdrop && state.backdrop) {
        state.backdrop.removeEventListener('click', handleBackdropClick);
      }
      if (state.listenForMessages) {
        window.removeEventListener('message', handleMessage);
      }
    }

    if (state.closeOnEscape) {
      document.addEventListener('keydown', handleKeydown);
    }
    if (state.closeOnBackdrop && state.backdrop) {
      state.backdrop.addEventListener('click', handleBackdropClick);
    }
    if (state.listenForMessages) {
      window.addEventListener('message', handleMessage);
    }

    setMode(state.mode);
    syncOpenState(false);

    const api = {
      open,
      close,
      destroy,
      setMode,
      get isOpen() {
        return state.isOpen;
      },
      get root() {
        return state.root;
      },
      get frame() {
        return state.frame;
      },
    };

    return api;
  }

  window.YuplanModalHost = {
    create,
  };
})();
