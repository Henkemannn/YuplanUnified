# Data Model Overview

## Core Tables
- tenants(id, name, active)
- units(id, tenant_id, name, default_attendance)
- users(id, tenant_id, email, password_hash, role, unit_id)
- dishes(id, tenant_id, name, category)
- recipes(id, tenant_id, title, body)
- menus(id, tenant_id, week, year)
- menu_variants(id, menu_id, day, meal, variant_type, dish_id)
- menu_overrides(id, tenant_id, unit_id, date, meal, variant_type, replacement_dish_id, scope)
- dietary_types(id, tenant_id, name, default_select)
- unit_diet_assignments(id, unit_id, dietary_type_id, count)
- attendance(id, unit_id, date, meal, count, origin)

## Offshore Module
- shift_templates(id, tenant_id, name, pattern_type)
- shift_slots(id, tenant_id, unit_id, template_id, start_ts, end_ts, role, status, notes)
- portion_guidelines(id, tenant_id, unit_id, category, baseline_g_per_guest, protein_per_100g)
- service_metrics(id, tenant_id, unit_id, date, meal, dish_id, category, guest_count, produced_qty_kg, served_qty_kg, leftover_qty_kg, served_g_per_guest)
- tasks(id, tenant_id, unit_id, task_type, title, done)
- messages(id, tenant_id, sender_user_id, audience_type, unit_id, subject, body, created_at)

## Municipal Module
- (Reuses core tables) additional workflow stored via menu_variants + selection logic and future diet_selections table.

## Planned Additional Tables (Phase 2+)
- tenant_feature_flags(id, tenant_id, feature_name, enabled)
- exports_audit(id, tenant_id, type, created_at, meta_json)
- imports_audit(id, tenant_id, type, created_at, meta_json)

## Enumerations (Implicit First Pass)
- roles: superuser, admin, unit_portal, cook
- variant_type: alt1, alt2, dessert, kvall
- task_type: prep, freezer, generic
- scope: global, unit, private
- pattern_type: weekly, motor_v1, simple6
- status (shift_slot): planned, published, cancelled

## Key Indices (To add in migrations)
- users(email) unique
- dishes(tenant_id, name)
- menu_variants(menu_id, day, meal, variant_type)
- menu_overrides(tenant_id, unit_id, date, meal)
- shift_slots(tenant_id, start_ts)
- service_metrics(tenant_id, unit_id, date, meal)
