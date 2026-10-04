# Department Portal Architecture

## Layer Definition

Layer: Input / Operational UI

Depends on: current Portal 1.0 implementation and the current production engine path

Type: Pilot UI with a clear future-lab boundary

## Purpose

The Department Portal is the operational input surface used by departments to make menu choices, communicate needs to the kitchen, and see explicit completion status.

Current truth:

- Portal 1.0 is implemented and closed at the component/E2E gate level.
- Home + Week workflow exists.
- Explicit submit/completion truth exists.
- Canonical Portal menu choice flows directly to Kitchen Weekview.
- There is no duplicate menu/choice truth.

The portal is an input/experience layer, not a production calculator.

## Core Principle

The UI should feel simple, but the data should stay structured.

## Current Shell

The current unit_portal uses the shared Yuplan topbar/shell.

Current shell truth:

- shared Yuplan topbar/shell
- no left sidebar for unit_portal
- no Veckovy
- no Planera
- no Rapport
- no Admin
- no actionable Specialkost module link

## Routes

Current routes:

- Portal Home: GET /ui/portal/department
- Portal Week: GET /ui/portal/department/week

## Identity and Scope

For normal unit_portal usage, the department comes from the authenticated user's department_id.

Query override must not switch the department.

Admin/support flows may use explicit department support context, but that is a separate privileged path.

## Home View

Portal Home is a read-only operational overview and entry point into the week workflow.

It may show:

- department identity
- resident count
- registered specialkost or needs
- serving adaptations where data exists

Security correction:

- Department.notes / Faktaruta is private.
- It must never be shown to unit_portal.

## Week View

Portal Week is the choice screen.

It shows:

- the week menu
- the days in that week
- choice rows for the relevant meals
- explicit completion state

It is not a duplicate menu model. It reflects the published Builder menu and department selections.

## Completion Model

Completion is explicit submission truth, not simply a matter of selecting all options.

Current states:

- not_started
- in_progress
- complete
- needs_review / stale where applicable

The canonical truth is:

published Builder menu + department menu choices + department portal week submission

If a required choice changes after submission, the submission becomes stale.

## What Portal Is Not

The portal does not calculate production.

It does not own production truth.

It does not create a second menu or choice model.

## Live Acceptance Notes

The current live acceptance scope is:

- verify menu visibility for the same published menu
- verify required choices
- verify single-option days are read-only
- verify explicit submit
- verify propagation to Kitchen Weekview
- verify persistence after reload/login

## Design Boundary

Portal 1.0 is the current operational input surface.

Portal 2.0 remains the future input-layer concept for a deeper engine integration, but current documentation must not describe that future state as if it were the present product truth.