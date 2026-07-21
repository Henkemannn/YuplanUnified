# Offshore Cook Operational View

## Product purpose
The cook operational view is a read-only Offshore page for daily service awareness. It shows the selected day, the current or next applicable work period, the day’s service items, and a bounded lookahead into upcoming services.

## Intended users and roles
The page is available to the Offshore viewer roles defined by the module gate: `viewer`, `cook`, `editor`, `admin`, and `superuser`. The page itself is read-only for every role.

## Route and access policy
- Exact route: `GET /offshore/operations`
- Endpoint name: `offshore2.operations`
- Authentication: handled by the Offshore module gate and `@require_roles(*VIEWER_ROLES)`.
- Tenant resolution: taken from the active Offshore context resolved by `resolve_active_context()`.
- Site resolution: taken from the active Offshore context resolved by `resolve_active_context()`.
- Allowed roles: `admin`, `superuser`, `cook`, `editor`, `viewer`.
- Invalid or missing scope: `gate_or_404()` blocks disabled feature access; `_context_or_redirect()` either redirects to site selection or returns a forbidden response when the active context is missing or mismatched.
- Cross-tenant behavior: if the current context does not match the requested tenant, the active site is cleared and the request follows the existing redirect/forbidden path.
- Cross-site behavior: the page does not bypass active site resolution; it relies on the same Offshore context guard as the rest of the module.
- Write methods: none. The route is `GET` only and does not mutate state inline.

## Selected local date behavior
- Default selected date: today in the installation timezone, or `Europe/Oslo` when the installation timezone cannot be resolved.
- Explicit `?date=YYYY-MM-DD`: parsed with `date.fromisoformat` and used as the selected local date.
- Invalid date: redirected back to `/offshore/operations` without applying the invalid value.
- Previous navigation: links to the previous local day by subtracting one day from the selected date.
- Next navigation: links to the next local day by adding one day to the selected date.
- Today navigation: links back to `/offshore/operations` with no `date` query parameter.
- Date navigation bounds: the route does not impose a hard navigation boundary. Only the upcoming service section is bounded.

## Installation timezone and fallback behavior
- The view uses `site_timezone_name(tenant_id, site_id)` when an installation exists.
- If timezone resolution fails for any reason, the service falls back to `Europe/Oslo`.
- Local day grouping, period resolution, and UTC window conversion all use the resolved local timezone.
- UTC-to-local conversion: service-event timestamps are converted with `astimezone(zone)` before formatting or grouping.
- DST behavior: because conversion uses the resolved zone via `zoneinfo`, local dates and times follow the site timezone’s daylight-saving rules.

## Period resolution order
The implemented resolution order is:
1. A period containing the selected local date whose status is `active`.
2. A period containing the selected local date whose status is `planned`.
3. The first non-cancelled period that starts after the selected local date.
4. No period.

The containment check is half-open in local time: `starts_at < next_local_midnight` and `ends_at > selected_local_midnight`.

## Day-view structure
The day view is projected into the frozen dataclass `OffshoreOperationalDay` and rendered as:
- a local date label
- a state title/body pair for empty or fallback cases
- a count of service items
- a tuple of service-item read models

The day section is the selected date only. It is not a multi-day list.

## Upcoming-view bound
The upcoming section is a bounded lookahead, not a full agenda.
- Bound: up to 7 days beyond the selected date, or sooner if the relevant period ends earlier.
- Grouping rule: service items are grouped by local date.
- Sorting rule: dates are sorted ascending; items within a date are ordered by the service query order (`starts_at`, then `id`).
- Selected period usage: when a relevant period exists, the lookahead is clipped to that period’s end date; otherwise the view falls back to the selected day only.
- Same-time events: ties are ordered by database id after the timestamp sort.
- Cancelled/completed events: they are still part of the read model if they fall inside the loaded window; the day-state logic separately recognizes fully finished days.

## Service-item read model
The operational service item is the frozen dataclass `OffshoreOperationalServiceItem`.

Exact fields:
- `service_event_id`: Offshore service-event primary key.
- `local_date`: local service date as `YYYY-MM-DD`.
- `local_start_time`: local start time as `HH:MM`.
- `service_label`: display name for the service event.
- `service_code`: service code from the Offshore service event.
- `event_status`: Offshore event status.
- `work_period_id`: owning work-period id.
- `work_period_name`: owning work-period name.
- `work_period_status`: owning work-period status.
- `work_position_label`: resolved work-position label or `None`.
- `menu_title`: resolved menu title or `None`.
- `builder_menu_identity`: Builder menu id/version string or `None`.
- `builder_menu_version`: Builder menu version or `None`.
- `menu_context_status`: Menu Context status or `None`.
- `assignment_source`: Menu Context assignment source or `None`.
- `resolution_reason`: Menu Context resolution reason or `None`.
- `detail_url`: read-only detail URL.
- `manage_url`: management URL for roles that can manage, or `None`.
- `editable`: boolean edit flag derived from role and period status.
- `has_menu_context`: boolean indicating whether a Menu Context row exists.
- `calendar_item`: `CalendarItemRead` read model for the shared calendar contract.

Nullable fields:
`work_position_label`, `menu_title`, `builder_menu_identity`, `builder_menu_version`, `menu_context_status`, `assignment_source`, `resolution_reason`, `manage_url`.

Data shape:
- This dataclass contains read-model values only, plus the nested `CalendarItemRead` projection.
- It does not contain ORM rows or relationships.

## Menu Context mapping
Implemented mapping behavior:
- The service loads `OffshoreServiceEventMenuContext` rows in batch for the period ids in scope.
- A service event with no context row is rendered as missing context.
- A resolved context keeps its stored status, assignment source, and resolution reason.
- An unresolved context keeps its stored status and receives a fallback unresolved reason when needed.
- An unavailable context keeps its stored status and receives a fallback unavailable reason when needed.

Resolved menu title source:
- First choice: Builder reader data from `current_app.extensions["builder_menu_context_flow"].list_menus()` when app context is available.
- Fallback: a safe display string derived from the Builder menu id.
- The service does not read a publication pin directly for the title.

Builder boundary:
- The view reads Builder-facing metadata only.
- It does not write to Builder.
- It does not copy components, dishes, recipes, or food records.

## Editable/manage semantics
- `editable` is `True` only when the user role can manage and the owning period is not completed.
- `manage_url` is exposed only when `can_manage` is true.
- The template uses `manage_url` only as a navigation link.
- No inline edit forms or mutation controls exist on the operations page.

## Navigation and dashboard entry point
- `modules/offshore2/navigation.py` adds an `operations` nav item pointing to `/offshore/operations`.
- `templates/offshore2/dashboard.html` promotes `Open today's operations` as the primary Offshore CTA.
- The dashboard also keeps settings as the secondary manager action.

## Empty/setup states
Implemented states include:
- no installation settings
- no applicable period
- upcoming period only
- period with no services
- missing Menu Context
- unresolved Menu Context
- unavailable publication
- all events cancelled/completed
- normal resolved day

The page renders state titles and bodies from the Offshore i18n table.

Explicit test coverage exists for:
- access and dashboard entry
- invalid date redirect
- period resolution and Menu Context states
- timezone and DST conversion
- no installation and no applicable period behavior
- no migration / no persistent-calendar-row proof

## Query strategy
- Work periods are loaded with one bounded query by `tenant_id` and `site_id`, ordered by `starts_at` and `id`.
- Service events are loaded with one bounded query by `tenant_id`, `site_id`, and a local-date-derived UTC window.
- Menu Context rows are loaded in batch for the period ids in scope.
- Work positions are loaded in batch for the work-position ids in scope.
- Builder menus are queried once through the extension reader when app context is available and there are menu ids to resolve.
- There is no DB-level N+1 on the operations path.
- The remaining per-event lookup against in-memory period rows is linear in Python, not a database N+1.

## Read-only / no-write rule
- The route is GET-only.
- The service builds projections only.
- No persistence occurs in the operations page path.
- No Builder mutation occurs.
- No Menu Context mutation occurs.
- No calendar persistence occurs.

## No-migration rule
- This slice adds no migration.
- It does not alter models or tables.

## Future prep / freezer / handover seams
- The dashboard intentionally reserves roadmap wording for future operational surfaces, but no prep, freezer, order, or handover write flow is implemented here.
- The operations page exposes only read-only seams for later expansion: period summary, day summary, upcoming-day grouping, and safe read-model slots.
- Any future prep/freezer/handover work must be added as separate functionality without changing this read contract.

## Explicit out-of-scope items
- No persistence or migrations.
- No POST/PUT/PATCH/DELETE route on the operations page.
- No inline management forms.
- No Builder writes.
- No Menu Context writes.
- No new calendar storage.
- No prep, freezer, order, or handover implementation.
- No component/dish/recipe/food-data copying.