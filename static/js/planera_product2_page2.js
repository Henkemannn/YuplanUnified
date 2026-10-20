document.addEventListener("DOMContentLoaded", () => {
  const root = document.querySelector("#yp-product-app");
  if (!root) {
    return;
  }

  const tabs = Array.from(root.querySelectorAll("[data-page2-option-tab]"));
  const panels = new Map(
    Array.from(root.querySelectorAll("[data-page2-option-panel]")).map((panel) => [panel.id, panel]),
  );
  if (!panels.size) {
    return;
  }

  const reviewEndpoint = root.dataset.page2ReviewEndpoint || "/ui/kitchen/planering/day/review";
  const productionUrl = root.dataset.page2ProductionUrl || "";
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

    const parseMembers = (input) => {
      const raw = input.dataset.page2ReviewMembers || "";
      if (!raw) {
        const destinationId = input.dataset.page2ReviewDestinationId || "";
        const requirementGroupId = input.dataset.page2ReviewGroupId || "";
        if (!destinationId || !requirementGroupId) {
          return [];
        }
        return [{
          destination_id: destinationId,
          requirement_group_id: requirementGroupId,
        }];
      }
      try {
        const parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
      } catch (_error) {
        return [];
      }
    };

    const controls = Array.from(panel.querySelectorAll("[data-page2-review-checkbox]")).map((input) => ({
      input,
      initialChecked: input.getAttribute("data-page2-review-initial") === "1" || input.checked,
      mixed: input.getAttribute("data-page2-review-mixed") === "true",
      members: parseMembers(input),
    }));
    const submitButton = panel.querySelector("[data-page2-review-submit]");
    const resetButton = panel.querySelector("[data-page2-review-reset]");
    const feedback = panel.querySelector("[data-page2-review-feedback]");
    const banner = panel.querySelector("[data-page2-review-banner]");
    const status = panel.querySelector("[data-page2-review-status]");
    const editButton = panel.querySelector("[data-page2-review-edit]");
    const noAdaptationButton = panel.querySelector("[data-page2-review-no-adaptation]");
    const currentReview = !panel.dataset.page2ReviewStale &&
      (panel.dataset.page2ReviewState === "REVIEWED_NO_DEVIATIONS" ||
        panel.dataset.page2ReviewState === "REVIEWED_WITH_DEVIATIONS");
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
      editing: !currentReview,
    };

    const syncEditability = () => {
      state.controls.forEach((control) => {
        control.input.disabled = currentReview && !state.editing;
      });
      if (editButton) {
        editButton.hidden = !currentReview || state.editing;
      }
      if (noAdaptationButton) {
        noAdaptationButton.hidden = currentReview && !state.editing;
      }
      if (state.submitButton) {
        state.submitButton.hidden = currentReview && !state.editing;
      }
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
      syncEditability();
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
      let label = "Ingen anpassning behövs";
      if (hasControls && checkedCount > 0) {
        label = "Spara och visa produktionsunderlag →";
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
      control.input.indeterminate = control.mixed && !control.input.checked;
      control.input.addEventListener("change", () => {
        control.input.indeterminate = false;
        syncState();
      });
    });

    if (editButton) {
      editButton.addEventListener("click", () => {
        state.editing = true;
        state.controls.forEach((control) => {
          control.input.disabled = false;
        });
        if (editButton) {
          editButton.hidden = true;
        }
        if (noAdaptationButton) {
          noAdaptationButton.hidden = false;
        }
        if (state.submitButton) {
          state.submitButton.hidden = false;
        }
        syncPanelActiveState(state);
      });
    }

    if (noAdaptationButton) {
      noAdaptationButton.addEventListener("click", () => {
        state.editing = true;
        state.controls.forEach((control) => {
          control.input.checked = false;
          control.input.indeterminate = false;
          control.input.disabled = false;
        });
        if (editButton) {
          editButton.hidden = true;
        }
        if (noAdaptationButton) {
          noAdaptationButton.hidden = false;
        }
        if (state.submitButton) {
          state.submitButton.hidden = false;
        }
        syncPanelActiveState(state);
        void saveReview(state);
      });
    }

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
    let label = "Ingen anpassning behövs";
    if (hasControls && checkedCount > 0) {
      label = "Spara och visa produktionsunderlag →";
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

    const decisions = state.controls.reduce((accumulator, control) => {
      const members = control.members && control.members.length ? control.members : [{
        destination_id: control.input.dataset.page2ReviewDestinationId || "",
        requirement_group_id: control.input.dataset.page2ReviewGroupId || "",
      }];
      const decision = control.input.checked ? "ADAPTATION_REQUIRED" : "NO_ADAPTATION_REQUIRED";
      members.forEach((member) => {
        accumulator.push({
          destination_id: member.destination_id || "",
          requirement_group_id: member.requirement_group_id || "",
          decision,
        });
      });
      return accumulator;
    }, []);

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
      if (productionUrl) {
        window.location.assign(productionUrl);
        return;
      }
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
  } else {
    const initialPanel = panels.values().next().value;
    initialPanel.hidden = false;
    initialPanel.classList.add("is-active");
    activePanelId = initialPanel.id;
    syncPanelActiveState(getPanelState(initialPanel));
  }
});