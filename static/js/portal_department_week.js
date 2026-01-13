document.addEventListener("DOMContentLoaded", () => {
  const root = document.getElementById("portal-dept-week-root");
  if (!root) return;
  const params = new URLSearchParams(window.location.search);
  const demoMode = params.get("demo") === "1"; // Non-blocking conflict UX for first-time demo
  // Expose globally for showConflictOverlay logic
  window.portalDemoMode = demoMode;
  // Safety: ensure conflict overlay is hidden (user reported persistent overlay on initial load)
  const initialOverlay = document.getElementById("portal-conflict-overlay");
  if (initialOverlay) initialOverlay.hidden = true;
  let menuChoiceEtag = root.dataset.menuChoiceEtag;
  const year = parseInt(root.dataset.year || "0", 10);
  const week = parseInt(root.dataset.week || "0", 10);
  const statusEl = document.getElementById("portal-status-message");
  // Popup elements
  const overlay = document.getElementById("portal-menu-overlay");
  const modal = overlay ? overlay.querySelector(".portal-menu-modal") : null;
  const closeBtn = overlay ? overlay.querySelector(".portal-menu-close-btn") : null;
  const dayEl = overlay ? overlay.querySelector(".portal-menu-day") : null;
  const lunchAlt1El = overlay ? overlay.querySelector(".portal-menu-lunch-alt1") : null;
  const lunchAlt2El = overlay ? overlay.querySelector(".portal-menu-lunch-alt2") : null;
  const dessertEl = overlay ? overlay.querySelector(".portal-menu-dessert") : null;
  const kvallsmatEl = overlay ? overlay.querySelector(".portal-menu-kvallsmat") : null;

  function setStatus(message, kind) {
    if (!statusEl) return;
    statusEl.innerHTML = message || "";
    if (kind) statusEl.dataset.kind = kind; else delete statusEl.dataset.kind;
  }
  // Expose for external helpers (bindConflictReloadIfVisible defined outside this closure)
  window.portalSetStatus = setStatus;

  function applySelectionHighlight(weekdayName, selectedAlt) {
    const rows = document.querySelectorAll(".portal-day-row");
    rows.forEach((row) => {
      const dayNameCell = row.querySelector(".portal-day-name");
      if (!dayNameCell) return;
      const label = dayNameCell.textContent || "";
      if (!label.includes(weekdayName)) return;
      const alt1 = row.querySelector(".portal-alt1-cell");
      const alt2 = row.querySelector(".portal-alt2-cell");
      if (alt1) {
        const isSelected = selectedAlt === "Alt1";
        alt1.classList.toggle("portal-alt-selected", isSelected);
        alt1.setAttribute("aria-pressed", isSelected ? "true" : "false");
      }
      if (alt2) {
        const isSelected = selectedAlt === "Alt2";
        alt2.classList.toggle("portal-alt-selected", isSelected);
        alt2.setAttribute("aria-pressed", isSelected ? "true" : "false");
      }
    });
  }

  let autoRetriedOnce = false; // for demo mode auto-retry
  function handleAltClick(cell) {
    const weekdayName = cell.dataset.weekday;
    const selectedAlt = cell.dataset.selectedAlt;
    if (!weekdayName || !selectedAlt || !menuChoiceEtag) return;
    setStatus("Sparar val…", "saving");
    // Optimistic update
    applySelectionHighlight(weekdayName, selectedAlt);
    fetch("/portal/department/menu-choice/change", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "If-Match": menuChoiceEtag,
      },
      body: JSON.stringify({ year, week, weekday: weekdayName, selected_alt: selectedAlt }),
    })
      .then(async (resp) => {
        if (resp.status === 200) {
          const data = await resp.json();
          if (data && data.new_etag) {
            menuChoiceEtag = data.new_etag;
            root.dataset.menuChoiceEtag = data.new_etag;
          }
          setStatus("Val sparat.", "ok");
        } else if (resp.status === 412) {
          // Concurrency conflict.
          if (demoMode) {
            // Demo: try silent refresh; if still stale, do a one-time full reload
            setStatus("Demo: uppdaterar…", "conflict");
            attemptSilentRefresh().then((ok) => {
              if (ok) {
                setStatus("Demo: uppdaterad – försök igen.", "ok");
              } else if (!autoRetriedOnce) {
                autoRetriedOnce = true;
                setStatus("Demo: laddar om för att komma i synk…", "conflict");
                const url = new URL(window.location.href);
                url.searchParams.set("r", Date.now().toString());
                window.location.assign(url.toString());
              } else {
                setStatus("Demo: kunde inte uppdatera.", "error");
              }
            }).catch(() => {
              setStatus("Demo: fel vid uppdatering.", "error");
            });
            return;
          }
          // Normal mode: attempt silent refresh of portal state so user can retry without full reload.
          setStatus("Konflikt upptäckt – försöker uppdatera…", "conflict");
          attemptSilentRefresh().then((ok) => {
            if (ok) {
              setStatus("Uppdaterad – försök igen.", "ok");
              return; // Skip showing overlay since we've refreshed.
            }
            // Fall back to overlay reload UX if refresh failed.
            setStatus("Informationen är utdaterad – välj åtgärd.", "conflict");
            showConflictOverlay();
          }).catch(() => {
            // On unexpected error just show overlay
            showConflictOverlay();
          });
          return;
        } else if (resp.status === 400) {
          setStatus("Ogiltig förfrågan – försök igen eller kontakta admin.", "error");
        } else {
          setStatus("Ett fel uppstod vid sparning.", "error");
        }
      })
      .catch(() => {
        setStatus("Nätverksfel – försök igen.", "error");
      });
  }

  function attachHandlers() {
    const cells = document.querySelectorAll(".portal-alt1-cell, .portal-alt2-cell");
    cells.forEach((cell) => {
      cell.addEventListener("click", () => handleAltClick(cell));
      cell.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          handleAltClick(cell);
        }
      });
    });
    attachMenuHandlers();
    // bindConflictReloadIfVisible(); // Removed - overlay permanently disabled
  }

  function openMenuPopup(btn) {
    if (!overlay || !modal) return;
    const weekday = btn.dataset.weekday || "";
    const date = btn.dataset.date || "";
    const lunchAlt1 = btn.dataset.lunchAlt1 || "";
    const lunchAlt2 = btn.dataset.lunchAlt2 || "";
    const dessert = btn.dataset.dessert || "";
    const kvallsmat = btn.dataset.kvallsmat || "";
    if (dayEl) dayEl.textContent = `${weekday} – ${date}`;
    if (lunchAlt1El) lunchAlt1El.textContent = lunchAlt1 || "Ingen menytext";
    if (lunchAlt2El) lunchAlt2El.textContent = lunchAlt2 || "Ingen menytext";
    if (dessertEl) dessertEl.textContent = dessert || "Ingen dessert";
    if (kvallsmatEl) kvallsmatEl.textContent = kvallsmat || "Ingen kvällsmat";
    overlay.hidden = false;
    if (modal) modal.focus();
  }

  function closeMenuPopup() {
    if (!overlay) return;
    overlay.hidden = true;
  }

  function attachMenuHandlers() {
    const menuButtons = document.querySelectorAll(".portal-menu-btn");
    menuButtons.forEach((btn) => {
      btn.addEventListener("click", () => openMenuPopup(btn));
      btn.addEventListener("keydown", (ev) => {
        if (ev.key === "Enter" || ev.key === " ") {
          ev.preventDefault();
          openMenuPopup(btn);
        }
      });
    });
    if (closeBtn) closeBtn.addEventListener("click", closeMenuPopup);
    if (overlay) {
      overlay.addEventListener("click", (ev) => {
        if (ev.target === overlay) closeMenuPopup();
      });
    }
    document.addEventListener("keydown", (ev) => {
      if (ev.key === "Escape" && overlay && !overlay.hidden) closeMenuPopup();
    });
  }

  attachHandlers();
  // Auto attempt refresh if overlay somehow visible on initial load
  const initialConflict = document.getElementById("portal-conflict-overlay");
  if (initialConflict && !initialConflict.hidden) {
    attemptSilentRefresh().then((ok) => {
      if (ok) {
        initialConflict.hidden = true;
        root.classList.remove("portal-conflict-active");
        setStatus("Uppdaterad – försök igen.", "ok");
      }
    });
  }

  // Phase 7: periodic ETag check (every 20s) to detect remote changes
  const syncIndicator = document.getElementById("portal-sync-indicator");
  function checkSync() {
    if (!root || !syncIndicator) return;
    const current = root.dataset.menuChoiceEtag;
    const year = root.dataset.year;
    const week = root.dataset.week;
    if (!current || !year || !week) return;
    const url = `/portal/department/week?year=${year}&week=${week}`;
    fetch(url, { method: "HEAD" })
      .then((resp) => {
        const etag = resp.headers.get("ETag");
        if (etag && etag !== current) {
          syncIndicator.classList.add("stale");
          syncIndicator.textContent = "Ej synkad – ladda om";
        }
      })
      .catch(() => { /* ignore network errors for indicator */ });
  }
  setInterval(checkSync, 20000);
});

function showConflictOverlay() {
  // Overlay permanently disabled – never show modal.
  const conflict = document.getElementById("portal-conflict-overlay");
  const root = document.getElementById("portal-dept-week-root");
  if (conflict) conflict.hidden = true;
  if (root) root.classList.remove('portal-conflict-active');
  console.log("[portal] Conflict overlay suppressed");
  return;
}

function _showConflictOverlayActual(root, conflict, reloadBtn, infoEl, retryBtn) {
  if (conflict) {
    conflict.hidden = false;
    if (root) root.classList.add("portal-conflict-active");
  }
  const statusEl = document.getElementById("portal-status-message");
  if (statusEl) {
    statusEl.textContent = "";
    statusEl.setAttribute("aria-hidden", "true");
  }
  if (reloadBtn) reloadBtn.focus();
  bindConflictReloadIfVisible();
  if (infoEl) {
    infoEl.hidden = false;
    infoEl.textContent = "Data har ändrats av någon annan. Uppdatera innan du sparar igen.";
  }
  if (retryBtn && !retryBtn.dataset.bound) {
    retryBtn.dataset.bound = "1";
    retryBtn.addEventListener("click", () => {
      retryBtn.disabled = true;
      if (infoEl) infoEl.textContent = "Försöker hämta…";
      attemptSilentRefresh().then((ok2) => {
        if (ok2) {
          if (conflict) conflict.hidden = true;
          if (root) root.classList.remove("portal-conflict-active");
          if (typeof window.portalSetStatus === 'function') window.portalSetStatus("Uppdaterad – försök igen.", "ok");
        } else {
          if (infoEl) infoEl.textContent = "Misslyckades. Använd Ladda om.";
          retryBtn.disabled = false;
        }
      }).catch(() => {
        if (infoEl) infoEl.textContent = "Fel vid hämtning. Använd Ladda om.";
        retryBtn.disabled = false;
      });
    });
  }
}

// Fetch latest week JSON to update menu choice etag & selections without full page reload.
async function attemptSilentRefresh() {
  try {
    const root = document.getElementById("portal-dept-week-root");
    if (!root) return false;
    const year = parseInt(root.dataset.year || "0", 10);
    const week = parseInt(root.dataset.week || "0", 10);
    const url = new URL(window.location.origin + `/portal/department/week?year=${year}&week=${week}`);
    url.searchParams.set("_", Date.now().toString()); // cache-bust
    console.log("[portal] silent refresh fetch", url.toString());
    const resp = await fetch(url.toString(), { headers: { "Accept": "application/json" }, credentials: "same-origin" });
    if (!resp.ok) {
      console.warn("Silent refresh response not OK", resp.status);
      // Fallback: fetch UI HTML and try to extract etag from root dataset
      const uiUrl = new URL(window.location.origin + `/ui/portal/department/week?year=${year}&week=${week}`);
      uiUrl.searchParams.set("rhtml", Date.now().toString());
      console.log("[portal] fallback HTML fetch", uiUrl.toString());
      try {
        const htmlResp = await fetch(uiUrl.toString(), { credentials: "same-origin" });
        if (!htmlResp.ok) return false;
        const htmlText = await htmlResp.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(htmlText, "text/html");
        const newRoot = doc.getElementById("portal-dept-week-root");
        if (newRoot && newRoot.dataset.menuChoiceEtag) {
          root.dataset.menuChoiceEtag = newRoot.dataset.menuChoiceEtag;
          console.log("[portal] fallback HTML updated etag", root.dataset.menuChoiceEtag);
          return true;
        }
      } catch (e2) {
        console.warn("Fallback HTML refresh failed", e2);
      }
      return false;
    }
    const payload = await resp.json();
    if (!payload || !payload.etag_map || !payload.etag_map.menu_choice) return false;
    // Update etag
    root.dataset.menuChoiceEtag = payload.etag_map.menu_choice;
    // Reapply current selections from payload days
    if (Array.isArray(payload.days)) {
      payload.days.forEach((d) => {
        if (d && d.choice && d.choice.selected_alt && d.weekday_name) {
          applySelectionHighlight(d.weekday_name, d.choice.selected_alt);
        }
      });
    }
    console.log("[portal] silent refresh success, new etag", root.dataset.menuChoiceEtag);
    return true;
  } catch (e) {
    console.warn("Silent refresh failed", e);
    return false;
  }
}

// Standalone helper so we can bind even if script loads after a pre-existing conflict state
function bindConflictReloadIfVisible() {
  // Permanently disabled - do nothing
  return;
  const overlay = document.getElementById("portal-conflict-overlay");
  const btn = document.getElementById("portal-conflict-reload");
  const dismissBtn = document.getElementById("portal-conflict-dismiss");
  if (!overlay || !btn) return;
  const forceReload = () => {
    try {
      const url = new URL(window.location.href);
      // Remove any existing r param first (URL API replaces automatically but we ensure cleanliness)
      url.searchParams.delete('r');
      url.searchParams.set('r', Date.now().toString());
      // Provide immediate feedback by disabling button and changing text
      btn.disabled = true;
      btn.textContent = 'Laddar…';
      // Hide overlay to reduce perceived "stuck" state
      overlay.hidden = true;
      window.location.assign(url.toString());
    } catch (e) {
      // Fallback
      window.location.reload();
    }
  };
  // Ensure we don't double attach
  if (!btn.dataset.bound) {
    btn.dataset.bound = '1';
    btn.addEventListener('click', forceReload);
    btn.addEventListener('keydown', (ev) => {
      if (ev.key === 'Enter' || ev.key === ' ') {
        ev.preventDefault();
        forceReload();
      }
    });
  }
  if (dismissBtn && !dismissBtn.dataset.bound) {
    dismissBtn.dataset.bound = '1';
    dismissBtn.addEventListener('click', () => {
      overlay.hidden = true;
      document.getElementById('portal-dept-week-root')?.classList.remove('portal-conflict-active');
      const infoEl = document.getElementById('portal-conflict-info');
      if (infoEl) infoEl.hidden = true;
      if (typeof window.portalSetStatus === 'function') {
        window.portalSetStatus("Fortsätter utan uppdatering.", "warn");
      }
    });
  }
  // If overlay already visible (race) focus button
  if (!overlay.hidden) {
    btn.focus();
  }
}
