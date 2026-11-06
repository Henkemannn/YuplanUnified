# Yuplan Unified — release roadmap

**Reviewed:** 2026-11-06. This document describes **phase sequence only**. The **single live gate/status authority** is [Kommun 1.1 Live Acceptance](KOMMUN_1_1_LIVE_ACCEPTANCE.md); architecture/scope authority is [Ground Truth](ground_truth/README.md).

## NOW — Kommun 1.1, pilot preparation

The core Kommun planning and packing flows, K25–K27, and Builder Gates 19–21E are product-owner accepted and protected. Do not reopen these paths without a reproducible regression.

1. **CLOSED (2026-11-06):** Admin Menu Import → Builder editor host outer white frame; product code checkpoint `3bfc9892`, owner-verified after reload.
2. **CLOSED for owner-approved desktop appearance (2026-11-06):** Department Portal menu-choice light/dark layout, week scrolling, equal lunch columns, weekend note and Dessert/Kvällsmat separation; checkpoint `1ff5dbef`. iPad/mobile and end-to-end interaction remain in final live walkthrough.
3. **NOW:** Audit and complete login/password recovery/security rules; preserve first-login/revocation and spinning globe.
4. Product-owner full Kommun walkthrough plus focused/full isolated regression, real Portal choice/submit, tenant/site/RBAC negatives, reports/export consistency, iPad/mobile; resolve nine legacy Portal JS test failures by proving fixture drift vs actual defects without redesigning accepted UI.
5. Clean-customer pilot acceptance, staging/migration/deployment checks, freeze/tag Kommun 1.1.

**Not overall pilot GO yet.** Report/export and meal-path behavior must be verified in the final acceptance; test-only failures do not automatically reopen accepted production features.

## THEN — Offshore 1.0

Resume the locked offshore MVP using the shared Builder, Planera 2.0 engine and site/tenant/auth foundation. Fresh scoped census before implementation; no duplicated production, menu or choice truth.

## THEN — Yuplan 1.0

Final cross-product platform release gate after Kommun 1.1 and Offshore 1.0 meet their individual pilot conditions.

## DEFERRED

Event/Hotel/Bankett, Home, generalized booking or asset modules, new recipe/ingredient expansion, autonomous menu substitutions, advanced analytics and broad rewrites. Future Lab is reference, not a pilot blocker.

## Historical planning documents

The September finishline and October status/handoff files on separate documentation branches preserve decisions and evidence, but their dated next-gate recommendations are superseded by the current [Live Acceptance](KOMMUN_1_1_LIVE_ACCEPTANCE.md). Do not create further competing MVP masterchecklists or dated status files.
