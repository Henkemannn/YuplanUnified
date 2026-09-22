document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("#yp-product-app");
  if (!root) {
    return;
  }

  const tabs = Array.from(root.querySelectorAll("[data-page2-option-tab]"));
  const panels = new Map(
    Array.from(root.querySelectorAll("[data-page2-option-panel]")).map((panel) => [panel.id, panel]),
  );
  if (!tabs.length || !panels.size) {
    return;
  }

  const reviewEndpoint = root.dataset.page2ReviewEndpoint || "/ui/kitchen/planering/day/review";
  const siteId = root.dataset.page2SiteId || "";
  const serviceDate = root.dataset.page2ServiceDate || "";
  const meal = root.dataset.page2Meal || "lunch";
  const switchNote = root.querySelector("[data-page2-review-switch-note]");
  const csrfToken = (() => {
    const meta = document.querySelector('meta[name="csrf-token"]');
    if (meta && meta.getAttribute("content")) {
      return meta.getAttribute("content");
    }
    try {
      const cookie = document.cookie
        .split("; ")
        .find((row) => row.startsWith("csrf_token="));
      return cookie ? decodeURIComponent(cookie.split("=").slice(1).join("=")) : "";
    } catch (_error) {
      return "";
    }
  })();

  const panelStateById = new Map();
  let activePanelId = null;

  const getPanelState = (panel) => {
    const optionId = panel.dataset.page2OptionId || "";
    if (panelStateById.has(panel.id)) {
      return panelStateById.get(panel.id);
    }

    const controls = Array.from(panel.querySelectorAll("[data-page2-review-checkbox]")).map((input) => ({
      input,
      initialChecked: input.getAttribute("data-page2-review-initial") === "1" || input.checked,
    }));
    const submitButton = panel.querySelector("[data-page2-review-submit]");
    const resetButton = panel.querySelector("[data-page2-review-reset]");
    const feedback = panel.querySelector("[data-page2-review-feedback]");
    const banner = panel.querySelector("[data-page2-review-banner]");
    const status = panel.querySelector("[data-page2-review-status]");
    const state = {
      panel,
      optionId,
      reviewState: panel.dataset.page2ReviewState || "UNREVIEWED",
      reviewIsStale: panel.dataset.page2ReviewStale === "true",
      controls,
      submitButton,
      resetButton,
      feedback,
      banner,
      status,
      dirty: false,
      saving: false,
    };

    const syncDirty = () => {
      state.dirty = state.controls.some((control) => control.input.checked !== control.initialChecked);
      if (state.resetButton) {
        state.resetButton.hidden = !state.dirty;
      }
      if (state.feedback) {
        state.feedback.hidden = true;
        state.feedback.textContent = "";
      }
      if (switchNote && !state.dirty) {
        switchNote.hidden = true;
        switchNote.textContent = "";
      }
      refreshSubmitLabel(state);
    };

    const refreshStatus = () => {
      if (!state.banner || !state.status) {
        return;
      }
      const currentReview = !state.reviewIsStale && (state.reviewState === "REVIEWED_NO_DEVIATIONS" || state.reviewState === "REVIEWED_WITH_DEVIATIONS");
      if (state.reviewIsStale) {
        state.banner.hidden = false;
        state.banner.classList.add("is-warning");
        state.banner.classList.remove("is-positive");
        state.status.textContent = "Underlaget har ändrats – granska igen.";
      } else if (currentReview) {
        state.banner.hidden = false;
        state.banner.classList.remove("is-warning");
        state.banner.classList.add("is-positive");
        state.status.textContent = "Granskad";
      } else {
        state.banner.hidden = true;
        state.status.textContent = "";
      }
    };

    const refreshSubmitLabel = (currentState) => {
      if (!currentState.submitButton) {
        return;
      }
      const checkedCount = currentState.controls.filter((control) => control.input.checked).length;
      const hasControls = currentState.controls.length > 0;
      const currentReview = !currentState.reviewIsStale && (currentState.reviewState === "REVIEWED_NO_DEVIATIONS" || currentState.reviewState === "REVIEWED_WITH_DEVIATIONS");
      let label = "Alla kan äta rätten som den är →";
      if (hasControls && checkedCount > 0) {
        label = currentState.dirty || !currentReview ? "Bekräfta anpassningar →" : "Ändra granskning";
      } else if (currentReview && hasControls) {
        label = "Ändra granskning";
      }
      currentState.submitButton.textContent = label;
      currentState.submitButton.disabled = currentState.saving;
    };

    const syncState = () => {
      syncDirty();
      refreshStatus();
      refreshSubmitLabel(state);
    };

    controls.forEach((control) => {
      control.input.addEventListener("change", () => {
        syncState();
      });
    });

    if (resetButton) {
      resetButton.addEventListener("click", () => {
        controls.forEach((control) => {
          control.input.checked = control.initialChecked;
        });
        syncState();
      });
    }

    if (submitButton) {
      submitButton.addEventListener("click", () => {
        void saveReview(state);
      });
    }

    panelStateById.set(panel.id, state);
    syncState();
    return state;
  };

  const getActivePanel = () => {
    if (!activePanelId) {
      return null;
    }
    return panels.get(activePanelId) || null;
  };

  const setSwitchNote = (message) => {
    if (!switchNote) {
      return;
    }
    switchNote.hidden = !message;
    switchNote.textContent = message || "";
  };

  const refreshSubmitLabel = (state) => {
    if (!state.submitButton) {
      return;
    }
    const checkedCount = state.controls.filter((control) => control.input.checked).length;
    const hasControls = state.controls.length > 0;
    const currentReview = !state.reviewIsStale && (state.reviewState === "REVIEWED_NO_DEVIATIONS" || state.reviewState === "REVIEWED_WITH_DEVIATIONS");
    let label = "Alla kan äta rätten som den är →";
    if (hasControls && checkedCount > 0) {
      label = state.dirty || !currentReview ? "Bekräfta anpassningar →" : "Ändra granskning";
    } else if (currentReview && hasControls) {
      label = "Ändra granskning";
    }
    state.submitButton.textContent = label;
    state.submitButton.disabled = state.saving;
  };

  const syncPanelActiveState = (state) => {
    if (state.resetButton) {
      state.resetButton.hidden = !state.dirty;
    }
    if (state.feedback && !state.saving) {
      state.feedback.hidden = !state.feedback.textContent;
    }
    refreshSubmitLabel(state);
  };

  const saveReview = async (state) => {
    if (state.saving) {
      return;
    }
    state.saving = true;
    setSwitchNote("");
    if (state.feedback) {
      state.feedback.hidden = false;
      state.feedback.textContent = "Sparar...";
      state.feedback.classList.remove("is-error", "is-success");
    }
    refreshSubmitLabel(state);

    const decisions = state.controls.map((control) => ({
      destination_id: control.input.dataset.page2ReviewDestinationId || "",
      requirement_group_id: control.input.dataset.page2ReviewGroupId || "",
      decision: control.input.checked ? "ADAPTATION_REQUIRED" : "NO_ADAPTATION_REQUIRED",
    }));

    try {
      const response = await fetch(reviewEndpoint, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
        },
        body: JSON.stringify({
          site_id: siteId,
          service_date: serviceDate,
          meal,
          option_id: state.optionId,
          decisions,
        }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(payload.message || payload.error || "Kunde inte spara granskningen");
      }
      const review = payload.review || {};
      state.reviewState = review.review_state || state.reviewState;
      state.reviewIsStale = !!review.review_is_stale;
      state.controls.forEach((control) => {
        control.initialChecked = control.input.checked;
        control.input.setAttribute("data-page2-review-initial", control.input.checked ? "1" : "0");
      });
      state.dirty = false;
      if (state.feedback) {
        state.feedback.textContent = "Sparat";
        state.feedback.classList.remove("is-error");
        state.feedback.classList.add("is-success");
      }
      syncPanelActiveState(state);
      refreshStateBanner(state, review);
      setTimeout(() => {
        if (state.feedback && state.feedback.textContent === "Sparat") {
          state.feedback.hidden = true;
        }
      }, 1800);
    } catch (error) {
      if (state.feedback) {
        state.feedback.hidden = false;
        state.feedback.textContent = error && error.message ? error.message : "Kunde inte spara granskningen";
        state.feedback.classList.remove("is-success");
        state.feedback.classList.add("is-error");
      }
    } finally {
      state.saving = false;
      refreshSubmitLabel(state);
    }
  };

  const refreshStateBanner = (state, review) => {
    if (!state.banner || !state.status) {
      return;
    }
    const reviewState = review && review.review_state ? review.review_state : state.reviewState;
    const isStale = review && Object.prototype.hasOwnProperty.call(review, "review_is_stale") ? !!review.review_is_stale : state.reviewIsStale;
    if (isStale) {
      state.banner.hidden = false;
      state.banner.classList.add("is-warning");
      state.banner.classList.remove("is-positive");
      state.status.textContent = "Underlaget har ändrats – granska igen.";
      return;
    }
    if (reviewState === "REVIEWED_NO_DEVIATIONS" || reviewState === "REVIEWED_WITH_DEVIATIONS") {
      state.banner.hidden = false;
      state.banner.classList.remove("is-warning");
      state.banner.classList.add("is-positive");
      state.status.textContent = "Granskad";
      return;
    }
    state.banner.hidden = true;
    state.status.textContent = "";
  };

  const activateTab = (tab, { focus = false } = {}) => {
    const panelId = tab.getAttribute("aria-controls");
    if (!panelId) {
      return false;
    }
    const nextPanel = panels.get(panelId);
    if (!nextPanel) {
      return false;
    }

    const activePanel = getActivePanel();
    if (activePanel && activePanel !== nextPanel) {
      const activeState = getPanelState(activePanel);
      if (activeState.dirty) {
        setSwitchNote("Spara eller återställ ändringarna först.");
        return false;
      }
    }

    setSwitchNote("");
    tabs.forEach((candidate) => {
      const isActive = candidate === tab;
      candidate.classList.toggle("is-active", isActive);
      candidate.setAttribute("aria-selected", isActive ? "true" : "false");
      candidate.tabIndex = isActive ? 0 : -1;
    });

    panels.forEach((panel, id) => {
      const isActive = id === panelId;
      panel.hidden = !isActive;
      panel.classList.toggle("is-active", isActive);
    });

    activePanelId = panelId;
    const nextState = getPanelState(nextPanel);
    syncPanelActiveState(nextState);
    if (focus) {
      tab.focus();
    }
    return true;
  };

  const focusRelative = (currentIndex, step) => {
    const nextIndex = (currentIndex + step + tabs.length) % tabs.length;
    const nextTab = tabs[nextIndex];
    if (nextTab) {
      activateTab(nextTab, { focus: true });
    }
  };

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
      activateTab(tab);
    });
    tab.addEventListener("keydown", (event) => {
      switch (event.key) {
        case "ArrowLeft":
        case "ArrowUp":
          event.preventDefault();
          focusRelative(index, -1);
          break;
        case "ArrowRight":
        case "ArrowDown":
          event.preventDefault();
          focusRelative(index, 1);
          break;
        case "Home":
          event.preventDefault();
          activateTab(tabs[0], { focus: true });
          break;
        case "End":
          event.preventDefault();
          activateTab(tabs[tabs.length - 1], { focus: true });
          break;
        default:
          break;
      }
    });
  });

  const initialTab = tabs.find((tab) => tab.getAttribute("aria-selected") === "true") || tabs[0];
  if (initialTab) {
    activateTab(initialTab);
  }
});