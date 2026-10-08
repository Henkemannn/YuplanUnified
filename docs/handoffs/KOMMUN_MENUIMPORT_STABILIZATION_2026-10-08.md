# Kommun Menyimport — Stabilization / Shared Modal Handoff

Status: ACTIVE / UNCOMMITTED  
Date: 2026-10-08  
Documentation branch only: `handoff/kommun-1-1-2026-10-07`  
Active local development branch remains: `feat/planera-app-shell-2026-03-03`

## 1. Stable checkpoint and safety state

Latest stable committed checkpoint:

`a0c84db762567c03b68fac8a3b66457c5358ad23`  
`fix(kommun): harden weekview pilot feature flag`

All Menyimport work after this checkpoint remains local and uncommitted.

Known safety archives:
- `C:\Users\Henrik Jonsson\Yuplan Unified\backups\YuplanUnified_PRE_RECOVERY_2026-10-07_201644.tar.gz`
- `C:\Users\Henrik Jonsson\Yuplan Unified\backups\YU_MENYIMPORT_STABILIZATION_SNAPSHOT_2026-10-08_10-49-40.zip`

Do not use remote development branch state as proof of current local source.

## 2. Closed Kommun gates

Desktop functional gates remain CLOSED:
- Department / Kostbehov
- Kostbehov lifecycle
- Serveringsanpassningar
- Weekview
- Weekview feature-flag hardening

Responsive work remains deliberately PARKED until one later global pass.

## 3. Menyimport product contract remains locked

Canonical ownership:
- Builder owns Dish / Composition / Components / library identity and shared editors.
- Week surface owns year/week, day, meal_slot and placement/action context.
- Rättbibliotek is a selector only.
- `static/js/builder_composition_search.js` remains the canonical shared composition-search runtime.

Resolved row actions:
- Dish-name click -> existing shared Dish editor.
- `⋯ -> Öppna rätt` -> exact same shared Dish editor.
- `⋯ -> Byt rätt` -> Rättbibliotek selector -> canonical `composition_id`.
- `⋯ -> Ta bort från menyn` -> remove placement only.

No direct Builder mount into the week parent App Shell.

## 4. What happened during stabilization

Menyimport became visually and architecturally unstable after several local recovery attempts.

Observed regressions included:
- shared Dish editor appearing as a full/large white page-like surface
- picker iframe blocked by Firefox framing policy
- host appearing at the bottom of the Menyimport document
- duplicate modal/card surfacing
- competing modal ownership between parent host and child surfaces

The important correction from real Firefox acceptance:
- Direct Dish click DOES work.
- `Öppna rätt` DOES open the shared Dish editor.
- `Byt rätt` DOES reach Rättbibliotek after the frame-policy fix.
- The active problem is now shell/presentation ownership, not composition resolution or core action wiring.

## 5. Proven CSS corruption and repair

`static/css/menu_editor.css` was found to contain malformed/corrupted Menyimport host CSS:
- duplicated/nested `.menu-editor-builder-host` opening
- stray truncated fragment around backdrop/background
- broken brace alignment
- later conflicting full-viewport panel/frame override

A narrow single-file repair was applied locally:
- one authoritative root host block
- fixed overlay positioning restored
- backdrop block valid
- centered constrained panel restored
- later 100vw/100vh conflicting override removed
- `git diff --check -- static/css/menu_editor.css` reported clean for that file

This repair is NOT yet committed.

Real Firefox after repair:
- shared Dish editor opens as overlay again
- Rättbibliotek opens
- visual result is still rejected because parent host paints a large white surface around child cards and the frost/sizing does not match the accepted Yuplan modal feel

## 6. Frame-policy fix

A narrow local security change currently allowlists exactly:
- `/builder-editor-host`
- `/builder-composition-picker`

for same-origin framing.

Default framing policy remains DENY for ordinary routes.

This fixed the Firefox iframe refusal for Rättbibliotek.

Current status: KEEP candidate. Do not broaden route matching.

## 7. Offshore reference and architecture conclusion

Offshore has a working modal interaction and was used as the visual/behavioral reference.

Important conclusion:
- Do NOT copy Offshore modal code into Menyimport.
- Offshore is currently feature-local and duplicates generic modal mechanics.
- Mirroring Offshore would create another duplicate implementation.

Existing shared modal infrastructure already exists:
- `templates/ui/_menu_modal.html`
- `static/css/app_shell.css`
- `static/js/menu_modal.js`

The repository currently duplicates modal responsibilities across shared shell, Offshore, Menyimport and Builder-related hosts.

## 8. New architecture rule — REUSE-BEFORE-BUILD

Locked rule:

Before implementing any generic UI behavior:
1. Search for an existing shared primitive.
2. If a shared primitive exists, reuse it.
3. If equivalent behavior exists only feature-locally, extract/generalize it before adding a second feature-local copy.
4. Only create a new primitive if no equivalent exists and architecture approval is explicit.
5. Feature-local duplication of generic behavior requires explicit approval.

Applies to at least:
- modal / overlay shell
- picker / selector
- search
- toast / notification
- drawer
- tabs
- loading state
- empty state
- confirmation dialog

Business modules must not independently own generic shell mechanics.

## 9. Shared modal direction

Canonical shared modal API name:

`YuplanModalHost`

Important implementation decision:
- Do NOT create a new parallel runtime file such as `static/js/yuplan_modal_host.js` in the first gate.
- Extend the EXISTING shared modal infrastructure in `static/js/menu_modal.js`.
- Existing `showModal()` / `hideModal()` behavior must remain compatible.

Two required visual ownership modes:

### shell-owned-card
Shared modal shell owns:
- backdrop
- card background
- radius
- shadow
- sizing
- generic open/close mechanics

### child-owned-card
Used when embedded child already paints its own modal/card, e.g.:
- shared Dish editor
- Rättbibliotek

Shared shell owns:
- full-screen overlay
- frost/dim backdrop
- centering
- viewport boundary
- z-index
- scroll lock
- Escape/backdrop close
- focus restore
- iframe hosting mechanics

Shared shell must NOT paint:
- large white outer card
- duplicate radius
- duplicate shadow

## 10. Safety override for first shared-modal gate

The first shared-modal implementation must be ADDITIVE.

Non-negotiable safety rules:
- Existing working `showModal()` / `hideModal()` paths remain functionally unchanged.
- Existing consumers are not migrated in the first gate.
- Offshore is untouched.
- Weekview is untouched.
- Builder is untouched.
- Picker internals are untouched.
- Menyimport is the ONLY pilot consumer of the new shared API.
- If the shared primitive requires changing existing legacy modal semantics, STOP.

Blast radius target:
- new shared API surface
- Menyimport adapter only

## 11. Current pending Copilot task

Copilot is currently being asked to:
1. map every current `showModal` / `hideModal` definition and caller with file/line evidence
2. prepare a NON-APPLIED additive patch for the shared modal primitive + Menyimport adapter
3. keep the patch small and reviewable
4. not modify working legacy consumers

The patch must be reviewed before application.

No implementation should proceed if the mapping shows that working legacy consumers must change.

## 12. Commit strategy

Do NOT commit the current Menyimport stabilization work yet.

Commit only after:
- shared modal direction is accepted
- Menyimport direct Dish open works in real Firefox
- `Öppna rätt` matches the same behavior
- `Byt rätt` opens Rättbibliotek correctly
- only one visible modal/card surface remains
- frost/backdrop/sizing are accepted
- focused tests pass
- diff is understood
- no whitespace/line-ending collateral remains

After acceptance, create a coherent checkpoint before continuing broader Menyimport work.

## 13. Project-lead rule for Copilot

Workflow remains:

1 order -> 1 Copilot report -> review -> next order.

Every implementation order must define allowed production files.

If Copilot needs another production file:
STOP AND REPORT.

Do not:
- migrate adjacent modules
- refactor while here
- create parallel runtimes
- create feature-local duplicate primitives
- follow side effects into Offshore
- commit before user acceptance

## 14. One-line current state

**Kommun desktop core and Weekview remain closed; Menyimport domain/action wiring is largely alive again, but modal-shell ownership is being stabilized by moving toward one additive shared YuplanModalHost built on the existing shared modal infrastructure; Menyimport will be the first pilot consumer while all currently working modal consumers remain untouched.**
