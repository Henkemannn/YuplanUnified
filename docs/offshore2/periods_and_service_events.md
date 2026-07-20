# Offshore Periods and Service Events

Ticket 3 introduces the persistent period layer for Offshore v2. The implementation is intentionally snapshot-based: a template defines repeatable structure, and a concrete work period stores the actual generated service events for one installation/site at one point in time.

## Core model split

- `OffshorePeriodTemplate` is the repeatable plan definition.
- `OffshorePeriodTemplateEvent` is a template-level service slot.
- `OffshoreWorkPeriod` is one concrete generated period.
- `OffshoreServiceEvent` is one concrete service occurrence inside a work period.

## Snapshot semantics

Generation copies template events into service events. Existing work periods do not follow later template edits. This is deliberate so the period history remains stable after generation.

## Timezone convention

- Installation timezone is read from Offshore settings for the active tenant/site.
- User input enters the system as local wall time.
- Concrete stored timestamps are UTC-aware datetimes.
- Rendering converts stored UTC datetimes back to the site timezone.

## Overlap behavior

Overlapping work periods are allowed. The service detects overlaps and the dashboard surfaces them as warnings. Overlap is not blocked.

## Menu-cycle relationship

Work periods may reference a menu cycle, but the period layer does not own Builder content. The menu cycle link is only a site-scoped planning reference.

## Future Builder/Menu Context integration

Ticket 3 stops at period templates, concrete periods, and service events. Builder menu/version projection and meal-slot resolution remain out of scope for this slice.

## Out of scope for Ticket 3

- Period grid and day-slot editing
- Builder version pinning per meal slot
- Planned override semantics
- Portion override rules beyond snapshot storage
- Full crew portal behavior
- Any legacy Offshore rewrite

## Verified contract points

- period end is computed from `duration_days`
- active template events generate service events
- `day_offset` and local time resolve into concrete datetimes
- generated service events keep `source_template_event_id`
- invalid generation rolls back the transaction
- duplicate template events are rejected by service validation
- same-site and same-tenant scope is enforced for template, period, menu-cycle, and work-position references