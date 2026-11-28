# SEC-FINAL Handoff — 2026-11-28

## Read first — operational status, not pilot acceptance

This handoff records the accepted security checkpoint and current project
priorities. SEC-FINAL is **closed within the verified scope**. This does not
grant Kommun 1.1 Pilot GO, Yuplan release GO, a real pilot migration, fresh
staging approval or deployment approval.

The current operational A–Ö ledger is
[Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md). The security
evidence and scope boundary are recorded in the
[Yuplan Security Baseline](../security/YUPLAN_SECURITY_BASELINE.md).

## Verified checkpoint

- Repository: `Henkemannn/YuplanUnified`
- Branch: `feat/planera-app-shell-2026-03-03`
- Accepted and pushed commit: `479bd9c356ebfcd6270b6c7340262c28ee2771ba`
- Parent: `091ddedb458a61ee52ceb492d6ee9c484a92a983`
- Local, tracking and remote HEAD were verified equal after push; worktree
  clean at product checkpoint.
- SEC-FINAL-07F-R accepted; 130 candidate source files individually verified.
- Source-manifest SHA-256:
  `72b1ac57c79d045b6cd979b188c3e4c33c551d9e0888ea729fc1020f3f7c3818`
- Approved SEC-FINAL-08A review ZIP SHA-256:
  `e3686b726d578bd0620ca832d76dd181bf3feb3d35ad8807c494d14983acf74a`
- Full isolated pytest: **3,259 passed, 0 failed, 0 errors, 32 skipped,
  3 warnings**. All 125 historical regression-test IDs passed.
- Candidate Alembic head **0059**; synthetic migration rehearsal
  **0050–0059**; isolated PostgreSQL **17.12** verification completed.
- Coordinated synthetic backup/restore was exercised. It does not prove a
  real-pilot recovery or establish a production restore procedure.
- Six protected database/checkpoint artefacts remained unchanged. The four
  protected database copies each retained SHA-256
  `1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67`;
  checkpoint 0057 retained
  `e7b82d138de75fd78c95eb47552ba5ec664b1ee35f25bb3ee098e65c9ad8607c`;
  checkpoint 0059 retained
  `70f6e3ec8d73337212ff84c501df72f408b3998519e48c0977f340902dcfccf2`.

The accepted scope covers the audited tenant/site controls, canonical dietary
identity and migration recovery, Builder runtime provisioning/isolation,
PostgreSQL runtime verification, report scope and CSRF hardening. Do not
reinterpret this scoped closure as a new general security audit or as
production runtime proof.

## Documentation-branch reconciliation

The 04R handoff was inspected read-only from remote branch
[`handoff/sec-final-04r-2026-11-27`](https://github.com/Henkemannn/YuplanUnified/blob/handoff/sec-final-04r-2026-11-27/docs/handoffs/SEC_FINAL_04R_HANDOFF_2026-11-27.md),
tip `c19e193bb9e2e8fb36aaf171afa4b8fdbfc23250`; the file blob was
`a81ce8ab3ddf4ecedeac33af8825afaca7380e09`. Its “await 04R report” and
pre-08A checkpoint are historical and superseded by the accepted 08A push and
this handoff. The branch was not checked out, fetched, merged, rebased or
modified. The old handoff remains preserved on that branch.

## CI-RECOVERY-01 — prioritized open stabilization task

After the push, GitHub Actions run
[46160919466](https://github.com/Henkemannn/YuplanUnified/actions/runs/46160919466)
failed on the accepted commit:

- Vitest: **112 passed, 16 failed**, 7 failing files of 34:
  - `portal_department_week_choice.test.js`
  - `unified_admin_need_picker.test.js`
  - `builder_standalone_runtime.test.js`
  - `admin_menu_import_week_actions.test.js`
  - `planera_product2_page3_completion.test.js`
  - `admin_builder_iframe_color_scheme.test.js`
  - `builder_calculation_utils.test.js`
- Ruff 0.6.3 repository-wide:
  - `admin/ui_blueprint.py:1984` — F811.
  - `core/planera_v2/adapters/kommun_target_demand.py:227` — F822.
- The backend pytest job stopped at Ruff; backend pytest was not reached.
- `openapi-validate` passed; the separate [markdownlint run
  #828](https://github.com/Henkemannn/YuplanUnified/actions/runs/46160919460)
  passed.
- Separately verify PostgreSQL service/job scope and the migration command's
  `|| true`. Do not conclude that the failures are all pre-existing until
  comparative reproduction is done.

Treat CI-RECOVERY-01 as the next prioritized stabilization task before
continued product development. First inspect the workflow scope and migration
command, then reproduce and classify the reported failures against a
meaningful baseline. Do not weaken assertions or make fixes from assumptions.

## TEST-ISOLATION-01 — separate open test issue

A reproducible test-order dependency is reported between
`unified_admin_departments_phase2` and `admin_department_service_addons`.
This needs its own bounded test-isolation diagnosis. Its root cause is not
established here, and it is not evidence of a production defect by itself.

## Current A–Ö status

The owner-accepted AÖ-01–27 ledger is preserved in
[Kommun 1.1 Live Acceptance](../KOMMUN_1_1_LIVE_ACCEPTANCE.md). No A–Ö feature
was changed by SEC-FINAL-08A. Status summary:

- **CLOSED (16):** AÖ-01, 03, 05, 06A/B, 07, 08A/08I/08B, 12, 13, 14, 16,
  17, 20, 21, 24, 25, 26.
- **OPEN (9):** AÖ-02, 04, 09, 10, 11, 18, 22, 23, 27.
- **PARTIAL (1):** AÖ-19 — publication, modal and Admin unpublish safety
  accepted; site-scoped Kitchen searchable recipe-library permissions remain
  open. Automatic notices/diffs are deferred by owner decision.
- **CANCELLED (1):** AÖ-15 — rolled back; do not revive without a new owner
  decision.
- **Ancillary OPEN:** AÖ-IPAD-PRINT-01, AÖ-PWA-01,
  AÖ-KITCHEN-ALT2-01.

Preserve accepted UX and security behavior. AÖ-13 Thursday visual polish is
tracked under AÖ-27. AÖ-20 ISO year-boundary E2E and the noted long-label,
pagination and release-device checks are not claimed as passed.

## Remaining pilot blockers

The SEC checkpoint does not settle:

1. **Authoritative Builder storage** and the operational backup path.
2. **Legacy Unit/Assignment site identity** and a validated migration path.
3. **Runtime and restore evidence limits:** synthetic rehearsal is not a
   real-pilot backup/restore drill.
4. **Production configuration, secrets and authentication flows:** verify
   current runtime controls, secret handling/rotation, HTTPS, CSRF, and actual
   reset/authentication flows in approved staging.
5. **Separate owner approval** for any real pilot migration and deployment.

The older Fly.io Yuplan installation is a historical version, not the current
development or pilot environment. No deployment was performed in this gate.
The post-push GitHub Deployments API returned an empty list; external Fly.io
configuration is not fully verified.

## Recommended next bounded order

Issue **CI-RECOVERY-01** as a read-only-first stabilization order:

1. Inspect CI PostgreSQL service/job scope and the migration `|| true`
   behavior.
2. Compare the failed run with a relevant baseline; do not assume all errors
   predate the accepted commit.
3. Reproduce and classify the seven Vitest failure files and the two Ruff
   findings; distinguish code regressions from test-fixture or CI setup issues.
4. Keep TEST-ISOLATION-01 separately bounded; avoid mixing its repair into
   unrelated product changes.
5. Propose only evidence-backed minimal corrections in a later authorized
   order. No tests, migrations, production changes, commit or deployment are
   authorized by this handoff.

After CI recovery is independently reviewed, continue the open A–Ö work in
owner-priority order. Keep real pilot migration, deployment and operational
secrets as separate approval gates.
