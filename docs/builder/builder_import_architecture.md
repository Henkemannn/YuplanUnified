# Builder Import Architecture and Safety Boundary

Status: architecture note only (no runtime behavior change)

## Purpose
Define a safe boundary for future Builder import wizard work so existing menu-context import behavior remains protected.

## Safety Boundary: Two Import Paths

### Path 1: Protected menu-context import
This path is used for existing menu row import behavior and current municipal/menu workflows.

Characteristics:
- Imports rows into menu context.
- Resolves row text to existing compositions or stores unresolved rows.
- Is part of existing Yuplan Kommun/menu behavior and must remain stable.

Protection rule:
- Builder wizard work must not modify this path unless separately approved.

### Path 2: Builder import modal workflow
This path is used for Builder dish/component workflows and import review sessions.

Characteristics:
- Uses preview, row classification, review/edit, and publish-selected flow.
- Creates/reuses compositions and components based on selected item type.
- Is the correct place for future Builder wizard evolution.

## Current-State Constraints
- Recipe import is currently not structured into component recipe fields.
- Builder modal menu context option is currently not equivalent to true structured menu creation.
- Existing behavior must be treated as current v1 baseline until explicitly replaced.

## Protected Files and Flows
The following are protected for Builder wizard work and must not be touched without separate approval:
- core/menu/menu_import_service.py
- core/builder_menu_context_api.py
- Any existing Yuplan Kommun/menu import flow and related endpoints/services

## Future Builder Import Types (target model)
Future Builder wizard should support explicit type modes:
- menu_structured
- dish_list
- component_list
- recipe_text_structured
- uncertain/free text

## Future Wizard Flow
Recommended wizard stages:
1. Type selection
2. Preview and classification
3. Existing-entity matching (before save)
4. Confirmation step

Expected behavior:
- Reuse/create/ignore decisions are explicit.
- Existing entity matching happens before persistence.
- No overwrite without explicit user confirmation.

## First Safe Runtime Step
First implementation step should be minimal and low risk:
- Fix Builder import modal ID wiring only.
- Align Builder JS element lookups with template element ids.
- Scope limited to Builder import modal path.
- No changes to menu-context import services/endpoints.

## Non-goals for this step
- No backend schema changes.
- No save payload changes.
- No modifications to municipal/menu-context import logic.
- No runtime behavior expansion in this documentation task.
