# Offshore 2.0 Technical Model Notes

This note describes the implemented Ticket 2 data model and service invariants.
It does not replace [product_blueprint.md](product_blueprint.md).

## Models

### OffshoreInstallationSettings
Site-scoped installation configuration tied to `tenant_id + site_id`.
It stores timezone, default locale, default theme, default portions, active state, and audit timestamps.

Invariant: one row per tenant/site.

### OffshoreWorkPosition
Site-scoped virtual staffing position.
It stores a stable `code`, display `name`, `position_type`, `sort_order`, active state, and audit timestamps.

Invariant: `code` is unique per tenant/site and does not change when the display name changes.

### OffshoreMenuCycle
Site-scoped menu-cycle container.
It stores the cycle name, description, cycle length, active state, and audit timestamps.

Invariant: at most one active cycle per site.

### OffshoreMenuCycleSlot
Ordered slot rows inside a menu cycle.
It stores `cycle_index`, `label`, optional description, `sort_order`, active state, and audit timestamps.

Invariant: `cycle_index` starts at 1 and is unique within a menu cycle.

## Ownership and scope

- All four models are owned by the active site context.
- Mutation checks both `tenant_id` and `site_id` from the request/session context.
- Cross-site IDs are treated as not found for the Offshore v2 routes.

## Explicit non-goals for Ticket 2

- No period templates yet.
- No concrete work-period model yet.
- No Builder Menu or Builder version binding yet.
- No user assignments yet.
