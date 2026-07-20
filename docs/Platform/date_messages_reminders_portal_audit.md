# Yuplan Platform Audit: Dates, Messages, Reminders, Notes, Publication and Portal-Ready Functionality

Branch: `feat/planera-app-shell-2026-03-03`

Baseline / GZ: `gz-offshore2-menu-context-v0`

This is an audit and documentation report only. It inventories the current repository state and classifies what should be reused, adapted, or left domain-specific before any future shared calendar/timeline or communication layer is designed.

## Executive Summary

The repository already contains several separate but partially overlapping concepts:

- Commun has dashboard announcements, private notes, remember-to-order items, week-based menu choice state, and legacy message/announcement flows.
- Builder already has canonical menu content, week-based publication pins, menu links, and menu composition/projection adapters, but it does not materialize concrete dated occurrences itself.
- Offshore already has the strongest dated operational model with periods, service events, site timezone resolution, and the Ticket 4 menu-context contract that binds a service event to a publication snapshot and cycle slot anchor.
- Portals already expose read models for week-based department planning and kitchen dashboard communication, but they are not a single shared Portal Core yet.

The safest architecture direction is adapter-based read aggregation first, with shared contracts later only where naming and semantics are stable. The main duplication risks are:

- multiple “message/announcement/note” surfaces with different scope and visibility rules
- week-based Builder publication data competing with Offshore’s concrete service date model
- portal-specific menu choice state reusing week/day semantics that are not yet generalized

No production behavior was changed for this audit.

## Current-State Inventory

### Commun / core

#### Announcements / dashboard communication

- File: [core/announcements_repo.py](../../core/announcements_repo.py)
- Model/table: `announcements` table via repository-only schema creation
- Fields: `site_id`, `message`, `event_date`, `event_time`, `show_on_kitchen_dashboard`, `is_active`, `created_at`, `created_by_user_id`
- Scope: site-scoped, not tenant-scoped in the table itself
- Permissions: managed through UI routes in `core.ui_blueprint`; admin-only for create/update/delete
- Display: kitchen dashboard and admin announcements page
- Status: active and used
- Reuse class: `KEEP DOMAIN-SPECIFIC` for the current kitchen/admin announcement feature; `CANDIDATE FOR SHARED PLATFORM SERVICE` only if a future Notice contract can preserve audience and scheduling semantics

#### Notes

- File: [core/models.py](../../core/models.py)
- Model: `Note`
- Fields: `tenant_id`, `user_id`, `content`, `created_at`, `updated_at`, `private_flag`
- Scope: tenant-scoped and user-owned; visibility is private unless the role can bypass ownership in the API
- Routes: [core/notes_api.py](../../core/notes_api.py)
- Permissions: `superuser`, `admin`, `cook`, `unit_portal`
- Display: JSON API consumer only in current code; not a dashboard card by itself
- Status: active
- Reuse class: `CANDIDATE FOR SHARED PLATFORM SERVICE` for a future work-item/notice contract, but not directly reusable without new audience and due-date fields

#### Remember-to-order

- File: [core/remember_to_order_repo.py](../../core/remember_to_order_repo.py)
- Model/table: `remember_to_order_items`
- Fields: `site_id`, `week_key`, `text`, `created_at`, `created_by_user_id`, `created_by_role`, `checked_at`, `checked_by_user_id`
- Scope: site + week key
- Acknowledgement: yes, via `checked_at` / `checked_by_user_id`
- Display: kitchen dashboard and JSON APIs in `core.ui_blueprint`
- Status: active and mobile-friendly in intent
- Reuse class: `KEEP DOMAIN-SPECIFIC` today; `EXPOSE THROUGH ADAPTER` for a future shared calendar or work-item read model because it is already close to a dated work item, but it is kitchen-specific

#### Prep notes

- File: [core/prep_notes_repo.py](../../core/prep_notes_repo.py)
- Model/table: `prep_notes`
- Fields: `site_id`, `user_id`, `text`, `created_at`, `is_active`
- Scope: site + user, including global-to-site notes when `user_id` is NULL in the read path
- Display: kitchen dashboard only
- Status: active and operational
- Reuse class: `LEGACY / DO NOT BUILD ON` for shared communication; this is a local operational scratchpad, not a general notice layer

#### Legacy message store

- File: [core/models.py](../../core/models.py)
- Model: `Message`
- Fields: `tenant_id`, `sender_user_id`, `audience_type`, `unit_id`, `subject`, `body`, `created_at`
- Scope: tenant-scoped, audience can be all/unit/role, optionally unit-targeted
- Status: present in core model but not the preferred modern communication path in this branch
- Reuse class: `DUPLICATE / DEPRECATION CANDIDATE`

### Builder

#### Publication pins and menu links

- Files: [core/models.py](../../core/models.py), [core/commun_builder_publication.py](../../core/commun_builder_publication.py)
- Models: `CommunBuilderPublicationPin`, `CommunBuilderMenuLink`
- Publication fields: `tenant_id`, `site_id`, `year`, `week`, `legacy_menu_id`, `builder_menu_id`, `builder_menu_version`, `source`, timestamps
- Menu-link fields: same week identity plus `projection_version`
- Scope: tenant + site + ISO week
- Status: active and central
- Reuse class: `REUSE DIRECTLY`

#### Builder menu context / projection

- Files: [core/builder_menu_context_flow.py](../../core/builder_menu_context_flow.py), [core/builder_menu_context_api.py](../../core/builder_menu_context_api.py), [core/commun_builder_projection.py](../../core/commun_builder_projection.py)
- What it does: resolves menu rows from Builder composition data and validates version identity, unresolved rows, and projection safety
- Important translation boundary: Builder rows are still week/day/meal oriented and are not concrete date occurrences
- Reuse class: `REUSE DIRECTLY` for publication identity and projection safety; `EXPOSE THROUGH ADAPTER` for calendar/timeline readers

#### Date-driven menu presentation

- Files: [core/menu_choice_api.py](../../core/menu_choice_api.py), [core/weekview_vm.py](../../core/weekview_vm.py), [core/weekview/repo.py](../../core/weekview/repo.py), [portal/department/service.py](../../portal/department/service.py)
- Representation: ISO year/week + weekday/day-of-week; menu choice state is stored per department/week/day
- Reuse class: `EXPOSE THROUGH ADAPTER`

### Offshore

#### Work periods and service events

- Files: [modules/offshore2/models.py](../../modules/offshore2/models.py), [modules/offshore2/periods.py](../../modules/offshore2/periods.py)
- Models: `OffshoreWorkPeriod`, `OffshoreServiceEvent`
- Date fields: `starts_at`, `ends_at`, event `starts_at`, period `status`
- Scope: tenant + site + concrete timestamp
- Status: active and strongest dated source in the repository for operational menu context
- Reuse class: `REUSE DIRECTLY`

#### Offshore menu context

- Files: [modules/offshore2/models.py](../../modules/offshore2/models.py), [modules/offshore2/menu_context.py](../../modules/offshore2/menu_context.py), [modules/offshore2/routes.py](../../modules/offshore2/routes.py)
- Models: `OffshoreServiceEventMenuContext`, `OffshoreWorkPeriod.start_menu_cycle_slot_id`
- Purpose: dated operational snapshot tying a service event to a publication pin and cycle slot
- Statuses: `resolved`, `unresolved`, `unavailable`, `manual`
- Assignment sources: `automatic`, `manual`
- Match states: `matched`, `missing`, `ambiguous`, `withdrawn` reserved
- Reuse class: `REUSE DIRECTLY` for Offshore; `EXPOSE THROUGH ADAPTER` for future calendar/timeline reads

#### Dashboard summary

- File: [modules/offshore2/periods.py](../../modules/offshore2/periods.py)
- Fields: `current_period`, `next_period`, `upcoming_event_count`, `overlap_warnings`, `unresolved_count`, `next_service`, `setup_guidance`
- Status: active
- Reuse class: `EXPOSE THROUGH ADAPTER`

#### Calendar readiness payload

- File: [modules/offshore2/routes.py](../../modules/offshore2/routes.py)
- Route: `GET /offshore/periods/<period_id>/service-events/<event_id>/calendar-readiness`
- Payload fields: `source_module`, `source_type`, `source_id`, `tenant_id`, `site_id`, `starts_at`, `title`, `category`, `status`, `menu_context_status`, `detail_url`, `editable`
- Persistence: non-persistent
- Reuse class: `EXPOSE THROUGH ADAPTER`

### Portals

#### Department portal week read model

- Files: [portal/department/api.py](../../portal/department/api.py), [portal/department/service.py](../../portal/department/service.py), [portal/department/models.py](../../portal/department/models.py)
- Payload: `DepartmentPortalWeekPayload`
- Fields include: department/site identity, year/week, facts, progress, ETag map, day list
- Scope: department + site + ISO week
- Reuse class: `EXPOSE THROUGH ADAPTER`

#### Department portal menu choice

- Files: [portal/department/menu_choice_repo.py](../../portal/department/menu_choice_repo.py), [core/menu_choice_api.py](../../core/menu_choice_api.py)
- Storage: `alt2_flags` (current storage reuse), plus the department portal repo shim
- Purpose: day-level Alt1/Alt2 choice state for a weekly portal
- Reuse class: `KEEP DOMAIN-SPECIFIC` for now, with adapter reuse only

#### Kitchen and admin dashboards

- Files: [core/ui_blueprint.py](../../core/ui_blueprint.py), [templates/ui/kitchen_dashboard.html](../../templates/ui/kitchen_dashboard.html), [templates/ui/unified_admin_dashboard.html](../../templates/ui/unified_admin_dashboard.html)
- Communication surfaces: announcements, remember-to-order, prep notes, today menu
- Reuse class: `EXPOSE THROUGH ADAPTER`

#### Portal shell / legacy portals

- Files: [templates/unified_portal_week.html](../../templates/unified_portal_week.html), [templates/unified_portal_week_department.html](../../templates/unified_portal_week_department.html), [templates/portal_department_week.html](../../templates/portal_department_week.html)
- Status: active portal UI exists, but it is split by context/profile and not a shared technical core yet
- Reuse class: `CANDIDATE FOR SHARED PLATFORM SERVICE`

## Feature Matrix

| Feature | Domain | Key files | Model/table | Routes / templates | Status | Reuse classification |
|---|---|---|---|---|---|---|
| Kitchen/admin announcements | Commun | `core/announcements_repo.py`, `core/ui_blueprint.py` | `announcements` | `/ui/admin/announcements`, kitchen/admin dashboards | Active | Keep domain-specific |
| Notes API | Commun | `core/models.py`, `core/notes_api.py` | `notes` | `/notes` | Active | Candidate for shared platform service |
| Remember-to-order | Commun | `core/remember_to_order_repo.py`, `core/ui_blueprint.py` | `remember_to_order_items` | `/ui/api/remember-to-order*`, dashboard card | Active | Keep domain-specific |
| Prep notes | Commun | `core/prep_notes_repo.py`, `core/ui_blueprint.py` | `prep_notes` | kitchen dashboard | Active | Legacy / do not build on |
| Message model | Commun | `core/models.py` | `messages` | no current modern UI contract | Present, legacy | Duplicate / deprecation candidate |
| Builder publication pins | Builder | `core/models.py`, `core/commun_builder_publication.py` | `commun_builder_publication_pins` | publication service | Active | Reuse directly |
| Builder menu links | Builder | `core/models.py`, `core/commun_builder_publication.py` | `commun_builder_menu_links` | publication service | Active | Reuse directly |
| Builder projection / composition resolution | Builder | `core/commun_builder_projection.py`, `core/builder_menu_context_flow.py` | builder rows, compositions, recipes | adapter APIs | Active | Reuse directly + adapter |
| Offshore work periods / events | Offshore | `modules/offshore2/models.py`, `modules/offshore2/periods.py` | offshore period/event tables | Offshore period routes/templates | Active | Reuse directly |
| Offshore menu context | Offshore | `modules/offshore2/models.py`, `modules/offshore2/menu_context.py` | `offshore_service_event_menu_contexts` | `/offshore/periods/*/menu-context*` | Active | Reuse directly + adapter |
| Offshore calendar readiness | Offshore | `modules/offshore2/routes.py` | none | JSON read route | Active | Expose through adapter |
| Department portal week payload | Portals | `portal/department/models.py`, `portal/department/service.py` | no new table | `/portal/department/week` | Active | Expose through adapter |
| Department portal menu choice | Portals | `portal/department/menu_choice_repo.py`, `core/menu_choice_api.py` | `alt2_flags` | `/portal/department/menu-choice/change`, `/admin/menu-choice` | Active | Keep domain-specific |
| Portal shell / week views | Portals | `templates/unified_portal_*`, `templates/portal_department_week.html` | read models only | portal views | Active | Candidate for shared platform service |

## Data-Model Comparison

### Overlapping concepts

| Concept | Kommun / core | Builder | Offshore | Portals | Notes |
|---|---|---|---|---|---|
| tenant/site scope | `tenant_id`, `site_id` on many tables | `tenant_id`, `site_id` on publications and menus | `tenant_id`, `site_id` on periods, events, context | department portal derives `site_id` from department | Shared and stable |
| created by / sender | `created_by_user_id`, `sender_user_id` | publication source, link source | actor-free domain rows | portal choice is claims-driven | Naming is inconsistent |
| title/body/text | message, content, text, subject | menu title, row text via compositions | display_name, notes, resolution_reason | portal facts/note | Overlap, but semantics differ |
| dates | event_date, created_at, checked_at, week_key | year/week, version | starts_at/ends_at, service_date | year/week/day-of-week | Different abstraction levels |
| visibility / audience | audience_type, unit_id, private_flag, show_on_kitchen_dashboard | none on core publication rows | implicit via site and role gating | department claims / site scoping | Not yet unified |
| acknowledgement / response | checked_at on remember-to-order | none | manual assignment / clear | selected_alt in portal | Similar but not identical |

### Unsafe to unify directly

- `core.models.Message` and `core.announcements_repo.AnnouncementItem` are not interchangeable: one is a tenant/unit audience model, the other is a dated site announcement.
- `core.notes_api.Note` is user-owned content, not audience-targeted communication.
- `portal.department.menu_choice_repo` is weekly choice state, not a general notice/work-item model.
- Offshore menu context is an operational projection tied to a service event; it should not become a generic message row.

### Safe adapter boundaries

- convert week/year Builder publication records to concrete dates only in adapters
- convert Commun announcements/remember-to-order/prep notes into a future calendar feed only through read adapters
- keep Offshore as the operational source of truth for dated service events

## Date-First Findings

### How dates are represented now

- ISO week + weekday: `core.menu_choice_api`, `portal.department.menu_choice_repo`, `portal.department.service`
- concrete date: `core.announcements_repo`, `core.remember_to_order_repo`, `core.prep_notes_repo`, Offshore periods/events, Offshore service context
- local datetime: Offshore timezone-normalized service dates and `event_time` on announcements
- UTC datetime: notes and many core timestamp columns use UTC-aware defaults
- all-day dates: announcements, remember-to-order week key, portal week payload, Builder week key
- recurring templates: Offshore period templates and template events
- concrete dated occurrences: Offshore service events are the strongest operational dated occurrences in the repo
- publication-effective dates: Builder publication uses ISO year/week, not concrete dates
- timezone: Offshore uses installation timezone, defaulting to Europe/Oslo

### Answers

- Builder publication already materializes concrete dates? No. It materializes week/year publication identity, not concrete occurrence dates.
- Kommun mainly works from week/year rather than concrete dates? Yes, for menu choice and portal week payloads.
- Can current publication records reliably resolve to a service date? Not on their own; they need a consumer-side adapter that maps week/year to a concrete date context.
- Are Offshore service events already the strongest dated source? Yes.
- Where would a future calendar adapter need translation logic? Builder publication pins, Kommun week-based menu choice, portal week payloads, and any legacy announcement/reminder surfaces.

## Communication / Reminder Findings

### Announcements

- Persistent: yes
- Tenant/site scoped: site-scoped in current repository shape
- Targeting: kitchen-dashboard visibility flag
- Dates: event_date + optional event_time
- Priority: none explicit
- Acknowledgement: no
- Editable: yes through admin UI
- Dashboard / portal display: yes on admin and kitchen dashboards
- Mobile suitability: acceptable as a short list, but not a general work-item model
- Reuse outside Kommun: only as a read adapter or a future Notice contract, not as-is

### Notes

- Persistent: yes
- Tenant/site scoped: tenant-scoped, user-owned
- Targeting: user ownership / role access, not audience targeting
- Dates: created_at / updated_at
- Priority: no
- Acknowledgement: no
- Editable: yes
- Dashboard / portal display: not a direct dashboard communication surface
- Mobile suitability: yes as a personal note API
- Reuse outside Kommun: limited; suitable as a personal note primitive, not a shared notice system

### Remember-to-order

- Persistent: yes
- Tenant/site scoped: site + week key
- Targeting: site/week and current user context
- Dates: week_key plus created_at/checked_at
- Priority: no
- Acknowledgement: yes, via `checked_at`
- Editable: yes
- Dashboard / portal display: yes on kitchen dashboard
- Mobile suitability: good
- Reuse outside Kommun: possible as a dated work-item adapter, but not yet a shared service

### Prep notes

- Persistent: yes
- Tenant/site scoped: site + user
- Targeting: user-specific or site-wide when user_id is null in reads
- Dates: created_at
- Priority / acknowledgement: no
- Editable: yes
- Dashboard / portal display: yes on kitchen dashboard
- Mobile suitability: yes, but it is a local scratchpad
- Reuse outside Kommun: no

## Portal Findings

### Can Avdelningsportal and Mässportal share a common core?

Yes, but only at the infrastructure layer, not by collapsing their domain semantics.

Shared needs already visible in the repository:

- tenant/site context
- audience or recipient context derived from claims/session
- dated published content
- menu read model
- messages/notices on dashboards
- acknowledgement/input state
- authentication/token/session patterns
- branding and locale
- mobile-friendly layout patterns

Recommended split:

- shared portal infrastructure: auth/session/context resolution, branding, locale, shell, accessibility primitives, ETag helpers
- Kommun-specific behavior: week menu choice, weekview, kitchen dashboard reminders and announcements
- Offshore-specific behavior: service events, work periods, publication snapshot and menu context
- crew-specific behavior: public/private token flows, allergen/special-diet submissions, if those become first-class

Conclusion: one shared Portal Core is reasonable as a shell and session/context layer, but the portal implementations should remain profile-specific for the read model and business rules.

## Calendar / Timeline Readiness

The repository is not yet using a shared persisted calendar item. It can, however, emit a non-persistent read contract through adapters.

### Existing fields by module

- Commun announcements: `message`, `event_date`, `event_time`, site scope, kitchen visibility flag
- Remember-to-order: `text`, `week_key`, `created_at`, `checked_at`
- Notes: `content`, `created_at`, `updated_at`, tenant/user ownership
- Builder: `year`, `week`, `builder_menu_id`, `builder_menu_version`, `source`
- Offshore: `service_date`, `starts_at`, `ends_at`, `resolution_status`, `assignment_source`, publication snapshot fields
- Portal week payload: date per day, selected alt, menu texts, residents/diets summaries

### Missing fields for a generic adapter contract

- `all_day`
- `visibility` / audience normalization
- `priority`
- `related_entity_type` / `related_entity_id`
- stable cross-domain `source_module` / `source_type` / `source_id` for every feature

### Adapter sufficiency

- Offshore: adapter is sufficient now
- Builder: adapter is sufficient for week-level publication-to-date translation
- Kommun announcements and reminders: adapter is sufficient for a read feed
- Portal week payload: adapter is sufficient

### When schema change would be needed

- only if a future product decision requires shared persistence, cross-module acknowledgement tracking, or cross-domain mutation

## Reuse Classification

1. `KEEP DOMAIN-SPECIFIC`
- announcements
- remember-to-order
- prep notes
- portal menu-choice state

2. `REUSE DIRECTLY`
- Builder publication pins and menu links
- Offshore periods, service events, menu context

3. `EXPOSE THROUGH ADAPTER`
- Offshore calendar-readiness payload
- Builder publication-to-date translation
- Kommun announcements and reminders as read items
- portal week payloads

4. `CANDIDATE FOR SHARED PLATFORM SERVICE`
- common portal shell
- common calendar/timeline read aggregation
- common notice/work-item read contract

5. `DUPLICATE / DEPRECATION CANDIDATE`
- legacy `messages` model as a platform communication primitive

6. `LEGACY / DO NOT BUILD ON`
- prep notes as a shared platform concept
- any direct legacy offshore/kommun message table patterns from older apps

## Recommended Target Architecture

### Calendar / Timeline

Use adapter-based read aggregation first.

- Keep domain-owned persistence in Kommun, Builder, Offshore, and portals
- Translate to a shared non-persistent read contract at the edge
- Add shared persistence only if a concrete cross-module editing story emerges

Reason: the strongest dates already live in Offshore, while Builder and Kommun still speak in week/day/publish terms. A persisted shared table would duplicate domain truth too early.

### Notices / Work Items

Use a shared work-item/notice contract only as a future target, not now.

- Kommun announcements and remember-to-order are the closest candidates
- Notes should remain personal/user-owned, not notices
- Prep notes should remain local operational scratchpad data

### Portal Core

Build one shared portal shell and auth/context layer.

- shared responsibilities: auth/session/claims resolution, site/tenant context, locale, branding, layout primitives, ETag helpers, accessibility, mobile shell
- profile responsibilities: Kommun week planning, Offshore service-event operations, crew-specific forms or special-diet flows

### Publication / date materialization

Builder week publications should become concrete dated occurrences only in adapters, preferably by joining publication week/year with the consumer’s operational date anchor.

- Offshore should remain the concrete dated consumer for service operations
- Kommun portal week views should remain week-based read models
- the calendar adapter should perform translation at read time, not by writing new shared rows

## Migration Strategy

### Phase 1

- read-only adapters
- no behavior changes
- explicit source_module/source_type/source_id normalization in read payloads

### Phase 2

- shared contracts
- dual-read or projection views where needed
- keep domain writes local

### Phase 3

- optional shared persistence only if there is a validated product need
- backfill only from authoritative sources, never from derived UI state

### Phase 4

- deprecate duplicate communication or work-item paths only after adapter parity exists

### Data-risk areas

- week/year vs concrete date translation
- audience/visibility semantics
- acknowledgement semantics
- source-of-truth confusion between publication and operational occurrence

## Explicit No-Duplication Rules

- Do not duplicate Builder publication content into Offshore or portal storage.
- Do not model generic notices as notes.
- Do not turn remember-to-order or prep notes into the shared work-item model without a separate migration plan.
- Do not replace Offshore service events with a generic calendar table.
- Do not collapse Kommun week choice state into a generic publication row.

## Proposed Future Tickets

- Ticket A: shared calendar/timeline read contract and adapters
- Ticket B: Kommun, Builder, Offshore, and portal adapter coverage
- Ticket C: dashboard feed for day/week operational items
- Ticket D: Portal Core shell and shared auth/context primitives
- Ticket E: notice/work-item consolidation discovery and pilot

## Risks

- semantic drift between week-based and date-based systems
- accidental unification of personal notes with operational notices
- double source-of-truth for publication state
- portal shell overreach before the profile-specific contracts are stabilized

## Appendix Pointer

Detailed file/model references are listed in [date_messages_reminders_portal_audit_appendix.md](date_messages_reminders_portal_audit_appendix.md).
