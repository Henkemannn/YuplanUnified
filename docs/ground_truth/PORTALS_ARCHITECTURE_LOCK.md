Status: LOCKED
Last reviewed: 2026-08-29

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
