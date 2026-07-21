# Calendar Read Contract

## Purpose

This contract defines a read-only, date-first calendar/timeline feed that can be assembled from domain adapters without introducing new persistence, UI, or write paths.

The implementation is intentionally narrow: it reads existing domain data, normalizes it into a shared item shape, and returns a deterministic feed result for consumers that need a timeline view.

## Domain Ownership

Current ownership is the Offshore domain.

The only implemented adapter is the Offshore reference adapter, which maps Offshore service events into the shared calendar read contract. Builder and Kommun are future adapter targets only; they are not implemented here.

## No-Persistence Rule

This contract does not add calendar tables, calendar ORM models, calendar write services, or calendar migrations.

It is read-only by design. Any future write behavior would be a separate product decision and is out of scope for this contract.

## Core Types

### `CalendarItemRead`

Frozen dataclass with the following exact fields:

- `source_module: str`
- `source_type: str`
- `source_id: str`
- `tenant_id: int`
- `site_id: str | None`
- `starts_at: datetime`
- `ends_at: datetime | None`
- `all_day: bool`
- `title: str`
- `category: str`
- `status: str`
- `detail_url: str | None`
- `editable: bool`
- `priority: str | None`
- `audience: str | None`
- `visibility: str | None`
- `related_entity_type: str | None`
- `related_entity_id: str | int | None`
- `metadata: CalendarItemMetadata | None`

Validation rules implemented today:

- `source_module`, `source_type`, and `source_id` must be non-blank strings.
- `tenant_id` must be positive.
- `site_id`, when present, must be non-blank.
- `starts_at` must be timezone-aware.
- `ends_at`, when present, must be timezone-aware and strictly after `starts_at`.
- `priority`, when present, must be one of `low`, `normal`, `high`, or `critical`.
- `visibility`, when present, must be one of `private`, `site`, `tenant`, `department`, `role`, or `public`.
- `related_entity_id` requires `related_entity_type`.
- `related_entity_type`, when present, must be non-blank.
- `detail_url`, when present, must begin with `/` so it stays an internal path.

Immutability:

- `CalendarItemRead` is frozen.
- It is intended to be treated as immutable after construction.

### `CalendarItemMetadata`

Frozen dataclass with the following exact field:

- `menu_context_status: str | None = None`

Current implementation only uses this for Offshore menu-context state.

### `CalendarUserContext`

Frozen dataclass with the following exact fields:

- `tenant_id: int | None`
- `site_id: str | None`
- `user_id: int | None = None`
- `role: str | None = None`
- `capabilities: frozenset[str] = frozenset()`

This is a caller context, not a persistence object.

### `CalendarFeedWarning`

Frozen dataclass with the following exact fields:

- `adapter_name: str`
- `code: str`
- `message: str`
- `identity: tuple[str, str, str] | None = None`

Warnings are used for adapter failures and duplicate-identity conflicts.

### `CalendarFeedResult`

Frozen dataclass with the following exact fields:

- `items: list[CalendarItemRead]`
- `warnings: list[CalendarFeedWarning]`
- `range_start: datetime`
- `range_end: datetime`

The result is a read-only container object, but the contained lists are regular Python lists.

## Adapter Protocol

The shared protocol is `CalendarReadAdapter`.

It requires:

- an `adapter_name: str`
- a `get_items(...) -> list[CalendarItemRead]` method with keyword-only arguments:
  - `tenant_id: int`
  - `site_id: str | None`
  - `range_start: datetime`
  - `range_end: datetime`
  - `user_context: CalendarUserContext`

Adapters are expected to return `CalendarItemRead` objects only. They are not supposed to mutate source state.

## Range Semantics

The feed uses a half-open query range:

- inclusive start
- exclusive end

The intended overlap rule for ranged items is:

`item.starts_at < range_end and (item.ends_at is None or item.ends_at > range_start)`

This means:

- an item beginning exactly at `range_end` is excluded
- an item ending exactly at `range_start` is excluded
- an item spanning the whole range is included
- a point event inside the range is included

The implementation currently applies this overlap rule in the aggregator.

## Identity and Deduplication

The identity key is exactly:

- `source_module`
- `source_type`
- `source_id`

Items with the same identity are deduplicated by the aggregator.

Items that share the same `source_id` but differ in `source_module` or `source_type` are not deduplicated.

## Deterministic Sorting

The aggregator sorts surviving items deterministically by:

1. `starts_at`
2. `category`
3. `title`
4. `source_module`
5. `source_type`
6. `source_id`

## Tenant and Site Filtering

The aggregator filters adapter output again after each adapter returns items.

Rules implemented today:

- items with a mismatched `tenant_id` are rejected
- items with a mismatched `site_id` are rejected
- when the caller omits `site_id`, items with a non-null `site_id` are rejected
- out-of-range items are rejected even if an adapter returned them

This second filtering pass is intentional and keeps the feed contract defensive.

## Partial Adapter Failure Behavior

One adapter failure does not discard successful results from other adapters.

The aggregator catches adapter exceptions and records a warning with:

- `adapter_name`
- `code = "adapter_error"`
- a safe text `message`

If two adapters emit the same identity with different payloads, the aggregator keeps the first item and records a duplicate warning instead of overwriting blindly.

## Editable Semantics

`editable` is a read-side hint only.

It reflects the source domain's read policy and does not imply that this contract supports writes.

For the Offshore adapter today:

- viewer and cook-style read roles return `editable = False`
- editor/admin-style roles return `editable = True`

## Internal Detail URL Restriction

`detail_url`, when present, must be an internal path beginning with `/`.

This prevents the shared read contract from advertising external navigation targets.

The Offshore adapter currently emits an internal period detail path.

## Offshore Adapter Mapping

The implemented Offshore adapter maps Offshore service events into the shared contract as follows:

- `source_module` -> `offshore`
- `source_type` -> `service_event`
- `source_id` -> Offshore service event id as a string
- `tenant_id` -> Offshore service event tenant id
- `site_id` -> Offshore service event site id
- `starts_at` -> Offshore service event start time
- `ends_at` -> `None`
- `all_day` -> `False`
- `title` -> Offshore event display name
- `category` -> `service_event`
- `status` -> Offshore event status, preserved as-is
- `detail_url` -> `/offshore/periods/{work_period_id}`
- `editable` -> Offshore role policy result
- `visibility` -> `site`
- `audience` -> `None`
- `related_entity_type` -> `work_period`
- `related_entity_id` -> Offshore work period id
- `metadata.menu_context_status` -> Offshore menu-context resolution status when available, otherwise `None`

Current behavior also treats missing Offshore menu-context rows as safe and emits the item with null metadata status rather than failing.

## Timezone Convention

The contract requires timezone-aware datetimes.

Canonical feed output is UTC-aware.

SQLite can return naive datetimes for stored Offshore timestamps, so the Offshore adapter normalizes naive values back to UTC on read before constructing `CalendarItemRead`.

## Future Adapters

Builder and Kommun adapters are future extension points only.

They are not implemented in this delivery, and this document does not promise any particular Builder or Kommun field mapping yet.

## Future UI Consumers

The shared feed is intended for future consumers such as a calendar/timeline view, but no UI has been added in this delivery.

Any front-end or route work must remain separate from this read contract.

## Explicit Out-of-Scope Boundaries

The following are out of scope for this delivery:

- calendar persistence tables
- calendar ORM models
- calendar write APIs
- calendar UI pages or widgets
- calendar migrations
- Builder or Kommun adapters
- external links or non-internal detail URLs
- any behavior that modifies Offshore source data
