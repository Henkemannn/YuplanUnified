document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("portal-dept-week-root");
  if (!root) return;

  const year = Number.parseInt(root.dataset.year || "0", 10);
  const week = Number.parseInt(root.dataset.week || "0", 10);
  let menuChoiceEtag = root.dataset.menuChoiceEtag || "";
  const weekChangeUrl = root.dataset.weekChangeUrl || "/portal/department/menu-choice/change";
  const weekStatusUrl = root.dataset.weekStatusUrl || "";
  const weekSubmitUrl = root.dataset.weekSubmitUrl || "";
  const progressCountEl = document.getElementById("portal-progress-count");
  const weekStateEl = document.getElementById("portal-week-state");
  const statusEl = document.getElementById("portal-status-message");
  const submitButton = document.getElementById("portal-submit-button");
  const weekSelector = document.getElementById("portal-week-selector");
  const scrollOwner = document.getElementById("portal-week-scroll");
  const dayCards = Array.from(document.querySelectorAll("[data-day-card]"));
  const choiceButtons = Array.from(document.querySelectorAll("[data-choice-button]"));

  const WEEKDAY_CODE_BY_LABEL = {
    Måndag: "mon",
    Tisdag: "tue",
    Onsdag: "wed",
    Torsdag: "thu",
    Fredag: "fri",
    Lördag: "sat",
    Söndag: "sun",
  };

  function setStatus(message, kind) {
    if (!statusEl) return;
    statusEl.textContent = message || "";
    if (kind) {
      statusEl.dataset.kind = kind;
    } else {
      delete statusEl.dataset.kind;
    }
  }

  function setWeekState(text) {
    if (weekStateEl) {
      weekStateEl.textContent = text;
    }
  }

  function setWeekStateFromSubmission(statusData) {
    const completed = Number(statusData?.completed_choice_count ?? getCompletedRequiredCount());
    const submissionIsCurrent = Boolean(statusData?.submission_is_current);
    if (submissionIsCurrent) {
      setWeekState("Färdig");
      return;
    }
    if (completed === 0) {
      setWeekState("Ej påbörjad");
      return;
    }
    setWeekState("Påbörjad");
  }

  function getRequiredCards() {
    return dayCards.filter((card) => card.dataset.choiceRequired === "1");
  }

  function getCompletedRequiredCount() {
    return getRequiredCards().filter((card) => {
      const selectedAlt = card.dataset.selectedAlt || "";
      return selectedAlt === "Alt1" || selectedAlt === "Alt2";
    }).length;
  }

  function updateProgressText(completed, required) {
    if (progressCountEl) {
      progressCountEl.textContent = `${completed} av ${required} val gjorda`;
    }
  }

  function syncButtonSelection(card, selectedAlt) {
    card.dataset.selectedAlt = selectedAlt || "";
    card.classList.toggle("is-selected", Boolean(selectedAlt));
    const buttons = Array.from(card.querySelectorAll("[data-choice-button]"));
    buttons.forEach((button) => {
      const isSelected = button.dataset.selectedAlt === selectedAlt;
      button.classList.toggle("is-selected", isSelected);
      button.classList.toggle("portal-alt-selected", isSelected);
      button.setAttribute("aria-pressed", isSelected ? "true" : "false");
    });
    syncDayStatus(card, selectedAlt);
  }

  function syncDayStatus(card, selectedAlt) {
    const statusEl = card.querySelector(".portal-day-row__status");
    if (!statusEl || card.dataset.choiceRequired !== "1") return;
    const isSelected = Boolean(selectedAlt);
    statusEl.textContent = isSelected ? "Val gjort" : "Val krävs";
    statusEl.classList.toggle("portal-day-row__status--done", isSelected);
    statusEl.classList.toggle("portal-day-row__status--required", !isSelected);
  }

  function syncAllSelectionStates() {
    choiceButtons.forEach((button) => {
      const card = button.closest("[data-day-card]");
      if (!card) return;
      const selectedAlt = card.dataset.selectedAlt || "";
      const isSelected = button.dataset.selectedAlt === selectedAlt;
      button.classList.toggle("is-selected", isSelected);
      button.classList.toggle("portal-alt-selected", isSelected);
      button.setAttribute("aria-pressed", isSelected ? "true" : "false");
    });
    dayCards.forEach((card) => syncDayStatus(card, card.dataset.selectedAlt || ""));
    updateProgressText(getCompletedRequiredCount(), getRequiredCards().length);
  }

  function weekdayDisplayToApiCode(weekdayDisplay) {
    return WEEKDAY_CODE_BY_LABEL[String(weekdayDisplay || "").trim()] || "";
  }

  function updateWeekScrollFadeState() {
    if (!scrollOwner) return;
    const hasOverflow = scrollOwner.scrollHeight > scrollOwner.clientHeight + 2;
    const showTopFade = hasOverflow && scrollOwner.scrollTop > 1;
    const showBottomFade = hasOverflow && scrollOwner.scrollTop + scrollOwner.clientHeight < scrollOwner.scrollHeight - 1;
    scrollOwner.classList.toggle("has-scroll-top-fade", showTopFade);
    scrollOwner.classList.toggle("has-scroll-bottom-fade", showBottomFade);
  }

  function bindWeekScrollFadeState() {
    if (!scrollOwner || scrollOwner.dataset.scrollFadeBound === "1") return;
    scrollOwner.dataset.scrollFadeBound = "1";
    const scheduleUpdate = () => {
      window.requestAnimationFrame(updateWeekScrollFadeState);
    };
    scrollOwner.addEventListener("scroll", scheduleUpdate, { passive: true });
    window.addEventListener("resize", scheduleUpdate);
    scheduleUpdate();
  }

  function setSubmitState(statusData) {
    if (!submitButton) return;
    const completed = Number(statusData?.completed_choice_count ?? getCompletedRequiredCount());
    const required = Number(statusData?.required_choice_count ?? getRequiredCards().length);
    const isSubmittable = Boolean(statusData?.is_submittable);
    const submissionIsCurrent = Boolean(statusData?.submission_is_current);

    updateProgressText(completed, required);

    if (submissionIsCurrent) {
      submitButton.textContent = "Färdig";
      submitButton.disabled = true;
      setWeekStateFromSubmission(statusData);
      return;
    }

    submitButton.textContent = "Skicka val till köket";
    submitButton.disabled = !isSubmittable;
    setWeekStateFromSubmission(statusData);
  }

  async function refreshSubmissionState() {
    if (!weekStatusUrl) return;
    try {
      const resp = await fetch(weekStatusUrl, { credentials: "same-origin" });
      if (!resp.ok) return;
      const data = await resp.json();
      setSubmitState(data);
    } catch {
      updateProgressText(getCompletedRequiredCount(), getRequiredCards().length);
    }
  }

  async function saveChoice(card, selectedAlt) {
    const weekdayName = card.dataset.weekdayLabel || "";
    const weekdayCode = weekdayDisplayToApiCode(weekdayName);
    if (!weekdayCode || !selectedAlt || !menuChoiceEtag) return;
    const previousSelectedAlt = card.dataset.selectedAlt || "";
    setStatus("Sparar…", "saving");

    try {
      const resp = await fetch(weekChangeUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "If-Match": menuChoiceEtag,
        },
        body: JSON.stringify({ year, week, weekday: weekdayCode, selected_alt: selectedAlt }),
      });

      if (resp.status === 200) {
        const data = await resp.json();
        if (data?.new_etag) {
          menuChoiceEtag = data.new_etag;
          root.dataset.menuChoiceEtag = data.new_etag;
        }
        syncButtonSelection(card, selectedAlt);
        syncAllSelectionStates();
        await refreshSubmissionState();
        setStatus("Val sparat.", "ok");
        return;
      }

      if (resp.status === 412) {
        syncButtonSelection(card, previousSelectedAlt);
        syncAllSelectionStates();
        setStatus("Veckan har ändrats. Ladda om sidan.", "conflict");
        window.location.reload();
        return;
      }

      syncButtonSelection(card, previousSelectedAlt);
      syncAllSelectionStates();
      setStatus("Kunde inte spara valet.", "error");
    } catch {
      syncButtonSelection(card, previousSelectedAlt);
      syncAllSelectionStates();
      setStatus("Nätverksfel – försök igen.", "error");
    }
  }

  async function submitWeek() {
    if (!weekSubmitUrl || !submitButton) return;
    setStatus("Skickar val till köket…", "saving");
    submitButton.disabled = true;

    try {
      const resp = await fetch(weekSubmitUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ year, week }),
      });

      if (!resp.ok) {
        if (resp.status === 409) {
          setStatus("Veckan är inte komplett ännu.", "error");
        } else {
          setStatus("Kunde inte skicka val till köket.", "error");
        }
        await refreshSubmissionState();
        return;
      }

      const data = await resp.json();
      setStatus("Val skickade till köket.", "ok");
      setSubmitState(data);
    } catch {
      setStatus("Nätverksfel vid inlämning.", "error");
      await refreshSubmissionState();
    }
  }

  function bindEvents() {
    if (weekSelector) {
      weekSelector.addEventListener("change", () => {
        if (weekSelector.value) {
          window.location.assign(weekSelector.value);
        }
      });
    }

    choiceButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const card = button.closest("[data-day-card]");
        const selectedAlt = button.dataset.selectedAlt || "";
        if (!card || !selectedAlt) return;
        saveChoice(card, selectedAlt);
      });
      button.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          button.click();
        }
      });
    });

    if (submitButton) {
      submitButton.addEventListener("click", () => {
        if (!submitButton.disabled) {
          submitWeek();
        }
      });
    }
  }

  bindEvents();
  syncAllSelectionStates();
  bindWeekScrollFadeState();
  setSubmitState({
    completed_choice_count: Number(root.dataset.initialCompletedCount || 0),
    required_choice_count: Number(root.dataset.initialRequiredCount || 0),
    is_submittable: false,
    submission_is_current: false,
  });
  refreshSubmissionState();
});