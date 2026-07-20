# Offshore Menu Context

## Purpose

Offshore treats the service event as the dated operational anchor.
Builder owns the canonical menu content and publication identity.
Offshore owns the local site, timezone, operational period, and the contextual snapshot used to place a service event onto the correct cycle slot.

This contract keeps menu content authoritative in Builder while letting Offshore record only the operational context needed to resolve and manage a service event.

## Domain Model

### `OffshoreServiceEventMenuContext`

Each row stores one resolved context for one service event.

Fields:

- `id`
- `tenant_id`
- `site_id`
- `work_period_id`
- `service_event_id`
- `service_date`
- `menu_cycle_id`
- `start_menu_cycle_slot_id`
- `menu_cycle_slot_id`
- `menu_cycle_index`
- `service_key`
- `resolution_status`
- `assignment_source`
- `match_status`
- `resolution_reason`
- `manual_note`
- `builder_publication_pin_id`
- `builder_publication_year`
- `builder_publication_week`
- `builder_menu_id`
- `builder_menu_version`
- `created_at`
- `updated_at`

Constraints and invariants:

- one context per service event via `uq_offshore_service_event_menu_contexts_service_event_id`
- `resolution_status` values: `resolved`, `unresolved`, `unavailable`, `manual`
- `assignment_source` values: `automatic`, `manual`
- `match_status` values: `matched`, `missing`, `ambiguous`, `withdrawn`
- `withdrawn` is reserved by schema but is not currently emitted by the resolver

### `OffshoreWorkPeriod.start_menu_cycle_slot_id`

`OffshoreWorkPeriod` includes `start_menu_cycle_slot_id` as the anchor slot for cycle resolution.

- nullable foreign key to `offshore_menu_cycle_slots.id`
- `ondelete=SET NULL`
- used when resolving the first cycle slot for a period

### `OffshoreMenuCycleSlot`

No new fields were added to `OffshoreMenuCycleSlot` for Ticket 4.

## Cycle / Date Resolution

Resolution is timezone aware and uses the site installation timezone.

- the service event timestamp is normalized to the site timezone
- `service_date` is the local date of the service event
- `day_offset` is the difference between the local service date and the local period start date
- the cycle anchor comes from `OffshoreWorkPeriod.start_menu_cycle_slot_id` when present
- if no explicit anchor exists, the resolver falls back to the first active slot in the cycle ordered by `cycle_index`, `sort_order`, then `id`
- the configured `cycle_length` controls wrapping, so non-seven-slot cycles are supported
- multiple services on the same date are resolved independently because each service event has its own context row

The idempotent upsert identity is the service event row itself, scoped by `tenant_id`, `site_id`, and `service_event_id`.

## Builder / Publication Integration

Offshore references the weekly Builder publication pin through `CommunBuilderPublicationPin` and the publication repository.

Stored snapshot fields:

- `builder_publication_pin_id`
- `builder_publication_year`
- `builder_publication_week`
- `builder_menu_id`
- `builder_menu_version`

The Offshore context does not copy Builder components, dishes, recipes, or full menu rows. It stores only the publication identity and the local operational context needed for resolution.

## Resolution States

- `resolved`: automatic context resolved to a publication and cycle slot
- `unresolved`: context exists but the cycle-slot match could not be completed
- `unavailable`: no publication exists for the resolved week
- `manual`: a manager explicitly assigned the context

## Match States

- `matched`: the automatic resolution found the expected publication and slot
- `missing`: no publication exists for the resolved week
- `ambiguous`: the cycle-slot resolution could not determine a unique slot
- `withdrawn`: reserved for future states, not currently emitted

## Manual Override Behavior

- automatic sync creates or updates the automatic context row
- a manual assignment cannot be overwritten by automatic refresh
- clearing the manual assignment allows automatic resolution again
- completed periods are protected from automatic refresh overwrites
- future periods may be explicitly refreshed

## Missing / Unavailable Behavior

- a missing publication does not return a 500
- the context remains dated and visible
- publication snapshot fields remain null when no publication exists
- `resolution_reason` records the gap, typically `publication_missing`

## Permissions

- `viewer` and `cook` can read
- `editor` can perform operational management of periods and menu contexts
- `admin` and `superuser` have full management access
- route decorators enforce permissions; controls are not hidden only in the UI

## UI / Routes

Period detail exposes the persisted context and operational actions.

Read routes:

- `GET /offshore/periods/<period_id>`
- `GET /offshore/periods/<period_id>/service-events/<event_id>/menu-context`
- `GET /offshore/periods/<period_id>/service-events/<event_id>/calendar-readiness`

Management routes:

- `POST /offshore/periods/<period_id>/service-events/<event_id>/menu-context/refresh`
- `POST /offshore/periods/<period_id>/service-events/<event_id>/menu-context/manual`
- `POST /offshore/periods/<period_id>/service-events/<event_id>/menu-context/clear`

Period detail shows the service event date/time, cycle slot, menu title, context status, publication snapshot details, and the refresh/manual/clear actions for authorized users.

The dashboard shows next service, menu context status, unresolved count, and setup guidance when configuration is incomplete.

## Calendar Readiness

The calendar-readiness route returns a non-persistent JSON payload with these fields:

- `source_module`
- `source_type`
- `source_id`
- `tenant_id`
- `site_id`
- `starts_at`
- `title`
- `category`
- `status`
- `menu_context_status`
- `detail_url`
- `editable`

There is no `CalendarItem` table in this implementation. The route exists as an adapter payload for future calendar integration.

## Migration

Migration `0028_add_offshore_v2_menu_context` extends `0027_add_offshore_v2_periods`.

Expected roundtrip behavior:

- `0027 -> 0028`: adds `offshore_service_event_menu_contexts` and `offshore_work_periods.start_menu_cycle_slot_id`
- `0028 -> 0027`: removes the context table and the start-slot column
- `0027 -> 0028`: restores the same schema shape without creating demo rows

The migration is designed to leave no seed/demo context rows behind.

## Out of Scope

This contract does not define:

- generic calendar storage
- reminders or messages
- PM workflows
- prep planning
- freezer planning
- purchasing workflows
- Planera 2.0 behavior
- staffing logic
- portal behavior
