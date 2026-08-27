Status: LOCKED
Last reviewed: 2026-08-27

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
