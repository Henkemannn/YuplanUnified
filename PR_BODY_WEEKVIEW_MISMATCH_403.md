# P0: Explicit 403 on weekview tenant/site mismatch + stabilize dev seed

## Changes
- Return 403 with clear Swedish error when `/ui/weekview` receives a `site_id` belonging to another tenant (no silent clear).
- Stabilize dev seed so `accept-site-A` is assigned `tenant_id=1` on local init.
- Add regression test for the mismatch scenario.

## Out of Scope
- No refactors.
- No visual/UI changes to weekview templates.
- No changes to production seed or test fixtures beyond the added focused test.

## Verification
- Local full `pytest -q`: PASS.
- Manual sanity:
  - `/ui/weekview?...` with correct tenant → menu icon visible.
  - `/ui/weekview?...` with wrong tenant → 403 with explicit error message.
