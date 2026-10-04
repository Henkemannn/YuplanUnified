# Yuplan Unified — Live Acceptance Flow

## Purpose

This guide replaces the old internal demo script with the real live acceptance chain for KOMMUN 1.1.

It starts from a new customer and follows the actual product path from onboarding to reporting.

## Step 1 — Create Customer

Create a completely new customer/tenant.

Create the site/kitchen and verify tenant/site scoping.

Acceptance checks:

- tenant and site are new
- scoping is correct
- no accidental reuse of demo-only data

## Step 2 — Create Departments

Create several new departments.

Set:

- resident counts / current quantities
- realistic registered needs
- requirement groups
- specialkost
- serving adaptations where relevant

Verify persistence after reload.

## Step 3 — Department Login

Create or bind a unit_portal login for at least one department.

Verify:

- department scope is correct
- the user cannot escape into another department
- admin modules are not exposed through the portal path

## Step 4 — Builder

Import a realistic weekly menu.

Resolve or create required dishes and components through the current Builder flow.

Include meals sufficient to verify:

- lunch
- kvällsmat
- dessert

Publish the menu.

The canonical publication must be the source consumed downstream.

## Step 5 — Kitchen Weekview

Verify that the newly published menu appears for the same week.

Verify:

- correct days and meals
- correct department/customer/site context

## Step 6 — Department Portal

Log in as the new department.

Verify:

- the same published menu is visible
- required Alt1/Alt2 choices can be made
- single-option days are read-only
- choices are submitted explicitly
- status becomes complete

## Step 7 — Portal to Kitchen Propagation

Verify the department's menu choice appears in Kitchen Weekview.

There must be no manual sync and no duplicate choice model.

## Step 8 — Planera

Use the new customer's real data.

Verify planning for:

- lunch
- kvällsmat
- dessert

Important:

Do not assume dessert support if the current live implementation does not actually support it.

If lunch works but evening or dessert cannot complete the expected Planera workflow, record that as a real pilot gap or blocker.

Verify that current quantities, registered needs, and menu choices feed the planning result correctly.

## Step 9 — Production

Verify:

Planera Page1 → Page2 review → Planera 2.0 computation → Page3 Produktionsunderlag → mark complete → Kitchen Weekview completion state

## Step 10 — Report

Verify that the relevant weekly/report output reflects the new customer data.

## Appendix

### Acceptance Rule

This guide is a live acceptance path, not a synthetic demo script.

It is intended to surface real customer setup, workflow friction, and pilot blockers.
