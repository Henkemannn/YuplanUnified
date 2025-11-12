# Phase E — Pilot Readiness Acceptance Criteria

Definition of Done:
- Seed script `scripts/seed_varberg_midsommar.py` exists, idempotent, prints IDs + collection ETags
- Makefile target `seed-varberg` invokes seed script
- Staging smoke checklist `.github/PHASE_E_STAGING_SMOKE.md` present
- Demo guide `docs/pilot_demo_guide.md` present (one page)
- (Optional) staging simple auth behind env `STAGING_SIMPLE_AUTH=1` implemented (non-prod only)
- Staging smoke passes end-to-end (health, openapi version, admin writes, diet defaults, alt2, notes, 304 cache)
- No regressions in Phases B–D test suites (pytest + vitest remain green)
