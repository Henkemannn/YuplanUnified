Status: LOCKED
Last reviewed: 2026-11-06 (Kommun Menyval visual lock appended; portal architecture unchanged)

# Portals Architecture Lock

## Core Rule
Portals are experience and communication layers, not production engines.

## Shared Portal Foundation
Create or reuse a common Portal Foundation where practical:
- scoped authentication and access
- responsive and iPad shell
- published menu presentation
- week and day navigation
- information and messages
- canonical menu identity and data consumption
- portals consume the published or external menu truth.

## Cross-domain Portal Rule
Portal Foundation is shared platform infrastructure and must not be designed as Kommun-only.

Shared or potentially shared portal capabilities include:
- scoped authentication and portal identity
- published menu consumption
- week and day context
- explicit user choices or confirmations
- status and progress
- reminders and communication
- responsive and iPad shell

Business-specific adapters own their own domain context and must not be forced into one generic domain model merely to share portal capabilities.

Kommun is the first Portal Foundation adapter, not the definition of the portal platform.

Kommun-specific portal context may include:
- Department scope
- residents and resident counts
- department dietary and deviation context
- explicit department menu choices

`DepartmentPortalScope`, `Department`, and `department_menu_choices` are valid Kommun-specific implementations. They must not become the generic Portal Foundation model.

Offshore must be able to reuse the same Portal Foundation while using offshore-specific scope and context such as:
- installation, vessel or site
- crew or section context
- published offshore menu presentation
- relevant confirmations, communication and handover-oriented portal functions

Future shared portal concepts should use domain-neutral naming where the concept is genuinely shared. For example, a future shared week-status concept should be framed as portal-level status rather than hard-coded as a department-only platform concept.

Do not prematurely generalize away valid Kommun or Offshore domain models. Reuse should happen through shared contracts, services and adapters where the behavior is truly shared.

## Avdelningsportal
- scoped to a department.
- shows published menu.
- shows menu choices.
- can show relevant registered dietary and deviation information.
- communication and information from kitchen.
- residents and special-diet production statistics are read-only.
- portal itself must not become a second writer of production truth.
- menu choice is a legitimate portal-owned user action.
- preserve separation between explicit department menu choice and kitchen operational Alt2 or drift state.
- reuse useful existing portal service, API, and UI work rather than restart.
- menu-facing Dish names use effective_menu_name.
- portals must not read a cook's private Work Menu or COW Dish as external menu truth.
- operational or private Work Menu changes only become external portal truth if they are deliberately promoted or published through the proper publication flow.

## Kommun Department Menyval — visually accepted UI contract (2026-11-06)

The product owner approved the authenticated Department Portal **desktop light and dark** menu-choice appearance at code checkpoint `1ff5dbef6336feac26943cafce09053ddc13dcd4`. This is a **visual/interaction layout lock**, not a claim that the entire portal is final pilot GO.

- Canonical published menu, saved department choices, ETag/conflict/submit flow and scoped access remain the only truth; never replace them during visual work.
- Seven days follow the page's normal vertical scroll, not a nested height-limited pane with invisible scrollbar.
- On desktop, weekday Alt 1 / Alt 2 are two equally sized, clearly aligned choice areas; selected state is visibly distinct and must remain accessible.
- A single-option day shows the noninteractive Alt 1 dish in the left choice column and an informational **"Endast ett lunchalternativ idag"** in the right column on the **same row** (one line at standard desktop width), not a second stacked full-width card. Mobile may stack naturally.
- Dessert and Kvällsmat are clearly separated read-only entries in their own row beneath lunch, spanning the lunch content area; they are not part of Alt 2.
- Use shared App Shell theme tokens for light/dark backgrounds/text; keep subtle borders and separation between days, readable status/progress and touch-sized controls. No extra nested card frames or large decorative shadows.
- Preserve the accepted layout unless the product owner explicitly requests a change or a reproducible regression is proven. Changes require real before/after review at affected desktop/iPad widths and focused UI tests. Static CSS tests alone are insufficient.
- Reference regression tests: `static/tests/portal_department_week_layout_contract.test.js`, `portal_department_week_scroll_contract.test.js` and `portal_department_week_theme_contract.test.js`. Product owner accepted desktop visuals; iPad/mobile live checks and choice/submit interactions remain in Kommun 1.1 final acceptance. Approved screenshots are in project conversation but have not been committed as a repository visual baseline.
- The separate legacy standalone `static/tests/portal_department_week_choice.test.js` currently reports 9 failures against obsolete-looking DOM fixture markup; do not silently rewrite it or reopen the accepted layout. Investigate in the final regression gate. Current operational status belongs to `docs/KOMMUN_1_1_LIVE_ACCEPTANCE.md`.

## Mässportal
- same general Portal Foundation where useful.
- published menu.
- allergens and food information.
- meal times.
- practical and crew information.
- later reporting and communication functions.
- does not own menu or production truth.

## External Services
- Integrate strong existing external services first when Yuplan does not create unique value by rebuilding them.
- Normalize external data through Yuplan adapters before presentation.
- Offshore weather/marine information may be added from installation coordinates where useful.
- Weather/marine presentation should expose source and last update time.
- Yuplan must not present external weather/marine data as certified navigation or safety status unless the source/product explicitly supports that claim.
- External-service integrations must not become new menu or production sources of truth.

Existing legacy or current portal variants are reference material, not automatically canonical implementations.
