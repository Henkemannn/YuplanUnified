# Offshore Prep Tasks

## Purpose
Offshore prep tasks are an Offshore-owned operational work item for a specific service event on a specific local installation date. They are not a generic platform task and they are not a repurposed note store.

## Scope
- Anchored to `tenant_id`, `site_id`, `work_period_id`, and `service_event_id`
- Optional Builder component reference plus a frozen component-name snapshot
- Local operational date semantics: `planned_date` is the installation-local date, not a UTC date
- No hard delete in MVP

## Model
The persisted model is `OffshorePrepTask` in [modules/offshore2/models.py](../../modules/offshore2/models.py).

Important fields:
- `title`
- `instructions`
- `planned_date`
- `planned_time`
- `work_position_id`
- `status`
- `sort_order`
- `builder_component_id`
- `component_name_snapshot`
- `created_by_user_id`
- `completed_by_user_id`
- `completed_at`
- `created_at`
- `updated_at`

Allowed statuses:
- `planned`
- `in_progress`
- `completed`
- `cancelled`

## Read model
The prep day view uses frozen dataclasses in [modules/offshore2/prep_tasks.py](../../modules/offshore2/prep_tasks.py).

Read projections:
- `OffshorePrepSummary`
- `OffshorePrepTaskRead`
- `OffshorePrepServiceGroup`
- `OffshorePrepDay`

The read layer exposes only UI-friendly values and does not leak ORM rows.

## Permissions
Write access follows the Offshore prep write policy from [modules/offshore2/permissions.py](../../modules/offshore2/permissions.py):
- `cook`
- `editor`
- `admin`
- `superuser`

Viewer access still uses the Offshore viewer roles.

## Routes
- `GET /offshore/operations/prep`
- `GET /offshore/service-events/<service_event_id>/prep`
- `POST /offshore/operations/prep/tasks`
- `POST /offshore/operations/prep/tasks/<task_id>/update`
- `POST /offshore/operations/prep/tasks/<task_id>/transition`

The service-event route is a navigation shortcut that redirects into the date-based prep view.

## Transitions
Transition handling is explicit and bounded by the service layer.

Supported transitions in MVP:
- `planned` -> `in_progress`
- `planned` -> `completed`
- `planned` -> `cancelled`
- `in_progress` -> `planned`
- `in_progress` -> `completed`
- `in_progress` -> `cancelled`
- `completed` -> `planned`
- `completed` -> `in_progress`
- `cancelled` -> `planned`

Completion stamps `completed_at` and `completed_by_user_id`. Reopening clears those fields.

## Builder boundary
Prep tasks may snapshot a Builder component name, but they do not write to Builder data. The component lookup is read-only and goes through the existing Builder menu-context flow.

## Operations integration
`GET /offshore/operations` now shows prep summary counts and a link into the prep view for each service event.

## Empty states
The prep page handles these states:
- no installation configured
- no applicable work period
- no service events for the selected date
- no prep tasks yet

## Migration
The prep table is added in `migrations/versions/0029_add_offshore_v2_prep_tasks.py`.

## Out of scope
- Hard delete
- Generic cross-domain task reuse
- Builder writes
- Cross-site leakage
- Calendar persistence
- Platform-wide task abstraction
