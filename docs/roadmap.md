# Roadmap – Yuplan Unified

Status: **current operational roadmap, reviewed 2026-10-30**  
Development baseline: `feat/planera-app-shell-2026-03-03` @ `6233b11cd4530ed0261992dc6be18af0357955c7`

**Detailed accepted status, unresolved gaps and decision points:** [Kommun 1.1 current status – 2026-10-30](KOMMUN_1_1_CURRENT_STATUS_2026-10-30.md).  
**Live acceptance ledger:** [Kommun 1.1 – Live Acceptance](KOMMUN_1_1_LIVE_ACCEPTANCE.md).  
**Locked MVP/architecture:** [Ground Truth](ground_truth/README.md).

## DONE – bounded checkpoints, not full pilot GO

- Shared Builder/Menu/Dish/Component foundation: accepted for 1.0; freeze for unrelated polish.
- Planera 2.0 Page1/Page2 and Product2 computation/production foundation: established.
- Page3 production views, four print variants, Specialkost completion UX: accepted earlier (`07376af5` and its predecessors).
- Produktionslistor 2.0: ISO week/year selection, seven-day navigation, full-lunch Page3 links, legacy snapshots preserved (`9399350d`).
- App Shell first-paint dark/light flash: corrected and manually accepted (`6233b11c`); focused test slice **77 passed**.
- Live Gate 01 – clean tenant/site/customer onboarding: **previously GO**, retain as final smoke requirement.

**Test precision:** `2342 passed, 15 skipped` refers to an older automated baseline recorded in the live-acceptance ledger at `04731895`. It is **not** a full regression result for `6233b11c`. The latest 77 green tests are a focused slice, not release proof.

## NOW – Kommun 1.1 Pilot Gate sequence

1. **A–Ö Rapport – read-only census REVIEWED; gate OPEN.** Existing Weekview reporting already consumes the same completion repository as Page3 for marked specialkost cohorts, but not a full Planera 2.0 production result. The coverage route reports legacy meal registrations; coverage HTML and CSV/XLSX differ, its PDF is placeholder and some labels misleading. **Next narrow gate: negative two-tenant access test and minimal report site/department scoping fix, before any report UI or export redesign.** Refer to §4c in the current status document.
2. **Admin menu-choice semantics – OPEN technical decision (revisit only where real A–Ö evidence exposes a gap).** Confirm admin-vs-portal choice precedence and persisted identity, then implement at most an MVP-sized Admin → Menyval overview where needed.
3. **Full clean-customer E2E – PENDING.** Builder publish → Portal choices → Kitchen → Page1/Page2 → Page3 → completion → Weekview → report, including reload/relogin and tenant-scope.
4. **Meal coverage – PENDING verification.** Lunch established; verify Kvällsmat and dessert or make explicit scoped pilot decision. Produktionslistor is currently lunch-only.
5. **Report bridge – PENDING verification.** Confirm current reports consume Product2 cohort quantity/completion instead of only legacy sources; fix only demonstrated gap.
6. **Registered Serveringstillägg – display only (MVP, product decision 2026-10-31).** Show saved serving addon/preference and note beneath department name in Kitchen Weekview. In Produktionslistor add a small **Tillägg** icon next to each relevant **Lunch** action; clicking lists saved addons grouped by type, with department, registered count and department-specific note. **Require the same registered addon/count/note directly under each department in existing kitchen packing lists**, alongside that department's other pack details; do not require a separate lookup. No menu analysis, auto-replacement, generated salad variants, new totals or production engine. **No new Page3 tab** in this gate. Use existing service scope only. See §4b in `KOMMUN_1_1_CURRENT_STATUS_2026-10-30.md`.
7. **Planera 1 / 2.0 parity – PENDING.** Compare real weeks, classify differences, preserve legacy fallback until proven cutover.
8. **iPad UX, error/empty states – PENDING focused final pass.** 1024×768 and 768×1024; only user-visible blockers or high-impact friction.
9. **Release readiness – PENDING.** Full automated regression, cross-tenant security, migrations/staging smoke, final new-customer acceptance; freeze/tag Kommun 1.1 pilot candidate.

These tasks are **gates, not automatic implementation orders**. One order → one Copilot report → review → next order.

## THEN – Offshore 1.0 and Yuplan 1.0

- After Kommun 1.1 is pilot-ready: fresh read-only Offshore census against [Offshore 1.0 MVP lock](ground_truth/OFFSHORE_1_0_MVP_LOCK.md).
- Finish the three Offshore pillars: provisioning, cook operations and crew experience.
- Only then run the combined Yuplan 1.0 release gate.

## OUTSIDE CURRENT MVP

Home, Hotel/Bankett, advanced ingredient conversion and costing, full recipe import, large generic platform rewrites, advanced analytics, and broad new service-booking/asset modules. Future Lab stays separate from pilot blockers.

## Next decision

**Recommendation:** the Rapport census is complete. Start with an evidence-led **report tenant/site authorization gate** (test first, narrow fix). Then inspect the actual Report UI and choose pilot report semantics before repairing misleading exports. Keep the simple registered-only Serveringstillägg display as a separate planned UI gate. Do not restart the A–Ö traversal at Avdelningar. See the linked status report.
