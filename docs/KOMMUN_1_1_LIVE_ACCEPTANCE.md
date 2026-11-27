# Kommun 1.1 — Live Acceptance & UX Race

## CURRENT — 2026-11-27 | SEC-CLOSURE-01 security reconciliation

**Operational authority:** This section supersedes every earlier `CURRENT` section and
next-gate statement below. Earlier A–Ö decisions, acceptance entries, security
evidence and limitations remain historical and are preserved unchanged. This
reconciliation does not grant pilot GO, release GO, staging GO, migration approval
or deployment approval.

### Verified checkpoint and full regression

- Branch: `feat/planera-app-shell-2026-03-03`
- Local, tracking and remote HEAD: `a2b6f5b55bf64b701d1e1828840559778f303132`
- Working tree: clean; staged/untracked: `0/0`
- Full command: `.\.venv\Scripts\python.exe -m pytest --no-cov -ra --tb=short`
- HEALTH-16D: **3138 passed, 0 failed, 0 errors, 15 skipped, 3 warnings,
  exit 0, 945.40 seconds**
- Full log:
  `%TEMP%\SEC-HEALTH-16D-full-pytest.log`
- Log SHA-256:
  `8e4d94ec4752d1e810780e291117048c19664d46acc92548fd5dd80f7203e589`
- Alembic head: `0055_weekview_schema`
- Protected `instance/yuplan_mvp.db` and the protected backup both remain
  SHA-256 `1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67`.
- The full run used isolated temporary test databases. It did not use the
  protected pilot database or an external production database.

### SEC-01 reconciliation — implementation is complete; closure remains scoped

The fifteen original Astra SEC-01 findings have implemented remediations in the
verified Git history. Targeted regression evidence and the HEALTH-16D full suite
are green at the checkpoint above. “Scoped CLOSED” means that the audited
surface and its regression contract are addressed; it is not a blanket
certification of every route, tenant-data path or deployed runtime.

| Finding | Original risk / severity | Implemented remediation and verified commits | Regression evidence | Closure |
|---|---|---|---|---|
| F01 | Admin, Notes and Audit authorization / HIGH | Admin target scope and support/impersonation boundaries; `f542051d`, `87346fd6`, `67b9932e`; Notes site scope and Audit API changes in `eca346d2` | Focused admin/auth/site regressions; HEALTH-16D full suite | Scoped CLOSED |
| F02 | Menu API authorization / HIGH | Role and tenant/site resource checks consolidated in the security hardening history, including `eca346d2` | Focused menu/API/site regressions; HEALTH-16D full suite | Scoped CLOSED |
| F03 | Dish/Menu relationships, Municipal, import, Builder and references / HIGH | Site/tenant integrity, atomic legacy writes, and import guards; `eca346d2` added the audited migrations `0051_add_site_scoped_menu_uniqueness`, `0053_add_site_scope_to_dishes` and `0054_add_menu_import_guards` | Dish/Municipal, Builder/import, migration and combined suites; HEALTH-16D full suite | Scoped CLOSED for audited paths |
| F04 | Builder import auth/session scope / HIGH | Import authentication/session isolation and guard handling; `eca346d2` | Builder/import and session regressions; HEALTH-16D full suite | Scoped CLOSED |
| F05 | Denied login retaining session or token / HIGH | Denied HTML/JSON login paths fail closed without establishing usable auth; auth/session hardening in `eca346d2` and `b14cf629` | Auth login, disabled-account, password and token regressions; HEALTH-16D full suite | Scoped CLOSED |
| F06 | Refresh token accepted as access Bearer / HIGH | Bearer type and JWT validation hardened; `b14cf629`, `7df6f853` | JWT/auth negative-path regressions; HEALTH-16D full suite | Scoped CLOSED |
| F07 | Revoked/deactivated binding still usable / HIGH | Active-user, auth-version and strict site-binding checks; `5b301e8d`, `129d2b8d`, `9f9af654` | Revocation, deactivation and real-actor site tests; HEALTH-16D full suite | Scoped CLOSED |
| F08 | Export data leakage / HIGH | Report route authorization before reads and site-scoped report/export paths; `6688a0a0`, `9eb3d810`, `3eaad981` | Focused report/export suite and full regression | Scoped CLOSED for audited exports |
| F09 | Planera cross-site/resource-ID access / HIGH | Tenant and bound-site checks on legacy GETs and audited mutation routes; `9c6d98c1`, `2ce85af7` | 109/109 legacy route tests, 62/62 mutation tests, full regression | Scoped CLOSED for audited routes |
| F10 | Anonymous demo reaching real tenant data / HIGH | Deployed/demo guards and permanent synthetic anonymous isolation tests; `1d6c3f26`, `6d27154b` | 51/51 targeted anonymous/auth-site tests; HEALTH-16D full suite | Scoped CLOSED for examined configuration/routes |
| F11 | Weak or unsafe SECRET_KEY fallback / HIGH | Fail-closed runtime environment and JWT fallback policy; `d3d6cb8a` | Configuration and negative-path tests; HEALTH-16D full suite | Code/test scoped CLOSED; runtime release proof OPEN |
| F12 | Support authorization scope / MEDIUM | Support UI security and support authorization boundaries; `8a44b8f1` | Focused support UI/authorization tests; HEALTH-16D full suite | Scoped CLOSED |
| F13 | Unbounded upload/parser resources / MEDIUM | Upload size, parser and resource limits; `1cad0370` | Upload/parser limit regressions; HEALTH-16D full suite | Scoped CLOSED |
| F14 | Temporary password exposed in UI / MEDIUM | Safe temporary-password presentation and reset replay protection; `705b28b2` | Temporary-password/reset regressions; HEALTH-16D full suite | Scoped CLOSED |
| F15 | Destructive Weekview runtime schema repair / MEDIUM | Explicit canonical schema, atomic `0055_weekview_schema` and removal of runtime mutation; `ac618601`; cohort/portal test stabilization `5002e52e`; schema-isolated legacy regressions `a2b6f5b5` | Runtime/schema, migration, Weekview and HEALTH-16D full suite | Scoped CLOSED for audited runtime/migration paths |
| JWT | Separate RS256/HMAC algorithm confusion concern | Reject unsafe algorithm/fallback combinations and landing Bearer misuse; `7df6f853`, `d3d6cb8a` | JWT negative-path regressions; HEALTH-16D full suite | Scoped CLOSED for configured HMAC paths; live secret/runtime proof OPEN |

SEC-DELETE-01 (cross-tenant/null-site dietary deletion) and SEC-DELETE-02
(conflicting site bindings and authentication) were previously reviewed and are
also **scoped CLOSED**, with their targeted negative/positive regressions
preserved in the historical security record.

### What is and is not verified

**Implemented and test-verified:** the source remediations listed above, their
focused negative/positive regressions recorded in the historical gate reports,
and the complete HEALTH-16D run at the current checkpoint.

**Not verified by this closure:** PostgreSQL runtime behavior, a real fresh
staging deployment, a production-like HTTPS/cookie environment, a real
application password-reset delivery, provider credential rotation, backup
restore, or a live multi-role customer walkthrough. No actual pilot GO or
release GO is issued.

The following remain required before release/pilot acceptance:

**Before returning to the A–Ö work:**

1. Run PostgreSQL runtime and migration verification against an isolated
   temporary database.
2. Rehearse migration `0050 → 0055` on an isolated copy of the pilot database;
   verify row counts, constraints, indexes, schema head and application
   behavior. Do not migrate the protected original in this gate.
3. Perform backup, restore and data-integrity verification, including a
   documented recovery result.
4. Complete the final SEC reconciliation.

**Before actual pilot start:**

1. Build a fresh current-code staging/runtime configuration.
2. Verify runtime secrets, HTTPS, secure cookies, CSRF, rate limiting and
   fail-closed behavior.
3. Execute the real Yuplan password-reset flow over HTTPS with the configured
   mail provider.
4. Run role/site/tenant golden-path and denial walkthroughs with authorized
   synthetic or approved staging accounts.
5. Define and manually execute handling for
   `menu_import_guards.status = needs_review`; the guard is not an automatic
   distributed rollback or Saga.
6. Close all remaining release blockers and obtain explicit owner acceptance.

The historically exposed Postmark Server API Token must be rotated or revoked
by the owner and that action must be confirmed without recording the token.
The separate SMTP Access Key and SMTP Secret Key are different credentials and
must be handled and rotated independently; no secret values belong in this
document. Historical Fly installations, data, volumes and secrets remain
untouched.

### HEALTH-16D skipped-test classification

The 15 skips remain visible and are not treated as failures. Their actual
conditions are:

- Legacy portion-recommendation tests are superseded by service tests
  (historical test debt).
- The Redis token-bucket module is skipped because `redis-py` is absent.
  Redis-backed runtime behavior remains a release verification item if that
  backend is selected.
- The site-binding upload test is explicitly skipped because site-binding 403
  is enforced in dev/prod while the test runs with the TESTING bypass. This is
  a TESTING-environment limitation and requires a non-TESTING staging check.
- The DOCX and XLSX “missing library” cases intentionally skip when
  `python-docx` and `openpyxl` are installed; the dependencies are installed,
  so these are test-contract cases, not missing-dependency evidence.
- Placeholder problem-mode cases cover an absent placeholder endpoint.
- A CSRF functional case has no user bootstrap.
- Admin UI/diet-table cases are unavailable in the test environment.
- One Weekview/menu-planning case requires a larger department/site fixture.

None invalidates the 3138-pass result. The skips do not provide evidence for
PostgreSQL, backup/restore, hosted reset, credential rotation or live
golden-path acceptance.


## CURRENT — 2026-11-25 | SEC-F10 scoped CLOSED; SECURITY WORK CONTINUES

**Operational authority:** This section supersedes earlier F10 OPEN/next-gate statements; previous A–Ö acceptance and SEC evidence below remain historical. No municipal pilot GO, staging deployment GO, migration, or entire SEC-01 signoff.

- **New verified product/test checkpoint:** `1d6c3f269b9afb06bb909ed31bd276f91652bac4` on `feat/planera-app-shell-2026-03-03`, owner-confirmed Git CLEAN, origin match, and protected original/backup SQLite unchanged. Exactly one newly added file `tests/security/test_sec_f10_demo_anonymous.py` (326 lines), no production changes. GitHub SHA/diff independently verified.
- **SEC-F10-01/02 conclusion:** **F10 scoped CLOSED — no anonymous tenant-data exposure reproduced** in isolated synthetic tests. Local public `/demo`, `/demo/ping`, `/ui/demo` contain no customer markers; staging, pilot, production and Fly demo route/auth-bypass blocked in tested scenarios. Nine permanent F10 test identities; all ten actual protected GET/HEAD endpoints asserted registered and supporting both methods, with 20 anonymous requests returning 401 and no customer data. Real site-bound user can access own departments but not foreign same-tenant or cross-tenant department; placeholder demo login cannot access real tenant APIs. Targeted F10 + auth/site suite **51/51 PASS, exit 0**. Legacy `core/demo_views.py` not registered. Local `/_routes` header diagnostic gives route names only; never enable it in staging/pilot/production.
- **Limits and regression baseline:** F10 closure is restricted to examined routes and configuration, **not proof of security for a future public hosted demo**. No real deployed runtime was inspected. Previous **HEALTH-12R full pytest GREEN** at pre-F10 source: **3,018 total, 3,003 PASS, 0 FAIL, 0 ERROR, 15 SKIP**. F10 adds nine test identities after this checkpoint; **full pytest has not been rerun**, by design (avoid costly full run per minor gate).
- **Security backlog now:** F01–F10 CLOSED within their audited scopes; F11 code/scoped CLOSED but fresh runtime/staging secret proof OPEN; JWT RS256/HMAC negative algorithm-path review OPEN; F12–F15 P1 OPEN. NEXT: bounded **SEC-F11-RUNTIME-01** read-only inventory, then scoped JWT follow-up; continue SEC before returning to Kommun 1.1 A–Ö.
- **Process and sync:** One Copilot order/report/review, no broad speculative rewrites. Documentation-only remote commits after product HEAD require owner-side verified CLEAN fast-forward to latest documentation HEAD before further local work. Pilot original and backup each remain user-reported SHA-256 `1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67`.

---

## CURRENT — 2026-11-25 | HEALTH-12R full-suite GREEN; SEC-F09 scoped CLOSED

**Operational authority:** This section is the current project checkpoint and supersedes older CURRENT/HEALTH-11/HEALTH-12/F09-next-gate language below. Historical A–Ö decisions, acceptance entries, and prior SEC audit evidence remain unchanged. **Full pytest GREEN does NOT approve pilot GO, fresh staging GO, deployment, migration of the original SQLite database, or entire SEC-01 closure.**

- **Verified source checkpoint:** `46277ded13cc66d4a8b67add5b94c7786618fafa` on `feat/planera-app-shell-2026-03-03`, reviewed and owner-verified Git CLEAN. F09 product/test commit `2ce85af7da3ca4acec7bffdcf011b0da7d93ad9c` changed exactly six scoped files; HEALTH-12 recovery commit `46277ded13cc66d4a8b67add5b94c7786618fafa` changed exactly seven test files and no production code. GitHub comparisons independently verified.
- **F09 Planera/Weekview scoped CLOSED:** Previous `GET /api/planera/week` and `GET /api/planera/week/csv` were closed earlier (109 focused PASS). Newly closed ID-target writes: four Weekview PATCH routes (marks, residents, ALT2, specialdiets), `POST /api/kitchen/planering/normal_exclusions/toggle`, and `POST /ui/planera/day/mark_done`. The authorization checks tenant/site ownership of targets and denies ordinary-user cross-site/cross-tenant IDs, including absent or false `site_lock`; `mark_done` checks mixed department IDs before any mutation; specialdiets missing-If-Match ETag fallback is after authorization. Weekview's original **admin/editor-only** mutation roles retained. 62/62 focused tests passed, including 15 real-login F09 security identities. This is scoped closure of audited routes only, not blanket certification of every API or tenant-data surface.
- **HEALTH-12 failed checkpoint:** At the F09 code commit, full pytest yielded **3,018 total, 2,992 PASS / 11 FAIL / 0 ERROR / 15 SKIP**. All 15 new F09 tests passed, but 11 previously green legacy Report/Weekview/Planera tests had invalid synthetic/unbound Site/Department fixtures. Target authorization was not weakened; seven test files were corrected for proper tenant/site/department seed data and verified setup writes; targeted recovery replays **26/26 and 74/74 PASS**.
- **HEALTH-12R full regression GREEN:** One complete run under project Python venv and isolated temporary SQLite, **3,018 total; 3,003 PASS / 0 FAIL / 0 ERROR / 15 SKIP; exit 0; 1,125.20 s (~18m45s)**. Three existing OpenAPI validator deprecation warnings. Exact JUnit `classname + name` reconciliation: **all 11 HEALTH-12 FAIL→PASS**, zero old PASS regressions, zero removed identities, unchanged 15 SKIP identities, no duplicate IDs; vs HEALTH-11 exactly 15 new F09 tests all PASS and no earlier statuses changed. Local test artifacts reported at `%TEMP%\yuplan-health-12r\pytest-junit.xml` and `pytest-output.txt`. Copilot/owner report is the runtime evidence; committed source checkpoint was verified separately on GitHub.
- **Protected SQLite pilot:** Both `instance/yuplan_mvp.db` and `C:\Users\Henrik Jonsson\YuplanPilotBackups\yuplan_mvp_20261123_135608.db` reported unchanged before/after testing: SHA-256 `1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67`. No schema migration, prod/staging deployment or pilot-DB write.
- **Security plan:** F01–F08 previously scoped CLOSED; **F09 now scoped CLOSED and full-suite GREEN**. **NEXT: SEC-F10 OPEN P0 (anonymous demo access to real tenant data)**, followed by F11 fresh runtime/staging secret controls, separate JWT RS256/HMAC algorithm-confusion verification, and F12–F15 P1 findings. No return to Kommun A–Ö UX until remaining SEC work is finished. Keep existing A–Ö statuses as historical ledger, not permission to modify UX during security gates.
- **Process and sync:** One order → one Copilot report → independent review → guarded commit. Focused tests per bounded security fix; full pytest at material checkpoints, not on every small step. These two docs-only remote commits must be synced to local via **clean, locked, fast-forward-only pull** before starting F10.

---

## CURRENT — 2026-11-25, HEALTH-11 full-suite GREEN

**Operational authority:** This is the latest status and supersedes prior HEALTH-10/current/next-gate sections below. Prior A–Ö acceptance statuses and historical SEC evidence are preserved. **GREEN pytest is not permission for pilot GO, staging GO, deployment, migration of the original pilot DB, or SEC-01 closure.**

- **Verified product HEAD (before these documentation-only commits):** `9ce2952cbeb12d2a8e7adf53c53135b2a1284a2d`, branch `feat/planera-app-shell-2026-03-03`. HEALTH-10R test-only commit `test: stabilize site-binding regression fixtures` was reviewed, user-verified pushed with Git CLEAN and both protected DBs unchanged, and independently GitHub-verified to contain exactly three test files: `tests/reports/test_admin_report_week_real_login_isolation.py`, `tests/test_admin_user_target_authorization.py`, `tests/ui/test_login_ui.py`. No production code was changed by HEALTH-10R.
- **HEALTH-11 full pytest:** One complete nonparallel isolated-temp-SQLite run, exit **0**, **3,003 total: 2,988 PASS / 0 FAIL / 0 ERROR / 15 SKIP**, 3 existing `openapi_spec_validator` deprecation warnings, elapsed **1,493.22 s (24:53.22)**. Evidence: user's Copilot-generated JUnit and full log at `%TEMP%\yuplan-health-11\pytest-junit.xml` and `pytest-output.txt`. The full run is reported by Copilot and locally verified by the user's terminal process; GitHub independently confirms the corresponding source checkpoint, not the local TEMP files.
- **HEALTH-10 → HEALTH-11 JUnit identity comparison:** Both contain precisely **3,003 identical test identities**, all **10** HEALTH-10 failures became PASS; **0** prior PASS turned FAIL/ERROR/SKIP; **0** added/removed cases; the **15 SKIP** identities remain the same. All six login role cases, three F08 real-login cases, and admin staff-creation site-binding case are PASS. No reported full-suite failures for SEC-F08, SEC-F09-LEGACY, or SEC-DELETE regression tests. **HEALTH-10R test recovery CLOSED; current Python full regression GREEN at product HEAD above.**
- **HEALTH-10R cause and bounded remedy:** pytest-session shared temporary DB contained orphaned `kitchen_user_sites.user_id` rows; fixed test user-ID allocation above both the `users` and existing `kitchen_user_sites` maxima instead of overwriting bindings. Admin staff-creation test now validates the active binding representation (`users.site_id` and/or `kitchen_user_sites`) and refuses conflicting dual sources. Combined targeted replays: **20/20**, predecessor-order **24/24**, security/auth **53/53 PASS**. Product authorization and strict tenant/site fail-closed unchanged.
- **SEC-F08:** Scoped report/CSV/XLSX/PDF/API code review CLOSED; focused 26/26 tests and relevant full-suite tests now PASS. `/ui/admin/report/week` checks `_authorize_report_scope` before data reads. No exploitable current-login data disclosure had been reproduced; the fix adds route-local defense-in-depth. Do not extrapolate to a blanket audit of all exports.
- **SEC-F09:** `GET /api/planera/week` and `GET /api/planera/week/csv` scoped CLOSED (earlier leak reproduction and 109/109 targeted tests). **Remaining original F09 resource-ID/write routes OPEN.** **F10 anonymous demo access OPEN P0.** F11 source fix closed but staging/runtime secrets proof outstanding; F12–F15 and JWT RS256/HMAC investigation OPEN.
- **Protected original DBs:** `instance/yuplan_mvp.db` and `C:\Users\Henrik Jonsson\YuplanPilotBackups\yuplan_mvp_20261123_135608.db` verified unchanged before and after HEALTH-11; each SHA-256 `1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67`. No schema migration, deployment, production test or code changes in HEALTH-11.

**Immediate next gate:** `SEC-F09-REMAINING` — inventory and test remaining Planera **ID-based write/mutation endpoints** for real-account site/tenant authorization (including cross-site IDs, absent/false `site_lock`, revoked users and negative/positive scope), without reopening already-closed legacy week GETs or changing unrelated UI. One order → one Copilot report → security review → guarded commit; focused pytest per change. Then `SEC-F10` (anonymous demo real-data access P0) and remaining SEC-01 findings. Avoid repeat full pytest after each small change; rerun full suite after ~2–3 significant security gates, at risk checkpoints, or on a new suspected order-dependent failure, recording JUnit identity comparisons. Preserve A–Ö as historical ledger until SEC-01 complete.

**Git sync:** These documentation-only commits advance the remote branch beyond product HEAD `9ce2952c…`; the local user must perform a verified CLEAN fast-forward before giving Copilot an order that requires the new remote HEAD.

---

## CURRENT — 2026-11-24, HEALTH-10 full-suite checkpoint

**Authority:** This section supersedes older CURRENT checkpoint/test-status/next-order claims below. Historical accepted A–Ö statuses and prior SEC-01 evidence remain unchanged. **No Pilot GO, staging GO, Yuplan 1.0 release GO or original-pilot-DB migration approval.**

- **Verified local/remote product HEAD before these documentation-only commits:** `3eaad9816bfbadfef0baeb95b82a8ba8ee180bda` on `feat/planera-app-shell-2026-03-03`. Owner ran locked F08 fast-forward from `9c6d98c1…` to documentation checkpoint `08809c4a…`, then reviewed F08 product/test commit/push; Git CLEAN and local/origin/remote SHA matched. Independent GitHub compare verified identical.
- **SEC-F08-CLOSE code:** `/ui/admin/report/week` now runs `_authorize_report_scope(site_id, department_id)` before reading report site/department data. The original real-login tests demonstrated upstream 401/403 denials; missing defense-in-depth at the route was corrected but an exploitable disclosure under existing auth was **not** reproduced. Focused report/CSV/XLSX/PDF/API and spy-test suite **26/26 PASS**, 0 skips. **Scoped code correction CLOSED; full-suite regression acceptance OPEN.**
- **SEC-F09-LEGACY:** Two GET routes `/api/planera/week` and `/api/planera/week/csv` scoped CLOSED at `9c6d98c159d970de1db8dd252dc3f718c687da01`; 109/109 targeted tests passed. The overall F09 resource-ID scope still requires final reconciliation; do not reopen already reviewed paths without a new regression.
- **SEC-DELETE-01/-02 and HEALTH-09D:** Previously reviewed, pushed and targeted-green, as documented in the earlier CURRENT 2026-11-24 overlay below. Do not declare full regression GREEN from these focused tests.

### HEALTH-10 — one complete pytest run at F08 product checkpoint

| Metric | HEALTH-09 (previous full suite) | HEALTH-10 (2026-11-24) |
| --- | ---: | ---: |
| PASS | 2,959 | **2,978** |
| FAIL | 13 | **10** |
| ERROR | 0 | **0** |
| SKIP | 15 | **15** |
| Total | 2,987 | **3,003** |

- Executed exactly once under project `.venv` without test selection or parallelization. **HEALTH-10 exit 1, 2,834.78 seconds (~47m14s), NO-GO for overall GREEN.** Raw artifacts saved under `%TEMP%\yuplan-health-10\pytest-junit.xml` and `pytest-output.txt`; HEALTH-09 JUnit available under `%TEMP%\yuplan-health-09\health-09.junit.xml`.
- **Exact JUnit identity diff:** 6 previously failed test cases became PASS; 7 previous failures remain; 3 new F08 real-login report tests fail in full-suite order; 16 new test identities, none removed.
- **Nine failures** report `sqlite3.IntegrityError: UNIQUE constraint failed: kitchen_user_sites.user_id` — 6 parameterizations in `tests/ui/test_login_ui.py::test_ui_login_redirects_by_role` and 3 tests in `tests/reports/test_admin_report_week_real_login_isolation.py`. The targeted F08 suite passed separately; likely shared, session-scoped test-database/seed-state collision, **not yet proven remedied in full suite**.
- **One failure** in `tests/test_admin_user_target_authorization.py::test_real_admin_can_create_and_manage_site_bound_staff`: `TypeError: 'NoneType' object is not iterable` when asserting that a new staff user's site-binding row exists. Must distinguish test state from a real user-creation regression; do not blindly rewrite production auth.
- New F08 test failures mean full-suite regression readiness is **OPEN**, even though scoped code/security review was approved. No F09-legacy or SEC-DELETE-related failures reported in HEALTH-10.
- Both protected originals remained SHA-256 `1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67`: `instance/yuplan_mvp.db` and `C:\Users\Henrik Jonsson\YuplanPilotBackups\yuplan_mvp_20261123_135608.db`. Original remains protected; no migration, test against pilot DB, deployment, code changes or new commit during HEALTH-10.

### Next controlled gate: HEALTH-10R

First perform guarded **docs-only fast-forward** if local Git is still at product HEAD `3eaad981…`, without discarding dirty code. Then diagnose and resolve the **ten identified test failures**, using the saved JUnit/tracebacks and the smallest affected test fixtures; verify with a bounded combined-order pytest replay and real positive/negative site-binding tests. **Do not use `INSERT OR REPLACE` or global data deletion to conceal binding conflicts; never weaken fail-closed rules or test assertions.** A further complete pytest is authorized **only after** the ten-failure targeted evidence is green and reviewed. Preserve pilot hashes. One Copilot order → report → review → guarded code commit. After recovery, resume F09 residual/F10 and the remaining SEC findings.

**Test discipline:** targeted tests for every security change; compare JUnit test IDs at full-suite checkpoints every 2–3 substantial changes, not after weeks of accumulated work. Document actual FAILs, skips, duration and HEAD — never write GREEN from focused tests alone. This 47-minute full run reinforces the need to avoid frequent redundant full runs while maintaining periodic checkpoints.

---

## CURRENT — 2026-11-24 — SEC/HEALTH-recovery, F09 legacy closed, F08 next

**Authority:** This dated overlay supersedes the 2026-11-22 CURRENT checkpoint and next-task statements below. Keep all older detailed evidence and the 2026-11-18 A–Ö per-ID acceptance matrix intact as historical/owner-approved records. **No Kommun 1.1 PILOT GO, Yuplan 1.0 release GO, fresh staging GO or Fly deployment is claimed.**

### Verified source, worktree and protected pilot data

- Repository `Henkemannn/YuplanUnified`, branch `feat/planera-app-shell-2026-03-03`. **Latest owner-terminal-verified, pushed and independently GitHub-verified product HEAD before this docs-only update:** `9c6d98c159d970de1db8dd252dc3f718c687da01` — `fix(security): enforce tenant and bound site on legacy Planera week`. Local/remote HEAD matched; worktree CLEAN; no staged/untracked files.
- **Protected original:** `instance/yuplan_mvp.db`. **Verified backup:** `C:\Users\Henrik Jonsson\YuplanPilotBackups\yuplan_mvp_20261123_135608.db`. Current SHA-256 of **each**: `1add124065aae2aa995619aa9dcc349252a39493e0ea1855bb5ce0b3f21dbd67`; verified unchanged across recent HEALTH/SEC gates. The SHA `acf627...` in the 2026-11-22 overlay is **historical and must not be used as today's preflight guard**.
- Current code migration head was `0054_add_menu_import_guards`; original protected SQLite was previously documented at Alembic `0050_add_password_reset_storage`. No migration of the protected original, deployment or new staging occurred during the gates below. A copy-only 0050→0054 rehearsal was previously verified; do not treat this as approval to migrate the original.
- **Documentation-only GitHub commits advance remote HEAD.** Before the next Copilot gate or local edit, guarded `git fetch` + `git merge --ff-only` is required if local HEAD is still `9c6d98c1…`, with a CLEAN local worktree; never force-reset/rebase or run against a stale checkpoint. The product-code checkpoint above is not the post-docs Git tip.

### Completed since the 2026-11-22 overlay — reviewed, committed and pushed

| Work | Verified product commit / evidence | Disposition |
| --- | --- | --- |
| **SEC-DELETE-01** — cross-tenant legacy/null-site special-diet deletion | `da53d6137957ee5e4d02ca1a3327b4e92ca3800d`; `DietTypesRepo.delete_scoped()` and both registered deletion implementations, targeted negative/positive tests | **Scoped CLOSED** |
| **SEC-DELETE-02** — conflicting site bindings and authentication | `9f9af654ff632a0a35d1d3708f5119d21a485664`; shared fail-closed `_resolve_user_scope()` for login, established sessions, Bearer/JWT; active-user/auth-version and password-change restrictions tested | **Scoped CLOSED** |
| **HEALTH-09D** — duplicate site verification / order-dependent fixtures | `f54ef73d239923432e3afde3cd299d6bd1fc9c03`; `core/auth.py` site-binding adapter plus eight test files; 31 auth/real-actor, original 13/13, historical 81/81 and 28/28 six-module tests PASS in separate targeted runs | **Targeted regression CLOSED; full-suite confirmation OPEN** |
| **SEC-F09-LEGACY** — `GET /api/planera/week` and `/api/planera/week/csv` | `9c6d98c159d970de1db8dd252dc3f718c687da01`; reproduced real-login data exposure for same-tenant other site and different tenant; fixed tenant ownership and ordinary-account bound-site checks regardless of `site_lock`; 109/109 targeted tests PASS | **These two F09 routes scoped CLOSED** |

### HEALTH full-suite evidence — do not conflate with targeted PASS

- **HEALTH-09** full pytest ran **2,987 tests: 2,959 PASS, 13 FAIL, 15 SKIP, 0 reported ERROR** in approximately **17 min 46 sec** at HEAD `9f9af654…`. The 13 failures comprised 8 fixture/database/order cases and 5 auth/sitebinding cases.
- **Later HEALTH-09B/C/D** repaired and verified these cases using focused runs: original **13/13 PASS**, historical 81-node replay **81/81 PASS**, six modules together **28/28 PASS**, auth/sitebinding and real-actor **31/31 PASS**. These test groups overlap; counts must not be added together.
- **A fresh full pytest on the later commits has NOT run.** Run one final full suite only after remaining SEC-01 corrections, then classify any remaining failures. Neither targeted green tests nor a clean Git status implies overall security/release approval.

### SEC-01 disposition as of 2026-11-24

| Finding | Current status | Exact remaining evidence / work |
| --- | --- | --- |
| F01–F07 | **Scoped CLOSED** for previously audited paths | Preserve existing remediations; revisit only on proven regression. F03 scope/migration caveats from Nov 22 remain. |
| **F08** export/report tenant/site data exposure | **OPEN — NEXT gate: SEC-F08-CLOSE** | Existing report-isolation tests and previously scoped fixes must be reused; verify actual registered HTML/CSV/XLSX/PDF/API routes with real-user login and negative tenant/site/department tests. No new report or reviewed diff yet. |
| **F09** Planera cross-site/ID scope | **PARTIAL — legacy week JSON/CSV CLOSED** | Real-actor denial proven for the two legacy week endpoints; day/production-completion previously tested, task legacy quarantine observed. Final original-finding-to-route reconciliation for any other ID-based writing paths remains, without reopening accepted fixes. |
| **F10** anonymous demo portal | **OPEN — P0** | Verify anonymous reachability and whether actual customer data can be read; fix only reproducible exposure. |
| **F11** strong secrets policy | **Code/scoped CLOSED; runtime/staging verification OPEN** | Fresh staging secrets, cookies, negative runtime behavior, hosting E2E; stale Fly is not the current target. |
| **F12–F15** | **OPEN — P1** | F12 support authorization; F13 upload limits/failure handling; F14 temporary passwords in UI; F15 Weekview schema mutations on request. |
| **JWT RS256/HMAC algorithm confusion** | **OPEN — focused security verification** | Validate algorithm selection, secret separation and rejection of invalid tokens against current code. |

### Scope, product acceptance and next order

- **SEC-F08-CLOSE** has been issued as the next Copilot order; its report is **not yet reviewed/committed**. One order → one Copilot report → project-lead review → guarded owner commit/push. Do not mark F08 CLOSED from existence of tests alone.
- After F08: reconcile F09's residual original-finding coverage; complete F10 and the remaining security findings by actual pilot risk; then one full pytest and final security go/no-go. No speculative new SEC families or 18-minute pytest at every small gate.
- **Kommun 1.1 A–Ö unchanged** from 2026-11-22: 16 CLOSED, 9 OPEN (AÖ-02/04/09/10/11/18/22/23/27), AÖ-19 PARTIAL, AÖ-15 CANCELLED, and separate iPad print/PWA/Alt2 checks. No owner acceptance, design, deployment or new customer pilot was silently added.
- Production/pilot gate remains: real multi-role customer/site walkthrough, tenant/site negative tests, iPad Safari both orientations, reporting/export parity, Postmark real hosted reset, backup/migration rehearsal on copies then separately authorized production migration, fresh staging and owner signoff.

---
## CURRENT — 2026-11-22 — status, A–Ö, SEC-01 and next handover

**Authority:** This dated section supersedes older CURRENT/next-gate claims below; retain the detailed 2026-11-18 A–Ö matrix as the per-ID acceptance ledger. Earlier snapshots, old HEADs and next-order statements are historical. No overall Kommun 1.1 PILOT GO, no Yuplan 1.0 release GO, and no fresh staging GO.

### Latest Git and database checkpoint (owner terminal verified)

- Repository: Henkemannn/YuplanUnified. Active branch: feat/planera-app-shell-2026-03-03.
- **Last product/security code commit (before documentation-only updates): eca346d2fa6368843d1486b3fb124cfd7297cb11**, 2026-11-22; message: security: consolidate tenant-site isolation and pilot fixes. Owner verified commit, push, remote HEAD equal to local HEAD and CLEAN worktree. 79 files committed (+7,052/-495 lines). **Any docs-only commit after this checkpoint changes remote HEAD and requires a guarded local fast-forward before further development.**
- Development Alembic head: **0054_add_menu_import_guards**. Original local pilot database **instance/yuplan_mvp.db** remains at **0050_add_password_reset_storage**; it was NOT migrated during SEC-01/F03. Verified original SHA-256: **acf627a87ebb2bed9ec6521a982ea76bd1b3de53b3a8c11795fcef5e3b5de6f2**.
- F03-09: SQLite online-backup and separate working copy under SEC_F03_09_MIGRATION_20261122 were migrated **0050 → 0051 → 0052 → 0053 → 0054**, without manual stamp. Counts unchanged: tenants 2, sites 2, users 10, menus 23, dishes 248, variants 520. Zero NULL-site menus/dishes, zero cross-tenant/site MenuVariant/Dish relations, zero duplicate site/week menus, zero missing Dish refs in the migrated copy. This **proves that particular migration rehearsal**, not deployment or production migration approval.
- Old Fly installation is a stale historical environment; do not use it as an active development target, migrate it blindly, or claim code was deployed. User decision: finish Kommun locally, then build **fresh staging**.

### SEC-01 status (Astra independent review → scoped Copilot remediations)

Astra reported 15 numbered findings: 11 high (F01–F11), 4 medium (F12–F15). An additional RS256/JWT algorithm concern was recorded. Current disposition from targeted Copilot reports and local tests, **not a new independent full security audit**:

| ID | Status 2026-11-22 | Evidence / next action |
| --- | --- | --- |
| F01 | **Scoped CLOSED** | Admin target scope, Notes site scope (0052), Audit superuser boundary; targeted tests. |
| F02 | **Scoped CLOSED** | Menu API role/resource checks; targeted tests. |
| F03 | **CLOSED for the audited Dish/menu/import paths** | Cross-tenant/site Dish ID checks; atomic legacy variant write; migration 0051/0053; Municipal; Task/ServiceMetric Dish references; Builder/legacy session fix and 0054 import guard. F03-09 migration and focus regressions passed. No blanket proof of all operations. |
| F04 | **Scoped CLOSED** | Builder import auth/session scope; earlier targeted tests; include in release regression. |
| F05 | **Scoped CLOSED** | Denied login must not retain auth session. |
| F06 | **Scoped CLOSED** | Refresh JWT rejected where access Bearer required. |
| F07 | **Scoped CLOSED** | Revoked/deactivated user and live DB-bound access checks. |
| F08 | **OPEN — next P0** | Export authorization/data leakage. Reproduce active endpoints, correct only concrete tenant/site leak. |
| F09 | **OPEN — P0** | Planera cross-site authorization and resource ID scope. |
| F10 | **OPEN — P0** | Anonymous demo portal and possible real-data access. |
| F11 | **Code/scoped CLOSED; deployment acceptance OPEN** | Strong SECRET_KEY configuration policy, requires actual fresh-staging secrets and negative runtime checks. |
| F12 | **OPEN — P1** | Support authorization scope. |
| F13 | **OPEN — P1** | Upload limits and failure handling. |
| F14 | **OPEN — P1** | Temporary password flashed to screen: verify/remove unsafe exposure. |
| F15 | **OPEN — P1** | Weekview schema repair during request: deny unsafe runtime mutations, keep migrations explicit. |
| JWT RS256 | **OPEN — focused check** | Reject algorithm confusion when HMAC JWT_SECRETS are configured. |

**Hard delivery rule:** Complete F08 → F09 → F10 first, then RS256/F12–F15 by real pilot risk. One narrow security order → Copilot report → project lead review → tests → guarded commit. Avoid broad architectural rewrites, speculative threats and endless rounds; do not reopen F01–F07/F11 or accepted A–Ö without reproduced regression.

### F03 final evidence and honest limitations

- Most recent reported focused runs: 29/29 Dish/Municipal security, 17/17 Builder/import guards, 13/13 migration, and 290 passed + 1 pre-existing skip in an Admin/API/menu/site combined suite. Prior integration run: 302 passed + 1 skip. **These are overlapping runs; do not add their counts into a fake total.**
- **2,862 pytest cases collected, not executed as one full suite**. Known older Task-status and metrics/diet tests still fail at login HTTP 403 due to fixture/engine/context mismatch. Other historical Portal/Page2 UI fixture issues must be verified rather than hidden. Do not claim whole Yuplan regression-free.
- 0054 minimal **menu_import_guards** (tenant/site/year/week, operation ID, in_progress/completed/needs_review) blocks overlapping unfinished imports and blocks publication until verified. It **does not** implement automatic saga rollback, crash resume or distributed transactions. Failed imports require safe manual review, with an operational procedure before pilot. **Completed import is not the same as publication.** Do not add a Saga engine for the pilot.
- Read-only F03-08 Builder check found no newly reproduced active Dish/menu leak; F03-09 copy migration passed. Original database migration requires explicit separate approval, backup, verification and a real release window.

### Product and A–Ö (owner-accepted numbered ledger remains binding)

The detailed table immediately below (recorded 2026-11-18) remains the accepted per-ID evidence. **No A–Ö acceptance has been silently changed by the SEC work.**

- **16 CLOSED:** AÖ-01, 03, 05, 06, 07, 08, 12, 13, 14, 16, 17, 20, 21, 24, 25, 26.
- **9 OPEN:** AÖ-02 (Användare encoding); 04 (create diet type inline); 09 (Admin Users responsive table/actions); 10 (deactivate/delete decision); 11 (replace visible SCOPE); 18 (design consistency read-only census); 22 (Page3 heading cosmetics); 23 (Overview reversible dish/all selector); 27 (Weekview yellow highlight/Thursday polish).
- **1 PARTIAL:** AÖ-19: publication, Kitchen Dish modal and Admin unpublish warning accepted; Kitchen site-scoped searchable Recept & rätter library decision still open. Automatic publication-change notifications/diffs explicitly **DEFERRED**.
- **1 CANCELLED:** AÖ-15 rolled back. Never resurrect without new owner decision.
- **Three ancillary OPEN:** AÖ-IPAD-PRINT-01 (Production Lists print toggles), AÖ-PWA-01 (role-aware installed start route), AÖ-KITCHEN-ALT2-01 (Alt2 contrast).
- AÖ-09 Admin Users previously rejected as visually messy/unstable. Keep a full-width stable table (name/email, role, access, status, actions); no floating ellipsis that moves rows. Do not mark closed until owner accepts.
- Accepted: Admin/Kitchen app shell and login, Menu Builder/Components→Dishes→Menus/import, publication and week selection, Page2 review/Planera Page1–3, normal/specialkost production, Weekview completion, K25–K27 production lists/serving/packing, chosen iPad/Safari print fixes. Preserve exact locked behavior; tests do not replace final real user acceptance.

### Architecture and pilot acceptance rules

- **Tenant = kund; Site = arbetsplats/kök.** Ordinary users are DB-bound to exactly their site; never offer a site picker or implicit default. System superuser is separate from customer Users list and portal. No implicit cross-tenant or cross-site sharing; later permissioned multi-site features are out of pilot.
- Planera 2.0 Core uses canonical business/menu context. Distinguish **Specialkost** recipient needs from **Serveringsanpassning** department serving/packing instructions. Menu choice Alt2 yellow and completed green are independent truth.
- Kommun pilot golden path: new customer/site → account/roles → departments, resident/needs quantities and special diets → Builder menu import/create → publish → Department Portal menu choice → Planera Page1/2/3 → production/normal/specialkost → Production Lists/Servering/Packning → Kitchen Weekview mark done → reporting/export; then revisit with real reload, iPad/Safari print and negative permissions.
- **Release blocker checks:** export/report consistency, login and real reset mail, inactive/revoked user denial, tenant/site/department denial, iPad portrait/landscape light/dark, PWA and print, backup/restore, new current-schema staging HTTPS/secrets/cookies, verified original-data migration after explicit owner authorization, manual handling for needs_review, owner signoff.
- Postmark standalone SMTP delivery was owner-confirmed, but Yuplan hosted end-to-end reset flow not proven. Historical exposed provider token rotation confirmation pending. Never commit secrets.
- Current execution after SEC completion: full test run + categorize failures; bounded manual golden-path acceptance; remaining P2 A–Ö items in owner-priority order; fresh staging and release gate. **No pilot GO before evidence.**
- Future, not pilot blockers: Offshore 1.0 after Kommun freeze; then overall Yuplan 1.0. Event/Hotel/Bankett/Home and personal portable recipe library are future ideas, not active gates.

### Immediate next Copilot gate

**SEC-F08-A — READ-ONLY targeted export exposure audit** on the just-verified product commit. Identify actual active export routes, roles, request IDs, tenant/site filters, and reproducible same-tenant cross-site/cross-tenant attempts using synthetic data. Report exact source paths and minimal fix/test scope. Do not edit code, migrate databases, deploy, or create speculative export architecture. When F08-A report arrives, project lead issues one narrow repair only if evidence warrants.

### Work discipline / local synchronization

One order → one Copilot report → independent project lead review → tests + manual checks as needed → owner-approved guarded PowerShell commit/push → update this live ledger. Use verified branch, exact HEAD, dirty/staged manifest, git diff --check and pilot DB hash before consequential steps. A docs-only commit made directly on GitHub advances origin/branch while the user's local branch stays at eca346d2 until a **verified fast-forward**; never implement on top of stale local HEAD without syncing. Preserve prior backups and never force-push or auto-migrate the original pilot DB.

---



## HISTORICAL — 2026-11-18 — prior operational status

> This section and the **current status/priority matrix** are the only current Kommun 1.1 delivery ledger. The dated 2026-11-08 intake rows, earlier 'next' statements, October baseline and September finishline are preserved as historical evidence, **not current implementation instructions**. **No final Kommun 1.1 PILOT GO or Yuplan 1.0 release GO is claimed.**

**Active development branch:** `feat/planera-app-shell-2026-03-03`  
**Last confirmed pushed product checkpoint:** `347b958c1cadc80551fe0e46ebb5828e59c8f9be` — `feat(auth): support username login and preserve admin user form` (2026-11-18), **AÖ-01 CLOSED / OWNER-ACCEPTED / PUSHED**. Owner reported `AÖ-01 PUSH VERIFIED / CLEAN` after guarded PowerShell commit/push. GitHub branch tip and exact eight product/test files independently verified. E-post och globalt unikt ASCII-användarnamn stöds som alternativa inloggningar; case-insensitive username rejection, shared account rate limiting, inactive/deleted denial, Admin create/edit optional username, server-side email validation and form state preservation were tested. Final Copilot auth/Admin/UI regression: **159 passed, 0 failed**; owner manually reported all requested local acceptance checks working, including username login, duplicate rejection and preserved form after error. No schema migration, IDNA-equivalent email-login expansion, real-account reactivation, Fly deployment or pilot GO. International contact email with distinct ASCII username is the chosen Kommun 1.1 workaround; password reset with Unicode/Punycode equivalence is NOT claimed fixed.
**Earlier product checkpoint (AÖ-16):** `18dd96424ed14d83e0a8491d3d0ba538ddac984f` — `fix(shell): prevent iPad topbar badge clipping` (2026-11-13), **AÖ-16 CLOSED / OWNER-ACCEPTED / PUSHED**. Precisely `static/css/app_shell.css` and `static/tests/app_shell_topbar_layout.test.js` were committed; 2/2 focused Vitest tests, 1/1 focused Python shell/template test, and `git diff --check` passed. Product owner verified Admin and Kitchen on a real iPad in portrait and landscape, with visible badges, usable user menu and no clipped content; desktop appearance was also owner-approved. Static CSS tests are not browser geometry tests; extremely long labels at desktop widths >=1367px are a documented residual unverified overflow risk (not observed on owner's desktop). This is a local-code acceptance only, **no Fly deploy or Kommun pilot GO**.
**Earlier product checkpoint:** `f54b78f425fc84157ad96bfa388584d897590e5d` — `fix(planera): scope page2 review state to current option` (2026-11-13), **AÖ-21 CLOSED / OWNER-ACCEPTED / PUSHED**. AÖ-21 original first-visit false stale warning was reproduced in an isolated Page2 VM regression: previous loop variable `review_state` was used when rendering other options, and a returned unreviewed status object with `review_id=None` was treated as an existing saved review. Fix scopes decisions/state to current `option_id` and sets `review_present` only for a real persisted `review_id`. Product owner tested actual Yuplan Page2 alt1/alt2 switching and confirmed the correct behavior. Precisely two files changed (`core/ui_blueprint.py`, `tests/core/test_planning_option_review.py`), 25/25 review service tests and 15/15 review-related API tests passed, compile/diff check green. Three Page2 UI tests remain blocked by a separately preexisting isolated fixture `projection_error`, reproduced before and after fix: **test infrastructure debt, not a closed test suite or an excuse to suppress production safeguards**. Previously accepted AÖ-08 security test `ea8c0c2b`, AÖ-06H.3 `761c07e9`, AÖ-07 `828151f6`, AÖ-19 publication and modal gates `32696f55`/`93b5f5dd`/`be27f98f`, AÖ-20 week selector `7de5bfb4`/`81371499`, AÖ-13 `8ac4bc86`, AÖ-14 `9b73721e` remain locked.
**Last owner-accepted iPad visual UI checkpoint:** `18dd96424ed14d83e0a8491d3d0ba538ddac984f` (AÖ-16 shared topbar; Admin and Kitchen real-iPad portrait/landscape PASS, user menu PASS; desktop look also approved). Earlier `8ac4bc86448175553722304117a87e619b57d6d0` (AÖ-13 Weekview) remains accepted; minor Thursday irregularity deferred to AÖ-27. The owner additionally approved the AÖ-19 Gate 04C Kitchen Menu Overview Builder-linked row spacing on real iPad (2026-11-12, code commit `93b5f5dd`). Previous Department Portal desktop visual approval remains `1ff5dbef6336feac26943cafce09053ddc13dcd4`. AÖ-19 Kitchen Dish Modal desktop placement and outside-click were owner-accepted 2026-11-12; do not reopen absent reproduced regression. **New distinct 2026-11-13 acceptance:** Admin published weekly menu text layout on actual iPad AÖ-25 owner verified visually fine, without any new AÖ-25 code or specific implicated commit; older 2026-11-08 defect is not currently reproducible.
**Historical owner-reported Git/worktree (`18dd96424ed14d83e0a8491d3d0ba538ddac984f`, 2026-11-13):** local HEAD and remote product HEAD matched; `git status --short` was **empty** after verified guarded AÖ-16 commit/push. The five formerly protected dirty areas have been reconciled: three old Python diffs were reviewed, SHA256-backed-up and restored to tracked HEAD (do not reapply the permissive site-id change in `core/admin_repo.py`); `static/tests/builder_editor_host_styles.test.js` passed 3/3 tests and was committed/pushed as `992d62d50a27a39e9422adff13e3a8de2ec40c7e`; the 12 files of `artifacts/` (five recovery SQLite DBs, seven images) were SHA256-verified and moved into an external archive. Verified backup: `C:\Users\Henrik Jonsson\Yuplan-safe-backups\dirty-recovery-20261113-112829-41c916bc`; separately verified original artifacts archive: `C:\Users\Henrik Jonsson\Yuplan-safe-backups\artifacts-archived-20261113-113856-f390033a`. No `instance/` pilot database, old Fly app or deployment was modified. **Owner subsequently verified local+origin HEAD `06dc8a7a08ea951cb7c9e060b0e1733aefbe224f` with `WORKTREE: CLEAN` before this AÖ-20 ledger update. This new documentation-only GitHub commit will again require a guarded local fast-forward before any new Copilot implementation.** Keep publication recovery tag `checkpoint/ao19-publication-2026-11-11` fixed.

**Status:** Kommun 1.1 remains under local development and final pilot acceptance. The user explicitly decided **finish Kommun 1.1 first, then prepare fresh staging/deploy**. Do **not** redeploy or migrate the old Fly installation as a shortcut. Keep completed UI/Builder/Planera/K25–K27 work frozen absent a reproduced regression.

### 2026-11-18 detailed A–Ö per-ID matrix (owner-accepted evidence; retained under current overlay)

**Meaning of status:** **CLOSED** = implemented, commit verified and owner acceptance recorded for that scoped issue; **CODE FIXED / ACCEPTANCE OPEN** = tested implementation exists but a distinct real-device/security/end-to-end release check remains; **PARTIAL** = listed subgates closed, remainder explicitly named; **OPEN** = still requires diagnosis, decision or correction; **DEFERRED** = not in active Kommun 1.1 scope by owner decision; **CANCELLED** = intentionally rolled back. A successful local test/commit never implies Fly deployment or Kommun pilot GO.

| ID | CURRENT status | Remaining actionable scope / accepted evidence |
| --- | --- | --- |
| **AÖ-01** | **CLOSED · OWNER-ACCEPTED / PUSHED 2026-11-18** | Chosen product solution: optional globally unique ASCII username or existing email login, rather than expanding IDNA-equivalent email lookup. Server-side validation, duplicate rejection, shared rate limiting and retention of nonsecret Admin create-form values on error; owner manually accepted. Product commit `347b958c`; 159 auth/Admin/UI regressions passed. Historical inactive Punycode account untouched; Unicode/Punycode login equivalence and hosted reset delivery are not claimed. |
| **AÖ-02** | **OPEN · P3** | Sidebar encoding `Anv?ndare` → `Användare`; verify actual source/render before copy fix |
| **AÖ-03** | **CLOSED** | Residence create modal now closes; owner accepted `b9a478d7` |
| **AÖ-04** | **OPEN · P2** | In-context `+ Skapa ny kosttyp` from Admin department needs; reuse same site-scoped canonical catalog, design decision first |
| **AÖ-05** | **CLOSED · OWNER-ACCEPTED / PUSHED 2026-11-16** | Equal-emphasis combined special-diet labels accepted by owner in Admin department edit/quick overview and Unit Portal; primary + all modifiers share one visible label, one unchanged group count; no changes to registration, DB, recipe/Planera calculations or tenant/site isolation. Product commit `ae98e0ec49a4a078575d902119896a5e815c3170` (eight scoped files), focused Python 39 passed / 5 skipped, `git diff --check` PASS, terminal local/remote HEAD match and CLEAN. |
| **AÖ-06A/B** | **CLOSED · owner-accepted 2026-11-13** | Admin serving-adaptation picker/registration `884eb7ee` and Page3 real-navigation `761c07e9` fixes already committed/accepted. Owner completed all four consecutive checks using the **same persisted MOS/PASTA adaptation records** in Fantasiköket, Monday 2026-11-09, week 46: (1) Admin department assignments/counts; (2) Kitchen Production Lists additions/counts; (3) Planera Page3 Serveringsanpassningar shows data on direct tab navigation without browser reload; (4) Specialkost/Packlista correct department incl. addon-only/no-normal-menu-choice case. All four passed. **No new product code, seed or migration. CLOSED/OWNER-ACCEPTED**, distinct general final iPad/Safari release checks still pending. Reopen only on new reproducible issue. |
| **AÖ-07** | **CLOSED** | Admin menu status buttons light/dark accepted `828151f6` |
| **AÖ-08A / AÖ-08I** | **CLOSED · security gate accepted 2026-11-13** | Tenant-scoped import/context/library/projection fixes `a1c7a96b`, `89d56460`, `0169570a`, `453c62c5`; 20/20 local reference repairs accepted. Owner observed independent edits for both real test tenants and cross-tenant Weekview denial. Explicit Builder cross-tenant composition GET, text render and library no-leak coverage `ea8c0c2b`: 1 targeted + 5 related tests passed. **AÖ-08B visual modal issue is also owner-accepted as already fixed** (see separate row). Reopen security only on new reproducible evidence; hosted/security release gates remain. |
| **AÖ-08B** | **CLOSED · owner-accepted 2026-11-13** | Builder modal host/outer white-blue frame: product owner explicitly reports this was already fixed several days earlier and rejects further repeat investigation. Close alongside AÖ-26; no new product code. Specific original product-fix SHA not independently established by this acceptance update; `992d62d5` is a host regression **test** commit, not a claimed CSS fix. Reopen only if a new actual regression is reproduced. |
| **AÖ-09** | **OPEN · P2** | Admin Users action-button responsive layout only |
| **AÖ-10** | **OPEN · P2 decision** | User deletion vs deactivate/archive semantics; confirm audit/dependency/last-admin security contract before implementation |
| **AÖ-11** | **OPEN · P2** | Replace user-visible `SCOPE` with clear `Har tillgång till`/site/department language, without changing access rights |
| **AÖ-12** | **CLOSED** | Kitchen portrait iPad shell whitespace/nav accepted `dd60366a` |
| **AÖ-13** | **CLOSED** | Kitchen Weekview sticky/width fixes owner accepted `8ac4bc86`; minor Thursday cosmetics under AÖ-27 |
| **AÖ-14** | **CLOSED** | Kitchen Weekview mark done persistence, iPad, site isolation accepted `9b73721e` |
| **AÖ-15** | **CANCELLED / ROLLED BACK** | No AÖ-15 implementation should be revived; verify intended Kitchen-only navigation at final role/iPad walkthrough |
| **AÖ-16** | **CLOSED · owner-accepted / pushed 2026-11-13** | Shared Admin/Kitchen topbar badge clipping corrected in portrait and landscape, verified on real iPad by owner; user menu and content position PASS; desktop look owner-approved. Two scoped files `18dd9642`; 2 JS + 1 Python focused tests passed. Desktop extremely long-label overflow risk remains statically noted, **not browser-geometry verified**. No deployment or overall Pilot GO. |
| **AÖ-17** | **CLOSED · OWNER-ACCEPTED / PUSHED 2026-11-13** | Kitchen Menu Overview A4 print approved by owner on real iPad after Gate 05. Print-only rowwise Mon–Tue, Wed–Thu, Fri–Sat, Sun, non-table block rows to avoid Safari table row fragmentation; stable desktop presentation and all seven days. Product commit `715509c3edb9ef231e399c6dffe548b0f672b1d6` (four scoped files), targeted JS 2/2 and UI Python 5/5, `git diff --check` passed. Historical Thursday split and subsequent Wednesday/Sunday fragmentation superseded by latest approval. Unusually long menu multipage edge cases remain release E2E, not claimed proven. |
| **AÖ-18** | **OPEN · P3 AUDIT** | Whole-product read-only design consistency sweep after pilot blockers; print icons, modal/header/table styling, both themes/tablet |
| **AÖ-19** | **PARTIAL · P2 decision** | Publication `32696f55`, Kitchen Dish Modal `93b5f5dd`, Admin unpublish warning `be27f98f` CLOSED; broader site-scoped Kitchen `Recept & rätter` library access OPEN. 04D.2/04D.3 automatic notices/visible diffs **DEFERRED by owner** |
| **AÖ-20** | **CLOSED · owner-accepted 2026-11-13** | Code already pushed: published-week selector `7de5bfb4`, iPad year clipping `81371499`. Owner returned to actual iPad UI and confirmed Admin published-week selection and Kock → Planera 2.0 Page1 week selector are now working; original overlap/discoverability/year-display problems no longer reproduce in current use. **No new product code required.** This acceptance does **not** claim an independently documented year-boundary test or comprehensive orientation/browser matrix; verify ISO 2026-W52 → W53 → 2027-W01 with appropriate test data in final release E2E. Reopen only on new reproducible defect. |
| **AÖ-21** | **CLOSED · owner-approved 2026-11-13** | Actual first-visit false stale banner reproduced and fixed in Page2 VM for each current `option_id`: only actual saved `review_id` counts as previous review. Genuine stale validation preserved. Focused 25/25 review service + 15/15 review API green, owner manually verified Page2. Exactly two scoped files committed/pushed `f54b78f4`. Three unrelated pre-existing Page2 UI fixture `projection_error` failures separately recorded as regression-test debt, not concealed. Reopen only on fresh reproducible product defect. |
| **AÖ-22** | **OPEN · P3** | Page3 `Produktionsunderlag` heading typography / possible glyph clipping, visual-only |
| **AÖ-23** | **OPEN · P2** | Overview selectable `Visa` control equivalent to Normalkost (selected dish / all dishes / switch back); keep menu/production truth |
| **AÖ-24** | **CLOSED · owner-accepted / pushed 2026-11-13** | Planera Page3 Normalkost A4 print improved and owner accepted on actual iPad after Gate 01–03: print-only column/wrapping, hidden `#host-mismatch-banner`, compact readable typography, one `Normalkost` title (without printed `Kända mängder`), discrete provisional warning, safe table rows and non-repeated end SUMMA. Four exact files committed/pushed as `cbf6e1f109c31911da085f9512dd32260ecdf7b6`; 8/8 focused JS and 27/27 Page3 UI Python tests passed, `git diff --check` passed. Owner visually approved current Safari print; 20-department multi-page Safari pagination **not** independently proven. Residence-grouping request was explicitly withdrawn for Normalkost (separate Weekview print concept). No engine, DB, tenant/site or screen behavior change claimed. |
| **AÖ-25** | **CLOSED · owner-accepted on actual iPad 2026-11-13** | Previously observed excessively narrow dish-name columns in Admin → Meny → weekly menu on portrait iPad. Owner revisited the current actual Admin iPad UI and confirmed **the problem is gone**. No AÖ-25 implementation needed or made; cause/resolving earlier change is **not attributed** without proof. Keep accepted current appearance locked; reopen only if issue visibly reproduces again. |
| **AÖ-26** | **CLOSED · owner-accepted 2026-11-13** | Admin Builder Dish editor iPad oversized/blue outer frame: owner explicitly confirms it has already been fixed for several days. Treat accepted existing UI as locked, with no new product code or repetition of a recheck. The corresponding historical fix commit has not been independently mapped in this ledger update. Linked AÖ-08B CLOSED. |
| **AÖ-27** | **OPEN · P3 POLISH** | Kitchen Weekview yellow highlight/Thursday visual finish; existing AÖ-13 functional geometry is accepted |
| **AÖ-IPAD-PRINT-01** | **OPEN · P2** | Production Lists print toggles misleading green/grey/yellow after touch; preserve selection semantics |
| **AÖ-PWA-01** | **OPEN · P2** | Installed app wrong role-aware start route; verify manifest + authenticated redirects |
| **AÖ-KITCHEN-ALT2-01** | **OPEN · P3** | Kitchen Overview Alt2 label contrast in light/dark; preserve Alt2 visibility |

**Current gate counts (numbered AÖ-01..27):** 16 fully CLOSED numbered issues (**01, 03, 05, 06, 07, 08, 12, 13, 14, 16, 17, 20, 21, 24, 25, 26**); 1 CANCELLED (15); 1 PARTIAL (19); 9 otherwise OPEN (02, 04, 09, 10, 11, 18, 22, 23, 27). AÖ-08A/AÖ-08I security CLOSED; AÖ-08B UI modal CLOSED alongside AÖ-26 by owner acceptance (the historical product fix SHA not independently identified). Three ancillary tickets OPEN. Scoped owner approvals are not full Kommun pilot or hosted release GO.

### 2026-11-18 sequenced execution queue (authoritative)

**P0 — correctness completed for this sweep:** AÖ-08 tenant isolation CLOSED and AÖ-21 Page2 review state CLOSED. No remaining P0 work is queued without new reproducible evidence.

**P1 — operational and real iPad readiness (one bounded order per defect)**
1. **AÖ-16 CLOSED** (`18dd9642`, real iPad accepted); **AÖ-20 CLOSED** (`7de5bfb4` / `81371499`, current iPad Admin + Kock/Planera behavior owner-accepted 2026-11-13, no new code). ISO year-boundary W52 → W53 → W01 and comprehensive release-device matrix are explicitly **unverified final E2E checks**, not reasons to re-open the accepted UI fix.
2. **AÖ-26 + AÖ-08B CLOSED** by explicit owner acceptance of earlier Builder modal fixes. **AÖ-24 CLOSED** after owner-accepted real-iPad Normalkost print corrections, product commit `cbf6e1f1`, 8 JS + 27 Python focused passes. No residence grouping in Normalkost.
3. **AÖ-17 CLOSED / OWNER-ACCEPTED / PUSHED** `715509c3`: Kitchen Menu Overview weekly A4 print approved on real iPad after five scoped gates. Rowwise paired days on print; print-only non-table block structure addresses Safari fragmentation, preserves screen and Page3 print. No further print work without new live evidence.
4. **AÖ-05 CLOSED / OWNER-ACCEPTED / PUSHED** `ae98e0ec`: combined dietary needs have equal visible emphasis in Admin and Unit Portal with exactly one unchanged group count, owner verified both actual UIs. No further work unless a new defect reproduces.

**P2 — pilot usability and access/product decisions**
5. **AÖ-01 CLOSED / OWNER-ACCEPTED / PUSHED** `347b958c` using email or distinct global ASCII username (no IDNA schema project). **NEXT AÖ-09** Admin Users action-button responsive layout read-only census, then bounded UI fix if still reproduced; **AÖ-11** user-visible `Scope` language; **AÖ-10** user removal/deactivation requires a separate safety/lifecycle decision before implementation. Then **AÖ-04** inline diet type create and **AÖ-23** Overview reversible dish selector. Keep scopes separate.
6. **AÖ-IPAD-PRINT-01**, **AÖ-PWA-01**, AÖ-15 cancelled-feature navigation recheck; **AÖ-19 Kitchen recipe/dish library** decide permissioned read/search scope before implementing, without new automatic menu-change notices.
7. **Report/export and Portal JS fixture debt** plus role/site negative tests and ordinary local auth/reset/mobile acceptance; differentiate fixture failures from confirmed production bugs. These release workstreams are described below; not silently counted as closed AÖ rows.

**P3 — nonblocking copy/visual consistency after functional closure**
8. **AÖ-02, AÖ-22, AÖ-KITCHEN-ALT2-01**; **AÖ-18 read-only design census** and scoped approved fixes including **AÖ-27** Weekview yellow/Thursday finish. Avoid blanket restyling of locked components.

**Final release acceptance (not a current implementation gate):** complete role-specific Admin/Kitchen/Unit Portal E2E, owner real iPad portrait+landscape dark/light and Safari print, account/tenant isolation, report/export, auth locked-out/reset behavior and data safety. Only after **local Kommun 1.1 acceptance**, freeze a release candidate and prepare **fresh current-schema staging** with controlled backup/restore+migrations and HTTPS real Postmark reset. Historical old Fly staging/database must remain untouched. No unconditional Pilot GO.

**Work rule:** one specific Copilot order → report → code/test review → user visual acceptance → exact guarded PowerShell commit/push → update this ledger. Only a new observed defect may reopen an owner-accepted checkpoint.

### Latest checkpoint — 2026-11-18 (overrides older task-order notes below)

**2026-11-18 AÖ-01 owner acceptance / pushed product checkpoint:** The original IDN/Punycode login failure was reproduced in an isolated database. Product owner explicitly selected a smaller solution: allow globally unique, case-insensitive ASCII usernames alongside existing email login, retaining international email addresses as contact addresses. Gate 03/03B/03C added login lookup and shared account throttle, optional username in Admin Users, validation and preserved nonsecret form values on duplicate/invalid input. A duplicate `Pilotbarbro` was rejected against saved `pilotbarbro`; owner subsequently confirmed all manual acceptance checks working. No migration, historical account change, auth reset refactor, or hosted deployment. Final focused/broad Copilot regressions reported **159 passed / 0 failed**; owner guarded commit/push and clean worktree `347b958c1cadc80551fe0e46ebb5828e59c8f9be`, and GitHub commit and branch tip were independently verified. Exactly eight changed files: `core/admin_user_repo.py`, `core/auth.py`, `core/ui_blueprint.py`, `templates/login.html`, `templates/ui/unified_admin_users_form.html`, `tests/auth/test_login_form_and_json.py`, `tests/ui/test_login_ui.py`, `tests/ui/test_unified_admin_users_phase3.py`. **AÖ-01 CLOSED / OWNER-ACCEPTED / PUSHED; NEXT AÖ-09**. The 2026-11-08 historical inactive IDN/Punycode account was not activated or deleted; international email login normalization and password-reset IDNA equivalence remain explicitly unsupported/unenhanced. This documentation-only checkpoint requires a guarded local fast-forward before new Copilot edits.

### Prior checkpoint — 2026-11-16 (historical)

**2026-11-16 AÖ-05 owner acceptance and pushed product checkpoint:** Owner manually confirmed that the corrected combined dietary labels now look good in both Admin → Avdelning → Kostbehov and Avdelningsportalen after Gate 02. Portal renders a unified `display_label` for all needs at equal visual weight, with a single original group `quantity`; Admin edit, quick overview and visible variation names use the same combined label, preserving primary/modifier IDs and actual groups. Scope: exactly eight presentation/test files. `python -m pytest -q tests/portal/test_department_portal_home.py tests/ui/test_admin_departments_edit_specialkost.py` 39 passed, 5 skipped; `git diff --check` PASS. Owner's guarded PowerShell commit/push verified local and remote SHA **`ae98e0ec49a4a078575d902119896a5e815c3170`**, CLEAN. **CLOSED / OWNER-ACCEPTED / PUSHED; NEXT AÖ-01 read-only IDN login diagnosis.** This tracker-only GitHub commit follows product code and requires a guarded local fast-forward before further Copilot edits.

**2026-11-13 AÖ-17 owner acceptance and pushed checkpoint:** Owner tested the actual current Kitchen Menu Overview A4 print on iPad Safari after Gate 05 and expressly approved it ("ja nu ser d bra ut"). Earlier real-iPad PDF failures were observed at previous gates; latest acceptance supersedes them, not a claim of independent browser automation. Desktop had already been accepted. Final print-only rowwise Monday/Tuesday, Wednesday/Thursday, Friday/Saturday, Sunday uses non-table block print rows; screen and other print views retained. Targeted JS 2/2 and UI Python 5/5 PASS, diff check PASS; exactly four files committed/pushed at **`715509c3edb9ef231e399c6dffe548b0f672b1d6`**, terminal local and remote matched, clean tree. **CLOSED / OWNER-ACCEPTED / PUSHED; NEXT AÖ-05**. This docs-only GitHub commit requires guarded local fast-forward before Copilot changes.

**2026-11-13 AÖ-24 owner acceptance and pushed product checkpoint:** Product owner reviewed the updated Normalkost output on an actual iPad and approved the print design after three scoped gates. Product commit `cbf6e1f109c31911da085f9512dd32260ecdf7b6` was verified as one commit after `ce6fb582`, affecting exactly `static/css/planera_product2_page3.css`, `static/css/yuplan_print.css`, `templates/ui/kitchen_product_planera_page3.html` and `static/tests/planera_product2_page3_print_layout.test.js`. Focused JS 8/8, Page3 UI Python 27/27 and diff check PASS by owner/Copilot logs. Dev host mismatch banner hidden in print, right column fits better, headings/rows more readable, provisional status retained, single end SUMMA, no repeated `Kända mängder` title. Owner withdrew grouping by residence for Normalkost and clarified this as a separate Weekview print concept. Full many-department Safari multi-page pagination is not claimed verified. **CLOSED / OWNER-ACCEPTED / PUSHED; next AÖ-17**. This documentation-only GitHub commit follows the product push; guarded local fast-forward required if owner local branch is still at `cbf6e1f1`.

**2026-11-13 AÖ-08B + AÖ-26 owner acceptance / tracker closure:** Product owner expressly confirmed the Admin Builder Dish Modal blue/white outer host-frame problem had already been fixed for several days and asked not to repeat any further check or code work. Marked both IDs **CLOSED / OWNER-ACCEPTED** with no new product changes. The exact historical CSS fix commit is not independently identified in this ledger update; the existing Builder host test commit `992d62d5` should not be mistaken for a verified product fix. This replaces prior OPEN/next-gate descriptions. **AÖ-24 and AÖ-17 subsequently CLOSED after owner-accepted print fixes**; next AÖ-05. Earlier owner-reported local and origin checkpoint was clean at `e7559b8f83d8ffcd6a0f63d52b599cb4d7b03c76`; after this documentation-only GitHub update, local guarded fast-forward is required before further coding.

**2026-11-13 AÖ-20 owner acceptance / tracker closure:** After the prior `7de5bfb4` published-week selection and `81371499` year-clipping code fixes, the owner revisited the actual iPad UI and confirmed working Admin published-week selection and Kock → Planera 2.0 Page1 week selection. The original week-controls/Monday overlap and clipped year are not reported in current use. **CLOSED / OWNER-ACCEPTED; no new product code and no claim of a new test run.** Full ISO 2026-W52 → W53 → 2027-W01 navigation and orientation/browser/theme release matrix have not been independently evidenced and remain final release E2E checks. AÖ-24 was subsequently closed after owner-accepted print improvements; AÖ-26/AÖ-08B were also owner-accepted as already fixed.

**2026-11-13 AÖ-16 owner acceptance and pushed checkpoint:** Real iPad checks PASSED for both Admin and Kitchen in portrait/landscape after AÖ-16B; user menu, visible header badges and content position PASSED. Owner also liked improved desktop placement. Final read-only AÖ-16C confirmed the CSS cascade but **could not browser-verify extremely long desktop labels**; treated as nonblocking residual risk, not falsely claimed tested. JS 2/2, Python 1/1, diff checks PASS; exact 2 files committed/pushed at `18dd96424ed14d83e0a8491d3d0ba538ddac984f`; local+remote match and worktree clean. Next AÖ-20 owner real-iPad acceptance; no further shell edits without reproduced regression.

**2026-11-13 Git dirty-path recovery CLOSED:** Three previously uncommitted Python diffs were backed up and restored, standalone Builder modal-host test saved as pushed commit `992d62d5`, and 12 recovery artifacts were verified via SHA256 and separately archived outside the repo; final Git clean checkpoint reached before AÖ-16. Do not claim these legacy dirty paths remain active.

**2026-11-13 AÖ-25 owner acceptance:** Actual current Admin → Meny weekly view inspected on real iPad; owner reported previous portrait menu title-column squeeze has disappeared, so AÖ-25 **CLOSED**. No new CSS or Copilot order, no confirmed identification of the earlier fix.


**2026-11-13 AÖ-06 final owner acceptance:** using the same existing Fantasiköket W46/2026-11-09 MOS/PASTA data, Admin department registrations → Kitchen Produktionslistor → Planera Page3 Serveringsanpassningar on direct tab navigation → Specialkost/Packlista (including no normal menu choice) all passed in real local UI. AÖ-06A/B **CLOSED**; previous AÖ-06G and AÖ-06H.3 code commits unchanged. No overall hosted/iPad pilot release GO.


- **AÖ-19 Gate 04A/04B – CLOSED / OWNER-ACCEPTED / CHECKPOINTED (2026-11-11).** Kök → Menyöversikt now hides un-published/draft menus (both imported and manually created), enforces tenant/site access, and displays only published menu content. Existing Builder `composition_id` links open the canonical Admin Dish Modal from the published Kitchen menu without cloning dishes. AÖ-19 Gate 04B removed the reproduced `publication_revision_conflict` blocker by creating an internal Builder source version only on an actual changed menu publication, preserving the same menu, Builder menu, row and composition identities and immutable historical snapshots; retries after partial Builder-side bump are idempotent. Fantasiköket week 46 successfully published in real local UI and owner explicitly locked that behavior. Five focused suites passed 17+10+7+24+5 = **63/63**, without exclusions; `git diff --check` passed. Exactly nine accepted files committed/pushed as `32696f55`, annotated remote tag `checkpoint/ao19-publication-2026-11-11`; five protected unrelated dirty paths preserved. **No Fly deployment and no full Kommun pilot GO.** Week 45 was not separately re-published under the new code; do not claim that owner verification.
- **AÖ-19 Gate 04C – CLOSED / OWNER-ACCEPTED / PUSHED (2026-11-12).** In Kök → Menyöversikt, the canonical Builder-linked Dish Modal is visually centered and wholly visible on real desktop, and one click outside closes it on both sides. The owner previously verified internal modal tabs/close operation and real iPad Safari compact row spacing matching nonlinked dishes. The defective layout was diagnosed with browser geometry: at 1440px viewport the host had been only 1240px wide, card center displaced -100px and full-width iframe intercepted backdrop clicks; the resulting Kitchen-only CSS fixes restore viewport-wide fixed modal host and cap the centered panel at 1120px, with iframe constrained to panel. `clip-path`/pointer-event workaround was removed. Exactly `static/css/kitchen_menu_overview.css`, `templates/ui/kitchen_menu_overview.html`, `static/tests/kitchen_menu_overview_modal.test.js` committed/pushed as `93b5f5dd9dc6b3f28f270b6cce352610c79e3ddd`, 5/5 focused Python + 7/7 JS tests passed, diff check clean, five protected dirty paths unchanged. The shared App Shell / Builder modal implementation, publication code, and tenant/site scoping were not changed. **No Fly deployment; no full Kommun pilot GO.**
- **AÖ-19 Gate 04D.1 – CLOSED / OWNER-ACCEPTED / PUSHED (2026-11-12).** The published Admin menu now shows a compact status-card note during edit explaining changes require return to draft and re-publication. Clicking `Återgå till utkast` opens a compact accessible native confirmation dialog explaining temporary unpublishing and existing menu-choice/production records; confirmed unpublish requires server-validated `_confirm_unpublish=1` as well as existing CSRF, ETag, role and tenant/site checks. Owner visually approved live Admin note and dialog. Cancel, native cancel/Escape and single submit behavior are regression-tested; 15/15 targeted Python and 6/6 targeted JS tests green; JS syntax and `git diff --check` green. Exactly six scoped files committed and pushed as `be27f98f6d56f255e425f62366c8dc0669469267`; five protected dirty paths preserved. Publication core/Builder/Planera remain unchanged. No Fly deployment, no final Kommun pilot GO. **Next bounded scope: AÖ-07 Admin Menu Import status-card button colors and illegible hover contrast** (already in ledger), before 04D.2 and 04D.3 publication revision diff and dated notices. Do not reopen accepted dialog design.
- **AÖ-07 – CLOSED / OWNER-ACCEPTED / PUSHED (2026-11-12).** Admin → Meny weekly status-card buttons (`Redigera meny`, `Publicera`, `Återgå till utkast`, `Klar`, `Tillbaka`) have localized light/dark button hierarchy, readable hover/focus/disabled behavior and a toned-down warning action; product owner verified desktop light and dark screenshots. Light/dark warning and secondary text contrast were measured in final focused analysis at 7.85:1–13.44:1 for normal/hover states. Scoped change committed/pushed as `828151f671eda31e1e1d938fe5fa2b7304918833`, three files, 9/9 JS + 15/15 Python regression tests green. Existing AÖ-19 Gate 04D.1 dialog/notice and all shared App Shell rules remain untouched. iPad-specific full pilot verification is not claimed. No deployment or pilot GO.
- **AÖ-19 product contract / follow-ups (OWNER DECISIONS 2026-11-11 and 2026-11-12):** Admin may change and re-publish an existing weekly menu without creating a new menu or library composition ID. Implemented and locked Gate 04D.1: explicit warning/confirmation before `Återgå till utkast` and explanatory status-card information when editing an already published menu. **Owner decision 2026-11-12 supersedes previous 04D.2/04D.3 automatic notice scope:** DO NOT build automatic changed-menu notifications, mandatory day/meal change banners, or a new user-visible revision diff for Kök/Portal/Planera at this time. Admin is responsible for deciding whether a menu change needs communication; the existing Admin→Kitchen dashboard-notice channel can be used when needed, and similar Admin→Department Portal communication is a future capability, not assumed implemented. Do not add a new optional send-toggle or notification workflow now. Existing immutable publication revision/snapshot history, Builder identities, tenant/site isolation, ETag safety, and technical `stale`/`needs_review` correctness checks in Planera/Portal remain mandatory; do not suppress these safeguards merely to avoid informational notices. No automatic rewriting of menu choices, review state, production plans or completed flags. Revisit manual communication integration or user-visible revision history only after a new explicit product-owner decision. Broader Kitchen `Recept & rätter` site-scoped searchable library and explicit read/edit permissions remain a separate OPEN AÖ-19 product gate. Gate 04C Kitchen modal presentation stays LOCKED (`93b5f5dd`).
- **AÖ-20 — CLOSED / OWNER-ACCEPTED 2026-11-13; no new code.** The implemented published-week selector is `7de5bfb4` and iPad year-display fix is `8137149931977f3d5f9cb96325d716fd0c60fb0d`. Owner subsequently checked the real iPad Admin weekly menu and Kock → Planera 2.0 Page1 selector and confirmed the previously reported problem no longer reproduces. Preserve as accepted. **Not independently verified:** ISO rollover 2026-W52 → 2026-W53 → 2027-W01, and a full orientation/browser/theme test matrix; keep those as final release E2E checks, not fabricated PASS results.
- **Test-data policy clarified 2026-11-11:** No current menus are used by live paying customers. Development/test menus may be recreated where necessary to correct architecture, but Builder library/composition and recipe information should not be deleted casually, tenant isolation must remain strict, and tests still use isolated disposable databases. No claim of real hosted production acceptance.
- **AÖ-14 CLOSED — owner-accepted on real iPad Safari, committed and pushed.** Kök → Veckovy canonical K3 completion for specialkost and requirement groups is available to authorized staff without manual `ff.weekview.enabled` activation. Positive-count eligible cells can be marked/unmarked, saving feedback is shown, and green completion survives reload; zero-count cohorts remain disabled. Tenant/site/department checks fail closed on mismatch or DB error. AÖ-IPAD-03B–03J changes saved at `9b73721ebab6d29ef84d7c4edbac86649c24c66c`; 36/36 focused Python tests passed in each of two file orders, 19 focused JS tests passed, syntax/diff checks passed. This does **not** establish a whole-app or production release GO.
- **AÖ-12 CLOSED — real iPad shell/navigation accepted**, earlier checkpoint `dd60366a8269e86d8383589fa369f9c9420ebd03` (AÖ-IPAD-02/02B); portrait/landscape navigation geometry and usable content position accepted. Keep any later distinct topbar clipping under AÖ-16.
- **AÖ-03A CLOSED** (`b9a478d7`). **AÖ-06A/B CLOSED / OWNER-ACCEPTED 2026-11-13:** previous Admin recurring serveringsanpassningar picker fix `884eb7ee` and Page3 no-refresh navigation fix `761c07e9` locked. Owner verified *identical saved MOS/PASTA records* from Fantasiköket Admin → Kitchen Produktionslistor → Planera Page3 Serveringsanpassningar → Specialkost/Packlista, incl. department without normal menu selection; all four pass. No new code or test-data repair. General real-iPad browser/print final pilot walkthrough remains release-wide, not a reopening of AÖ-06.
- **Remaining A–Ö issues are not silently closed:** AÖ-25 **CLOSED/OWNER-ACCEPTED** after fresh real-iPad Admin menu check (no code); AÖ-06A/B **CLOSED/OWNER-ACCEPTED** after full persisted-data chain check; AÖ-21 **CLOSED/OWNER-ACCEPTED/PUSHED** `f54b78f4`; AÖ-08A/08I tenant security CLOSED `ea8c0c2b`, AÖ-08B visual modal CLOSED with AÖ-26 by owner confirmation 2026-11-13; no further modal work without new evidence. AÖ-24 Normalkost print CLOSED/OWNER-ACCEPTED/PUSHED `cbf6e1f1`; not a pending print gate. AÖ-07, AÖ-03, AÖ-12, AÖ-13, AÖ-14 CLOSED. AÖ-19 publication/modal/unpublish CLOSED; Kitchen `Recept & rätter` permissioned library OPEN. Automated notices/visible diffs OWNER-DEFERRED. AÖ-20 week selector CLOSED/OWNER-ACCEPTED after the fresh 2026-11-13 real-iPad recheck (year-boundary release E2E still unverified). AÖ-16 shared topbar badge clipping CLOSED/OWNER-ACCEPTED/PUSHED `18dd9642` after Admin + Kitchen portrait/landscape real-iPad verification. AÖ-15 CANCELLED. No final Kommun pilot GO.
- **Product-owner working direction:** focus on completing *full Yuplan* for sale/pilot; all already approved core functionality should be available to authorized users. Module-by-module sales, licensing tiers and further feature-flag commercial design are **not active A–Ö work**. Preserve safety/role/site protections and legacy gates outside K3 rather than globally unlocking unfinished code.
- **Operational order from here (2026-11-13, after AÖ-20 owner acceptance):** AÖ-16, AÖ-20 and AÖ-25 are CLOSED, with no extra AÖ-20/AÖ-25 product code. Five historic dirty paths were safely reconciled/archived. **AÖ-26/AÖ-08B CLOSED by explicit owner acceptance of pre-existing fix; AÖ-24 print CLOSED / OWNER-ACCEPTED / PUSHED `cbf6e1f1`; AÖ-17 Kitchen Menu Overview print CLOSED / OWNER-ACCEPTED / PUSHED `715509c3`; AÖ-05 combined dietary labels CLOSED / OWNER-ACCEPTED / PUSHED `ae98e0ec`. NEXT: AÖ-01 read-only IDN login diagnosis**. Year-boundary ISO W52 → W53 → W01 remains a transparent final release E2E item, not an unverified PASS. Keep accepted behavior frozen. After this GitHub documentation-only commit, guarded fast-forward local clean HEAD `06dc8a7a` to the new remote before Copilot code work. No seed, migrations, broad Builder refactor, or old Fly deployment.

- **AÖ-13 CLOSED / PUSHED (2026-11-11), owner accepted with known visual limitation.** On real iPad Safari, the owner confirmed the first column now stays sticky and meal/day columns are more compact; the owner chose to lock this as adequate for pilot and move on. Minor uneven Thursday/day geometry remains visible in landscape, explicitly accepted as a deferred visual defect under AÖ-27, not silently described as fixed. Focused AÖ-13C regression results reported: 24/24 JS, 30/30 Python and `git diff --check` passed; staged diff contained exactly 3 approved files (227 insertions/95 deletions) and owner verified push at `8ac4bc86`. This is not a full browser/release GO. Preserve the working responsive scroll, column behavior and AÖ-14 completion during the later redesign.
- **AÖ-27 OPEN — Kitchen Weekview visual polish (owner feedback 2026-11-11).** Real iPad landscape screenshot of Kök → Veckovy, week 46, shows large saturated yellow/ochre highlighted lunch cells and a dense, utilitarian grid that the owner does not consider Yuplan-finished. Separate aesthetic/visual-hierarchy review from AÖ-13's current geometry/sticky fixes; retain functional Alt2 distinction and completion indicators. Track as focused design scope linked to AÖ-18; no code change until AÖ-13 is accepted and owner has approved a visual direction. See AÖ-27 row below.

### Product-owner-accepted / CLOSED scope

- **Builder Gates 19–21E (2026-11-05/06):** import/unresolved/manual Create Dish follows one atomic reviewed-create route; per-component reuse/new mode; category saved with Skapa rätt; common component parser supports spaced `&` and connective separators without splitting `R&B`. Checkpoints `f1195d17`, `1c926d90`, `f46da3c2`, `a75f754c`. Builder functional enhancement phase is frozen.
- **Planera 2.0:** Page1 → Page2 review → Page3 production underlag, normalkost/specialkost, primary/modifier, production completion and Weekview projections have been implemented and previously accepted for day-to-day pilot use. Do **not** reopen due to the September finishline's historical ACTIVE label.
- **K25–K27 (2026-10-31):** Kitchen Weekview compact serving-addon notes (`bbea233b`); Production Lists grouped by family with department quantity/comment and per-family/full printing (`b09c3d7a`); Page3 department packing list including standing addons and addon-only departments with print (`0d803262`). The 2026-11-06 code branch includes these commits. Packing/serving functionality is accepted, not an invitation to build a new engine.
- **Admin registered serving adaptations:** family-scoped reuse, no auto-select, Create New and duplicate warnings accepted (`ad96abd4`).
- **Kommun UI Gate 01 — Builder editor outer frame (2026-11-06): CLOSED.** The white/grey rectangular iframe background in Admin Menu Import was removed using a Kommun-host-only `color-scheme: normal` rule; product owner confirmed it disappeared after a hard reload. Shared Builder editor and Offshore untouched. Product checkpoint `3bfc98921959f29821da777e4e9375616594e84e`; 7/7 focused JS/host tests passed.
- **Kommun UI Gates 02B–02F.2 — Department Portal menu-choice visual recovery (2026-11-06): CLOSED for product-owner-approved desktop design in dark and light themes.** Repaired nested hidden week scrolling, theme token use, consistent 50/50 weekday lunch columns, separate full-width Dessert/Kvällsmat row, subtle day-card separation, and weekend Alt 1 + noninteractive single-option note in the Alt 2 position. Owner inspected the live authenticated page and approved the final visual result. Product checkpoint `1ff5dbef6336feac26943cafce09053ddc13dcd4`; 7/7 CSS layout/scroll/theme tests and 30/30 focused Portal Python tests passed. **iPad/mobile live visual walkthrough and actual choice/submit interaction remain release-acceptance checks**, not claimed closed here.
- **Account/site and role isolation foundations** previously implemented. Existing forced first-login change and `auth_version` revocation are not to be discarded when hardening login.

### Security and Postmark checkpoints (verified through 2026-11-07)

- **Login/deployed-mode guard:** the earlier Gate 03C.1 bypass precedence issue was corrected in code (`auth_bypass_allowed()` checks `FLY_APP_NAME` and deployed environments before the testing allowance). This is **code/test accepted, not a claim of deployed verification**.
- **Persistent login throttling:** implemented with database-backed account/IP throttles and reservation semantics (migrations 0048–0049). Preserve login/API behavior and `auth_version` revocation; actual hosted behavior not yet verified.
- **Self-service password reset:** implemented in code with hashed expiring single-use reset tokens, request-throttle storage (migration `0050_add_password_reset_storage`), anti-enumeration response and failure handling, and SMTP mailer adapter. Existing mailer uses authenticated TLS and requires an HTTPS reset URL. **Owner-confirmed real Postmark SMTP inbox delivery** and isolated browser reset lifecycle passed; **hosted/app-configured real email reset is still pending release acceptance**.
- **Password policy:** central validation `core/password_policy.py`, 15–1024 characters, Unicode/spaces supported, small explicit denylist with optional configured extension; legacy password logins must remain valid. Security code checkpoint `6caa9d1a51a24f7b5b8da6ad249ae227660f1903`.
- **Gate 03G.1 — CLOSED (2026-11-07):** `PASSWORD_RESET_PUBLIC_BASE_URL` now flows from environment through `Config.from_env()` into Flask config while explicit test overrides are preserved. Four changed files (`core/config.py`, `core/app_factory.py`, `tests/auth/test_password_reset.py`, `tests/auth/test_password_reset_mailer.py`); **79/79 auth tests green**, focused Ruff and `git diff --check` green; GitHub push confirmed at `7286fb64`.
- **Postmark account and DNS:** user verified Postmark approval and `yuplan.se` domain. Postmark DKIM and Return-Path verified; one.com SPF enabled and custom DMARC TXT `v=DMARC1; p=none` created. User generated and saved a **separate** Postmark SMTP Access Key / Secret Key outside Git/ChatGPT. Do **not** log, paste into Copilot, check in, or request their values. Proposed sender `no-reply@yuplan.se`; intended controlled recipient `info@yuplan.se`. Real SMTP delivery **confirmed by owner on 2026-11-07**; no hosted app reset claimed.
- **Gate 03G.2 — POSTMARK DEVELOPMENT CLOSED / HOSTED ACCEPTANCE PENDING (2026-11-07):** Copilot inspected the existing SMTP adapter without changing production code and added exactly one 30-minute token-expiry regression to `tests/auth/test_password_reset.py`. **66/66** focused reset/login/site-binding/revocation tests passed; Ruff and `git diff --check` passed on the local code checkpoint `7286fb64`. Owner ran a Python STARTTLS SMTP smoke on port 587 using the dedicated SMTP Access Key/Secret Key; console showed **SMTP login OK** and **Postmark accepted message** from `no-reply@yuplan.se` to `info@yuplan.se`; owner independently **confirmed receipt** in inbox. This was a standalone delivery smoke, **not** a valid reset token or complete hosted password-reset E2E. **Expiry regression was safely committed/pushed as `c53b945288fb832b4b388a39ee076e2f1dc600e4`**; hosted mailer and actual reset still require a fresh release candidate. The originally attempted .NET SMTP send got `4.7.1 Relay access denied`; the subsequent direct Python Postmark SMTP call succeeded, so no app-adapter redesign is justified. The owner also exposed an existing Postmark Server API Token in a screenshot; rotation/revocation needs owner confirmation before treating all account secrets as secure.

- **Gate 03H.1 — local browser acceptance (2026-11-07):** isolated browser test verified correct login/site/role, account/IP throttling, lockout and unlock, forgot/reset token lifecycle, invalidation of prior sessions/JWTs and the existing rotating globe. Found one real UX defect: HTML login errors rendered raw API JSON. No product files changed in the gate.
- **Gates 03H.2 / 03H.2B — HTML LOGIN UX CODE CLOSED / OWNER ACCEPTANCE PENDING (2026-11-07):** `core/auth.py` renders the existing Yuplan login page with generic Swedish 401/429 messages while preserving API JSON/status, Retry-After, CSRF, security controls and globe. Browser verified 401 → 401 → 429, Retry-After, success after unlock, destination and 390px viewport without horizontal overflow. **82/82 auth tests**, focused Ruff and diff checks green. Precisely two product/test files committed and pushed as `a8fed697826623513243036faa3efeab7a061b06`. No deployment or real owner login/reset walkthrough claimed. Five protected unrelated dirty paths remain unchanged.

- **Gate 03H.3/03H.4 — LOCAL AUTH RUNTIME RECOVERED (2026-11-07):** During first owner login acceptance on the ordinary local Yuplan at `127.0.0.1:5000`, HTML login returned `503 {"error":"service unavailable"}`. Read-only investigation proved the local database `instance/yuplan_mvp.db` remained at Alembic **0047** (missing auth throttling and reset tables), and local `.env` lacked `AUTH_RATE_LIMIT_HMAC_SECRET`. Following owner-authorized controlled recovery, Copilot stopped the server, verified the original SQLite integrity, created and verified a pre-migration SQLite backup outside Git, rehearsed migrations **0048→0050** on a copy, then migrated **only the local database** to **0050**. All four new tables exist; SQLite integrity `ok`; key entity counts remained tenants 1, sites 1, users 4, menus 13, departments 2, production_lists 0. A new dedicated strong rate-limit HMAC secret was placed in gitignored `.env` without displaying its value. Real local browser then returned **HTTP 401 `text/html` and Swedish friendly error** for one controlled nonexistent account attempt, not 503. No product-code, test-code, protected dirty files, Fly or Git changes; ordinary local server was stopped after the proof. **Owner subsequently confirmed successful local login with the real account and friendly HTML feedback for an incorrect password**. Repeated-failure lockout and full real-mail reset remain unaccepted by owner; standalone SMTP delivery and isolated reset browser acceptance are not full local Postmark integration. Backup currently under Windows TEMP (`yuplan-mvp-20261107-112122-backup.db`); preserve durable copy before relying on it.

- **Gates 03H.5/03H.5B — LOCAL RECOVERY NAVIGATION CODE CLOSED (2026-11-07):** Owner observed that HTML Forgot Password stayed on the same form with no back link, and the owner had not received a real reset mail. Copilot changed only `core/auth.py`, `templates/auth_forgot.html`, `tests/auth/test_password_reset.py` plus isolated `test_missing_hmac_secret_returns_503_without_session` in `tests/auth/test_login_persistent_rate_limit.py` using `monkeypatch.setenv(..., "")` before app creation. Known/unknown user HTML POST both return **303 → `/auth/login`** with identical neutral Swedish flash; back link works. JSON/API POST remains **202 and unchanged**. Isolated browser fake-mailer acceptance passed; full auth tests **83 passed**, Ruff and diff checks passed. Exact four approved files safely committed/pushed at **`97c9cd6721f7a17b27de0e0f5650babf2cc81e12`**, five protected dirty paths preserved. **Owner has not yet confirmed the revised redirect visually after this commit.** Real recovery mail is **not configured/verified from ordinary local app** (Postmark direct standalone smoke succeeded separately); never infer message was sent from neutral status feedback. Next: read-only local mailer config census (presence only), then controlled owner-authorized integration test with an isolated test account; no token or secret disclosure. Password reset deployed acceptance stays pending.

- **Gate 03H.7 — CODE CLOSED (2026-11-07):** aligned `SMTPPasswordResetMailer` HTTP-loopback allowance with existing explicit-local-only `reset_url_allows_insecure` policy. External HTTP, staged/pilot/prod/Fly HTTP remain denied; HTTPS unchanged. 21 focused mailer tests + **88 auth tests** passed, Ruff/diff green. Owner safely committed/pushed two approved files at **`29c4da20c77b6ff573cdb0fc6fa0053b519e20d1`**; unrelated dirty paths protected. No real email sent or runtime SMTP config added.
- **Gate 03H.8 — LOCAL RESET BROWSER CORE PASS / TWO VERIFICATION LIMITS (2026-11-07):** Copilot ran a temporary 5057 local browser harness against disposable SQLite with one active unit_portal account and fake-mailer. **12 of 13 specified checks passed**: login UI, forgot/back link, HTML 303 + neutral flash, internal reset-link capture, valid reset, successful login with new password in portal role, old password rejection, reset replay HTTP 400, original globe/UI unchanged. **No real email, existing account, persistent DB or code touched; temporary harness cleaned.** Old authenticated session check was **UNVERIFIED in browser** because the browser sandbox could not support separate cookies/contexts; mobile 390px viewport also not completed. Existing automated `tests/auth/test_password_reset.py::test_reset_invalidates_existing_login_tokens_and_accepts_only_new_password` uses separate Flask test clients and asserts old session HTTP 401, old JWT/refresh rejection, new credentials; this was included in the 88 passed auth suite at 03H.7. Therefore do not open a new engineering gate merely to work around sandbox cookie APIs. Keep **real app SMTP/HTTPS hosted reset** and owner mobile visual checks as release acceptance; **no Pilot GO** from this gate alone.

### Fly inventory — historical environment, explicitly NOT the pilot-deploy target

The user confirms the existing Fly deployments were not used for active development for approximately **9–10 months**. Read-only inventory on 2026-11-07 found:
- Fly app `yuplan-unified-staging`, hostname `https://yuplan-unified-staging.fly.dev`, machine `68320edf664468`, release v141, health 1/1.
- Attached `yuplan_data` volume (~3 GB), runtime `DATABASE_URL` scheme SQLite, DB path `/data/yuplan_pilot.db`, `YUPLAN_ENABLE_STARTUP_MUTATIONS=0`.
- On-server Alembic **database current = `0020_add_diet_family_to_dietary_types`**; **deployed source head = `0023_scope_service_addons_by_site`**. Database approximately 1.2 MB with 48 tables; volume about 2.8 GB free. This is **not** the local migration HEAD `0050_add_password_reset_storage`.
- No backup, data migration, Fly secret setting, deployment or restart was performed during this inventory. No readiness/restore proof exists for the old DB.
- An older `yuplan-unified-staging-icy-wave-9332` environment and paused PostgreSQL apps also appear in Fly. Do not confuse old Postgres runbooks with the inspected SQLite app.
- **Decision:** leave all old Fly apps/data untouched. Do not advance the 0020 database to 0050 on the old machine. Once Kommun 1.1 reaches product-owner pilot acceptance, design a fresh, current-schema staging/release with proper backup, isolated migrations, runtime security and Postmark secrets verification.

### Historical 2026-11-08 proposed sequence — superseded by latest 2026-11-10 checkpoint

1. **NOW: FIRST A–Ö OWNER WALKTHROUGH CLOSED 2026-11-08; start read-only security/data triage before any fixes.** Local login+HTML wrong password were owner verified; local reset browser core passed 12/13 with a temporary fake-mailer, and 88 auth tests including separate-client session revocation passed. Do not reopen a broad auth rewrite. Owner mobile browser checks (including reset UI), real SMTP-hosted HTTPS end-to-end delivery and deployed cookie/throttle acceptance remain on the release checklist. No local SMTP secrets or real mail needed for current A–Ö. Confirm temporary test data/backup strategy before customer creation; log only reproduced defects and their severity. Preserve approved UI/Builder/Planera/K25–K27 and login globe. No Fly work until local Kommun acceptance.
2. **Then resume remaining Kommun 1.1 release work** using product-owner-approved flows and actual defect evidence, not stale historical gate lists: clean-customer full walkthrough, admin/department/kitchen/portal/menu/Planera completion and persistence, report/export parity, negative tenant/site/RBAC, mobile/iPad acceptance, obsolete Portal JS fixture audit vs real bugs, HTML login feedback/CSRF and actual login UX with spinning globe preserved. A remaining item is closed **only** with reviewed evidence; do not reopen accepted work without reproduction.
3. **When Kommun 1.1 is actually accepted:** freeze/tag candidate; determine fresh staging/DB deployment strategy, safely rehearse and verify current migrations with backup/restore; stage Postmark secrets (separate SMTP Access Key = username, Secret Key = password; HMAC secrets separately), use actual app HTTPS reset URL, and perform hosted real reset/session invalidation/negative tests. New staging is a release-acceptance activity, **not** today's work.
4. **After Kommun 1.1 Pilot GO:** resume Offshore 1.0 then the cross-product Yuplan 1.0 release gate. See [Roadmap](roadmap.md).

**Important:** `docs/security/YUPLAN_SECURITY_BASELINE.md` tracks security controls, evidence and remaining risks; this file remains the sole operational next-gate authority. Neither doc-only updates nor passing auth tests imply a real deploy or pilot GO.

**Locked visual UI rule:** Product-owner accepted Kommun Builder modal and Department Portal Menyval must not be restructured or restyled by unrelated features. Any required change to an accepted screen needs explicit scoped approval, actual before/after browser evidence in both themes and relevant iPad viewport, plus focused regression tests. The existing CSS/DOM tests are useful but do not replace visual review. Historic approved screenshot baselines are not currently versioned in the repository; capture reviewed visual baselines during final pilot acceptance rather than falsely claiming pixel-snapshot coverage.

**Security baseline owner:** `docs/security/YUPLAN_SECURITY_BASELINE.md` records security controls, evidence and open security risks. This is not a separate product status ledger; the present Live Acceptance document remains the single operational gate authority.

- **Login 1.1 / Gate 04A — OWNER VISUAL APPROVED (2026-11-08):** owner reviewed the actual local dark-theme desktop screenshot and explicitly said **lock the design**. Existing globe/SVG/animation preserved; Yuplan wordmark/tagline, consistent fields, teal submit CTA and CSP-safe password visibility control added. Copilot technical report: 98 auth + login UI tests passed, focused 22 green, JS syntax and diff checks green, browser light/dark desktop, 390px mobile and 768px tablet without overflow; login 401 and reset 303 retained. Exactly four approved login files (`templates/login.html`, `static/css/login.css`, `static/js/login.js`, `tests/ui/test_login_ui.py`) were **committed and pushed** as `45c961936c762881150ee85db4849c0d3b32e899`; owner confirmed remote tag `gz-login-1-1-approved-2026-11-08` was pushed. Preserve Ground Zero tag `gz-login-ui-before-polish-2026-11-07`, and all five protected unrelated dirty paths. No more login UI polish unless a reproduced regression. Owner will continue collecting A–Ö issues (AÖ-01 through AÖ-06) in this ledger; defer implementations for later prioritized bug-fix batch, starting with pilot blockers AÖ-06/AÖ-03. One Copilot order → one report → review.

**Tablet Pilot Gate — required before Kommun 1.1 PILOT GO (owner evidence 2026-11-08):** iPad Safari is a primary kitchen/department device, not a secondary responsive nicety. AÖ-12/13/14/16/20 demonstrate repeated **real-device** layout and tap/interaction failures that automated desktop tests did not establish as fixed. Once A–Ö collection ends, first perform a **read-only common shell/component cause analysis**, fix the shared cause in bounded tasks without regressing locked desktop and landscape behavior, then manually verify **both iPad orientations** with the actual admin/kitchen/department roles and real menu/Planera/Weekview actions, including touch, printing and both themes. No pilot GO on desktop-only browser evidence. AÖ IDs remain separately trackable; this gate is a release acceptance rule, not another backlog.

**AÖ-08A / AÖ-08I tenant security resolution (2026-11-13, owner accepted):** Import scoping `a1c7a96b`, menu context `89d56460`, Builder library fail-closed scope `0169570a`, publication scope `453c62c5` implemented and committed; owner-approved Fantasiköket local repair fixed 20 cross-tenant composition references without deleting menus or prior revisions. Live local two-tenant Admin tests showed independent daily changes and explicit foreign-tenant Weekview denial. New isolated regression at `ea8c0c2b` confirms tenant B cannot GET or render tenant A's known composition ID or see it in B's library, while A can read it (focused 1/1, related 5/5 passed). **SECURITY GATE CLOSED / OWNER-ACCEPTED**, not a full hosted penetration audit. **AÖ-08B Builder modal visual issue OPEN, tracked with AÖ-26.** Do not reimplement fixed scoping, rerun data repair, or restart broad security audit without new evidence.

### First A–Ö owner pass — CLOSED FOR INTAKE (2026-11-08)

- Owner confirmed first clean-customer end-to-end walkthrough is finished. **This closes the first observation round only; it does NOT close AÖ issues and does NOT mean Kommun 1.1 Pilot GO.** Retain numbering AÖ-01–AÖ-24, with **AÖ-15 cancelled/rolled back** and recheck of kitchen nav pending. The remaining IDs include security investigations, functional blockers, UI issues, requested features and the later AÖ-18 design audit; do not misrepresent all as proven bugs.
- **Confirmed empty output is not a new defect:** owner saw `Inga registrerade serveringstillägg` at Kitchen → Produktionslistor → Tillägg, consistent with earlier unsuccessful registration for this clean site. Keep linked to **AÖ-06A/B**, and prove after repair that data follows registration → production lists → Page3 packlista, with correct no-data state.
- **Triage order, no implementation in first gate:** (1) **AÖ-08A** read-only tenant/site isolation forensic review for W45 vs W46 menu/editor (elevate to CRITICAL only if foreign-tenant access evidenced); (2) **AÖ-06A/B and AÖ-03** creation blockers and downstream persistence; (3) **iPad real-device pilot blockers AÖ-12, AÖ-13, AÖ-14, AÖ-16, AÖ-20** through a common shell/component cause census; (4) **AÖ-19** Kitchen↔Builder read access/scope decision, **AÖ-21** review-state correctness, **AÖ-24/AÖ-17** print correctness, report/access and hosted auth release checks; (5) focused UX fixes AÖ-01/02/04/05/07/09/10/11/22/23 and **AÖ-18** read-only design consistency census at the end. Reprioritize with concrete evidence; do not bundle cross-cutting changes without proof.
- **Workflow:** one narrow read-only Copilot investigation/report first, owner+ChatGPT review, then one bounded fix per gate with tests and real iPad verification. No auto edits, migrations, seed, reimports, tenant data mutation, deploy or commits in the first security census. Preserve five dirty protected paths, approved login/Builder/portal/Planera behavior. Remote is documentation-only commits ahead of last owner-confirmed product HEAD `45c961936c762881150ee85db4849c0d3b32e899`; reconcile before any later code commit.

### Owner A–Ö walkthrough findings — 2026-11-08 intake (historical observations; 2026-11-13 status matrix overrides outdated status wording)

**Current A–Ö scenario (historical 2026-11-08 intake; use 2026-11-13 matrix for actual current statuses):** new test customer `Fantasikommunen`, site `Fantasiköket`, separate admin, new residence/department and registered needs. Owner is collecting defects/UX opportunities during the actual workflow. Keep these findings in this existing operational ledger (no competing bug list). **Login 1.1 visual polish Gate 04A is a separate, parallel VS Code Copilot workstream; do not interrupt or modify the dirty worktree until its report is reviewed.** One order → one report → review. Screenshots supplied by owner in the conversation, not yet checked into repo.

| ID | Type / priority | Owner observation | Status and acceptance target |
| --- | --- | --- | --- |
| **AÖ-01** | Login compatibility with internationalized email domains / MEDIUM | First admin entered with an `ö` domain (`barbro@fantasiköket.se`) could not be used to log in. **New owner screenshot 2026-11-08:** that first account is present in Admin → Användare as **inactive** with Punycode-address `barbro@xn--fantasikket-yfb.se` (both displayed name fallback and email). A *different* replacement account using `barbro@fantasikoket.se` (ASCII `o`) is active and works. Distinct domain names must not be conflated. Screenshot confirms IDN conversion/storage and inactive account, **not why login failed**: it might have been normalization mismatch at login or account activation/inactivation sequence. | **CLOSED / OWNER-ACCEPTED / PUSHED 2026-11-18, `347b958c` (supersedes historical OPEN triage).** Owner chose e-post OR globally unique ASCII username rather than IDNA-equivalent email login. Login/Admin form tests and manual owner checks accepted; original inactive account untouched; no schema, migration or hosted reset proof. Historical diagnosis text on this row remains intake evidence only. |
| **AÖ-02** | Copy/encoding / LOW | Admin sidebar displays `Anv?ndare` instead of `Användare` in owner's light-theme screenshot. | **OPEN** — confirm source, encoding and render path; correct localized label without changing shared navigation behavior. |
| **AÖ-03** | Creation blocker / HIGH | On New Department → Residence → `+ Lägg till` → `Spara boende`, the `Lägg till boende` dialog stays over the form as though stuck, even while newly created residence appears selected behind. | **CLOSED — AÖ-03A owner-accepted modal dismissal, commit `b9a478d7` (2026-11-10 checkpoint).** Historical diagnosis and acceptance target retained below for traceability; reopen only with reproduced failure. Investigate whether save succeeded exactly once and modal visual state failed to close. Source inspection suggests `setupResidenceCreateModal` in `static/js/unified_admin.js` calls `dialog.close()` on successful AJAX response without removing `ua-modal-open`; CSS `static/css/unified_admin.css` forces `display:flex` for that class. This is a **hypothesis**, not an accepted fix. Reproduce in isolated test site/DB; inspect JSON response, DB count, modal's `open` flag/class, dropdown selection, prevent duplicates; smallest scoped fix and regression then owner review. No blind CSS overhaul. |
| **AÖ-04** | Admin Specialkost UX improvement / MEDIUM, pilot prioritization pending | In Department → `Lägg till kostbehov` modal, owner cannot create a missing atomic **specialkosttyp** from the picker and must separately visit `Specialkost`. Suggests direct action or navigation. | **OPEN — design candidate only.** Preferred UX: small `+ Skapa ny kosttyp` action next to/below the primary requirement picker and optionally the additional-requirement picker. In-place create state (avoid nested modal), reuse **the same site-scoped canonical DietTypesRepo/upsert/validation semantics as** `/ui/admin/specialkost/new` (name, family, default-select if applicable), check existing/reuse before creating, then add the new type to both picker lists and preselect it in current context **without losing current department form, count or modifiers**. The newly created type must appear under Admin → Specialkost after reload and only inside the correct tenant/site. This is catalog creation, NOT creation of a department requirement cohort by itself; the user still explicitly saves `Spara kostbehov`. A navigation link with return context is fallback if in-place behavior cannot be safely delivered. Never create duplicate catalog truth. |
| **AÖ-05** | Combined dietary-needs **display** in department list **and unit portal** / MEDIUM-HIGH for pilot clarity | **Owner confirms registration, data model and combined count are correct.** Original finding: in Admin → department saved-needs list, additional dietary need was visually sidelined. **Follow-up 2026-11-08 from iPad unit portal (Fantasikommunen / Fantasiköket / Gammelapan):** special diet card shows `Glutenallergi` in bold and `+ Laktosallergi` as a small, faint side badge, with **1 person** at right; the smaller modifier appears less important even though *both restrictions apply to the same person and must carry equal kitchen importance*. Owner wants equal visual emphasis. | **CLOSED / OWNER-ACCEPTED / PUSHED 2026-11-16** (supersedes historical OPEN text). Both Admin and Unit Portal combined labels now use equal visual weight with one unchanged group count; owner verified both. Product commit `ae98e0ec`, 39 passed / 5 skipped, exact eight scoped files and clean verified push. Registration, group IDs, primary/modifier semantics, tenant/site isolation and Planera calculations preserved. |
| **AÖ-06A/B** | Serving-adaptation registration / **HIGH: pilot blocker** | Owner's clean test customer/department cannot select/register serving adaptations or use **`+ Skapa ny serveringsanpassning`** and **`+ Skapa ny familj…`** as intended; modal screenshot has blank family/dropdown, seemingly inactive choice cards and quantity fields shown inconsistently. Owner reports none of the flow works. | **CLOSED / OWNER-ACCEPTED 2026-11-13:** earlier technical fixes `884eb7ee` (Admin selection/registration) and `761c07e9` (Page3 server-backed navigation) were already pushed and accepted. Owner separately performed all four end-to-end UI checks on the same saved Fantasiköket 2026-W46 Monday lunch MOS/PASTA adaptations: Admin records/counts → Kitchen Produktionslistor → Planera Page3 Serveringsanpassningar without refresh → Specialkost/Packlista incl. department without regular menu choice. All four passed. No fresh code change or seeded data. The previous historical defect report at the start of this row is archived evidence, **not** a currently open blocker. General iPad/browser pilot release testing remains separate. |
| **AÖ-07** | Admin Menu Import / light+dark button contrast / MEDIUM | Owner observed mismatched menu status-card button palette and invisible/low-contrast hover text on `Redigera meny`, `Publicera`, `Tillbaka`, `Klar`, `Återgå till utkast`. | **CLOSED — owner visually accepted desktop light+dark on 2026-11-12; commit `828151f6` pushed.** Scoped to three Admin Menu weekly view CSS/template/test files; 9/9 JS + 15/15 Python focused regressions, normal/hover contrast measured; no global app-shell changes and 04D.1 dialog unchanged. Real iPad full UI check remains part of final pilot acceptance, not a reason to reopen the accepted design without evidence. |
| **AÖ-08A/B** | Canonical menu import cross-tenant reference integrity; **AÖ-08A CODE/DATA FIXED (2026-11-09)**, AÖ-08B separate Builder modal visual issue | **Historical verified defect:** 2026-11-09 forensic review found foreign-tenant composition IDs linked into Fantasiköket W45. No unauthorized read/write demonstrated. **Code remediation** committed/pushed as `a1c7a96b`: `core/commun_builder_import.py`, `core/menu/composition_resolution.py` and `tests/core/test_commun_builder_import.py` implement scoped alias/name resolution and cross-tenant regression. **Local data remediation AÖ-08I:** 20/20 incorrect references corrected, zero cross-tenant references remaining in the documented post-check, W45/W47/W48 version 2 publication with earlier revisions preserved and affected dish text retained unresolved. Owner accepted Fantasiköket flow. | **AÖ-08 SECURITY CLOSED / OWNER-ACCEPTED 2026-11-13:** previously repaired import/context/library/publication tenant scoping and 20/20 local bad references remain frozen. Two live local customer Admin sessions showed independent saved changes, foreign-tenant Weekview URL denied; dedicated Builder known-composition GET/render/library cross-tenant read test passed and pushed `ea8c0c2b` (1/1 focused, 5/5 related). No demonstrated leak. **AÖ-08B UI modal frame is separate and OPEN with AÖ-26.** This is not a full deployed/penetration audit; do not re-open security without new evidence. |
| **AÖ-09** | Admin Users list actions visual layout / MEDIUM UX | Owner screenshot 2026-11-08 from **Admin → Användare** for new customer `Fantasikommunen`/site `Fantasiköket`: action controls for active admin (`Redigera`, `Återställ lösenord`, `Inaktivera`) are awkwardly stacked as mismatched button sizes/widths with wrapping and excess row height, making the users table look unfinished. Top-right `+ Skapa användare` CTA visible, but the screenshot does **not** demonstrate a defect in the user-creation form. First inactive IDN/Punycode account shown separately and tracked under **AÖ-01**. | **OPEN — display-only polish after A–Ö review.** Make `Åtgärder` a consistent compact responsive action group for active rows, with uniform controls, spacing/alignment and appropriate wrapping or menu treatment on small screens; preserve edit/reset/deactivate actions, disabled/inactive states, permissions and confirmation UX. Verify light/dark desktop/mobile/iPad; do not alter account data, auth logic or revive inactive account. |
| **AÖ-10** | Admin user lifecycle / MEDIUM feature gap, safety-dependent | During new customer A–Ö owner finds no action to **remove a mistakenly created user**: only `Redigera`, `Återställ lösenord`, and `Inaktivera`. Owner proposes placing `Ta bort användare` *inside Redigera användare*, not cluttering list actions. The earlier inactive Punycode admin test user is an example of a record owner may want removed. | **OPEN — user-facing removal vs deactivation contract to decide before implementation.** Recommend secondary/destructive area in **Edit User** labeled clearly. Preserve `Inaktivera` as reversible access shutdown; **do not silently implement `Ta bort` as the same action**. Before any permanent deletion, inspect historical references (audit, menu choices, production records, etc.), FK constraints, retention requirements and impact on authentication. Support safe permanent removal of unused/test accounts only if dependencies permit, with explicit confirmation identifying account and consequences; otherwise offer archiving/hiding inactive accounts with clear explanation. Fail closed for own account, last tenant admin, foreign tenant/site, other protected accounts; CSRF, proper authorization, session/token revocation, tests. No deletions during A–Ö and never delete user data merely to make the table neat. |
| **AÖ-11** | Admin Users language / LOW-MEDIUM UX | Owner screenshot A–Ö 2026-11-08: user table column heading **`SCOPE`** is developer terminology. It is unclear to normal municipal administrators what they are granting access to. The New/Edit User form also labels context `Scope`. | **OPEN — copy-only improvement, no authorization changes.** Rename list column to **`Har tillgång till`** and display human-readable targets: e.g. admin/kitchen `Fantasiköket`, unit portal `Solgläntan – Gammelapan`. In create/edit form use **`Arbetsplats` / `Avdelning`** or clearly named **`Åtkomst`**, avoid technical terms `scope`, `site`, `tenant` in user-visible copy where practical. Ensure correct distinction between tenant, site and department while retaining all existing actual access-control checks and strict site isolation. Check responsive columns, dark/light and screen-reader labels. |
| **AÖ-12** | Kitchen shell: **iPad portrait** oversized blank block before content across multiple routes / **HIGH responsive pilot blocker** | First owner screenshot 2026-11-08 as `cook` in **portrait** from kitchen **Översikt** displayed a massive empty light block under navigation; useful dashboard content starts after approximately a screen of scrolling. **New independent owner screenshot 2026-11-08 17:29, portrait iPad Safari:** the **Planera** screen also starts with the same oversized empty app-shell/sidebar panel with `Yuplan` footer, and the actual Planera heading/Week 45 cards appear far below it. This is **cross-page shell behavior**, not only an empty Overview dashboard. Owner earlier said landscape looked correct for Overview; landscape Planera not yet verified. | **CLOSED — owner-approved real iPad portrait/landscape correction; AÖ-IPAD-02/02B checkpoint `dd60366a8269e86d8383589fa369f9c9420ebd03` (2026-11-10 status).** Prior diagnostic target (historical): prioritize shared shell portrait geometry diagnosis, then verify local page bodies. Reproduce with same site/`cook` in portrait and landscape for at least Kitchen Overview, Planera, Weekview, Menu Overview, Production Lists; inspect responsive sidebar transform/collapse, shell `min-height`, padding, flex/grid `height`, `100vh/100dvh`, safe-area/viewport differences; screenshot and computed layout evidence. Desired first useful heading/card visible immediately below usable nav in portrait without forcing one-screen scrolling. Preserve already-working desktop/landscape behavior, no broad design rewrite. No changes to Planera engine or data. Add iPad Safari real-device and browser-viewport regressions. **No code change during owner A–Ö collection.** |
| **AÖ-13** | Kitchen Weekview iPad layout / **HIGH, pilot tablet blocker** | Owner screenshots 2026-11-08 as `Kock Fantasi` show **both iPad portrait AND landscape** kitchen weekly grid breaking: menu/book icon rendered outside its intended cell/table edge; `Lunch`/`Kväll` subheaders are clipped/overlap or do not fit within their meal cells. The 7 days × 2 meals table currently appears over-compressed on iPad. Separate from AÖ-12 dashboard portrait whitespace. | **CLOSED / COMMITTED / PUSHED — owner accepted with known visual deviation (2026-11-11, `8ac4bc86`).** Responsive table and sticky diet column now work acceptably on real iPad; Thursday still renders slightly unevenly in landscape (tracked under AÖ-27). No more AÖ-13 tweaking now; retain tests and protect AÖ-14. Historical acceptance criteria: Reproduce tablet portrait/landscape and desktop, use adaptive/grid min widths and **contained horizontal scrolling where needed** (do not shrink 14 meal columns until unreadable), preserve sticky left `Kostbehov` column/row headings and day boundaries, ensure each `Lunch`/`Kväll` label and menu icon stays *inside its intended cell*, clickable and not clipped. Verify text wrapping, zoom and touch targets, no body-level sideways scroll and no other screen regression. Do not change menu/source/tenant data or approved counts. |
| **AÖ-14** | Kitchen Weekview iPad 'markera gjorda' interaction / **HIGH, functional pilot blocker** | Owner tested kitchen weekly view on iPad portrait and landscape 2026-11-08; cannot mark specialkost/cohort counts as done by tapping numbers, despite existing intended behavior. | **CLOSED 2026-11-10 — real iPad accepted, persisted green completion after reload, unmark works, tenant/site checks secured; AÖ-IPAD-03B–03J pushed as `9b73721ebab6d29ef84d7c4edbac86649c24c66c`, 36/36 Python tests each order and 19 JS tests passed.** Historic investigation target (superseded): reproduce function separately from layout. Verify touch/click targets, event delegation, overlay/z-index/pointer-events, disabled/ready state, API network/status, CSRF/ETag/authorization and cohort completion eligibility; compare desktop behavior and Page3 mark-done contract, confirm persisted completion and green circles + stats after refresh when allowed. Do not silently bypass prerequisites or alter authorization to make it clickable. Test both tablet orientations and normal desktop, with isolated reversible test data; no code changes during A–Ö collection. |
| **AÖ-15** | TEMPORARY testing navigation to Planera 2.0 / **CANCELLED AND ROLLED BACK 2026-11-08**, not a product feature | Owner requested a temporary `Planera 2.0 (test)` link directly below old `Planera` during A–Ö. Copilot changed `templates/ui/_layout/app_shell_base.html` and `tests/ui/test_global_navigation.py` locally; reported 32 green tests using a synthetic test harness, but owner observed `Avdelningsportal` link and mixed kitchen/admin navigation in real UI. **AÖ-15B correction order was NEVER sent.** Owner ordered an immediate rollback instead. | **ROLLBACK TECHNICALLY VERIFIED / LIVE UI RECHECK PENDING.** Copilot examined the exact 2-file diff (AÖ-15 only), restored *only* those files from local HEAD `45c961936c762881150ee85db4849c0d3b32e899`, verified worktree blob hashes match HEAD for both, found no staged changes, ran `tests/ui/test_global_navigation.py tests/ui/test_kitchen_user_access_pilot.py tests/ui/test_admin_dashboard_today_menu.py` = **16 passed**, and protected all five unrelated dirty areas. No commit/push/merge/deploy, no runtime restart. There is **no AÖ-15 navigation implementation left**. **No more Copilot link work during A–Ö.** Product owner should reload the current locally served app on iPad and check kitchen menu vs admin/department portals; if still mixed, investigate a separate role/session/nav-context issue without assuming the link patch is present. The existing product2 route `/ui/kitchen/planering?ui=product2` may be used directly with an authenticated kitchen session and valid active site; preserve a single product `Planera` navigation until final release decision. |
| **AÖ-16** | Global header badges clipped at top on iPad landscape / MEDIUM responsive UX | Owner screenshot 2026-11-08 15:27 on iPad **landscape**, logged in as `Kock Fantasi`: the **KUND: FANTASIKOMMUNEN · ARBETSPLATS: FANTASIKÖKET**, site and local/environment header badges are partially clipped at the **top of the viewport**, obscuring the top half of their text; user identity badge is lower and visible. Kitchen dashboard/main cards themselves render at expected positions. This is distinct from AÖ-12 portrait empty whitespace and AÖ-13/14 weekview grid/tap issues. | **OPEN — global shell display bug only.** Reproduce at real iPad Safari landscape and portrait (including browser address/toolbars, scroll position, zoom and viewport safe area), compare desktop; inspect sticky/fixed positioning, negative top offsets, transform, header row wrapping, overflow clipping, safe-area inset and responsive CSS/JS. Keep `Kund`, `Arbetsplats`, site and environment indicators fully legible, not hidden beneath iPad status bar or clipped by app shell. Avoid increasing global header height unnecessarily or altering approved desktop shell, role/site data and authentication. Add responsive visual regression for affected viewport. **No implementation during A–Ö collection.** |
| **AÖ-17** | Kitchen menu overview printing — undesirable two-page A4 pagination on iPad / MEDIUM-HIGH operational UX | Owner screenshot 2026-11-08 15:35 from **iPad Safari print preview** while logged in to Kök → **Menyöversikt** for **week 45/2026**, **A4, portrait, 100% scale, 1 page per sheet**: the week menu splits across **two pages**, with **Thursday (Torsdag) alone on the second page** and substantial wasted space. User expects a compact weekly menu printout rather than an orphaned day. Small developer/cookie text also appears in print preview header; verify whether it is unintended print content. This is a print-specific presentation issue, separate from AÖ-13 kitchen Weekview table responsive bug. | **CLOSED / OWNER-ACCEPTED / PUSHED 2026-11-13** (supersedes historical OPEN notice). Owner approved actual iPad Safari print after Gate 05; final product commit `715509c3`, 2/2 JS and 5/5 Python targeted tests passed, clean tracked checkout after push. Rowwise print-only non-table block structure fixed earlier mid-day/daycard splitting and preserved accepted desktop layout. No new tenant/site logic, menu data, app shell or other print work. Longer-than-page menus and orientation/browser release matrix remain final E2E, not independently verified. |
| **AÖ-18** | Yuplan-wide design consistency / UX AUDIT after A–Ö, NOT blanket redesign | Owner requests one systematic Copilot-led UI audit of **all current Yuplan interfaces** against the most recently owner-approved Yuplan design and components. Specifically **print buttons/icons throughout product should match the approved Planera 2.0 printer-button styling**, rather than mixed text buttons or disparate printer icons. Existing AÖ light-theme hover contrast, modal frames, table/actions and tablet regressions show need for consistency review. | **OPEN — scheduled audit first, not immediate implementation.** After owner finishes the A–Ö walkthrough, instruct Copilot to inventory Admin, Kitchen, Unit Portal, Menu Builder, Weekview, Planera 1/2/3, Menyöversikt, Production Lists, login and common modals in desktop/iPad portrait+landscape/mobile, **light and dark themes**. Compare real rendered states and components to approved baselines; list exact route/view, CSS/JS/templates, screenshot, severity, proposed minimal correction and regression risks. Pay particular attention to print icons/buttons (use Planera 2.0 approved as canonical), primary/secondary/danger controls, hover/focus/disabled contrast, spacing, typography, cards, backdrops/dialogs, table/responsive behavior and user-facing wording. Distinguish existing **functional bugs** (keep AÖ IDs) from polish; **do not duplicate or silently close AÖ-01..17**. Stage 1 READ-ONLY census/report → owner selects scope → one bounded Copilot order per accepted fix. Never change shared app shell globally or override already LOCKED features without evidence. Protect approved Login 1.1, Builder editors, Planera logic and five protected dirty paths. Release criterion: cohesive Yuplan styling without behavior regressions. |
| **AÖ-19** | Kitchen↔Builder knowledge/access — **publication and Admin safety portions CLOSED, separate Kitchen library scope OPEN** | Canonical publication and Menu Overview information access use the existing Builder Dish Modal; full site-scoped Kitchen searchable `Recept & rätter` access remains outstanding. | **PARTIAL / PRODUCT CHECKPOINT LOCKED (updated 2026-11-12):** Gate 04A/04B published-only Kitchen menu + safe Builder re-publication revisions CLOSED (`32696f55`, publication recovery tag unchanged); Gate 04C Kitchen Dish Modal display/closure and iPad row spacing CLOSED (`93b5f5dd`); Gate 04D.1 Admin unpublish warning and published edit explanation CLOSED (`be27f98f`). **04D.2/04D.3 changed-menu automatic user notices and displayed diffs are DEFERRED by explicit owner decision 2026-11-12, not queued as active implementation.** Admin chooses manual communication via existing Kitchen dashboard notices; Portal messaging is only future direction. Internal history and stale/review/tenant safety remain untouched. Separate Kitchen `Recept & rätter` library/search/permissions remains OPEN; full AÖ-19 and Kommun pilot GO not claimed. |
| **AÖ-20** | Kitchen Planera week/day selector on iPad portrait / **responsive interaction issue** | Owner found week controls colliding with Monday tile, unclear native week spinner, poor year display and discoverability. Published-week logic `7de5bfb4` and year-clipping fix `81371499` were pushed previously. | **CLOSED / OWNER-ACCEPTED 2026-11-13 (supersedes earlier pending note):** Owner rechecked actual Admin published-week selection and Kock → Planera Page1 iPad controls and confirmed the reported defects already fixed; no new product code. Preserve correct date/year and page flow. Separate ISO 2026-W52 → W53 → 2027-W01 and full browser/orientation release E2E still unverified, not claimed as passed. |
| **AÖ-21** | Planera 2.0 Page2 initial review warning appears on first entry / MEDIUM-HIGH state clarity; investigate false stale classification | Owner A–Ö 2026-11-08: after selecting a dish/meal in Planera Page1 and entering Page2 **for the first time**, the banner says **`Underlaget har ändrats – granska igen`**. To a new user, this misleadingly asserts a change since an earlier review that has not occurred in this workflow. Need verify whether Page2 is truly first review for meal/site/week, versus inherited/stale review state from a previously reviewed, republished or other meal/context; do not assume false positive or cross-tenant leakage without traces. | **CLOSED / OWNER-ACCEPTED / PUSHED 2026-11-13** `f54b78f4`: isolated Page2 VM reproduced erroneous stale banner for unreviewed alt1 when alt2 had saved review. Fix in `core/ui_blueprint.py` reads each current option's review and requires nonnull saved `review_id` for `review_present`; existing hash/stale safeguards and production contracts unchanged. Owner confirmed actual Planera Page2 experience working. Added focused regression in `tests/core/test_planning_option_review.py`; full review service 25/25 and related API 15/15 green. Three Page2 UI tests blocked by separately preexisting fixture `projection_error` and remain tracked for final test infrastructure acceptance; not a product blocker for this accepted fix. No further AÖ-21 work absent reproduced regression. |
| **AÖ-22** | Planera 2.0 Page3 **Produktionsunderlag** heading typography inconsistency / MEDIUM visual polish | Owner iPad Safari landscape screenshot 2026-11-08 17:36 shows the `Produktionsunderlag` h1 substantially heavier, tighter and visually louder than Yuplan app-shell page headings; owner suspects the **top of the P may be clipped**. Screenshot supports a possible glyph/line-box crowding issue, but does **not conclusively prove actual glyph clipping**. Read-only code evidence: `templates/ui/kitchen_product_planera_page3.html` uses `<h1 class="yp-planera-page3-title">`, with local `static/css/planera_product2_page3.css` defining `line-height: 1.05` and `letter-spacing: -0.05em` for that heading, rather than the shared `.app-shell__title` typography. Text style likely contributes to appearance; actual browser computed metrics and iPad font/text auto-sizing still need verification. | **OPEN — align Page3 title with approved Yuplan shell visual language, as a scoped instance of AÖ-18 design audit.** Reproduce iPad Safari portrait/landscape, desktop, light/dark, text zoom; inspect computed `font-family`, `font-size`, `font-weight`, `line-height`, `letter-spacing`, overflow, font ascent/line box and iOS text inflation; verify if the glyph top is actually clipped. Propose modest readable title typography matching comparable Yuplan page headings (weight, spacing, size), with full glyph extents and responsive wrapping, **without homogenizing approved Page3 body/controls or changing Page3 calculation/print/status/navigation**. Owner approves before implementation; targeted visual regression only. No code changes during owner A–Ö collection. |
| **AÖ-23** | Planera 2.0 Page3 Overview focused-vs-all menu options selector / MEDIUM usability and navigation gap | Owner A–Ö 2026-11-08: arriving at Production Underlag → **Översikt** after selecting one lunch dish correctly shows that dish, but the button `Visa hela lunchen` reads like an informational statement and shows both lunch alternatives upon click, **without an obvious return to one dish**. **Owner follow-up clarifies preferred existing solution:** under **Page3 → Normalkost** there is already a clear `Visa` dropdown with `Alla rätter` and the actual current lunch dishes; owner finds this much more understandable and wants **the same pattern in Översikt** instead of another bespoke two-state button. Verified template `templates/ui/kitchen_product_planera_page3.html` already renders `<select data-page3-normal-selector>` with options `Alla rätter` plus `vm.normal_matrix.columns` in Normalkost; Översikt uses only the `Visa hela lunchen` link. | **OPEN — reuse the approved Normalkost selector UX as the reference, not introduce a competing button concept.** Put a clearly labeled `Visa` selector in Översikt with **`Alla rätter`** and the actually available day's lunch alternatives, same visual/interaction semantics as Normalkost, automatically selecting the originally chosen dish upon entry. User can switch `vald rätt → alla rätter → vald rätt/other dish` at any time from the same control, with no stranded view. Prefer reuse of existing UI patterns/route state; check whether `vm.overview_options` and `vm.normal_matrix.columns` cover same options and keep optional dessert/other-meal behavior appropriate. Preserve scoped site/date/meal, selected option, URL navigation, reviewed/completion status, true totals and zero changes to underlying calculations/menus. iPad touch/portrait/landscape + desktop/light/dark keyboard tests, safeguard cross-tenant IDs, do not rewrite the working Normalkost selector. **No code change during owner A–Ö collection.** |
| **AÖ-24** | Planera 2.0 Page3 **Normalkost printable production underlay** A4 right-column crowding / **HIGH print operational correctness** | Owner supplied actual **Safari/iPad generated PDF, `Produktionsunderlag.pdf`, 1 page A4 portrait**, for **Fantasiköket / Lunch / Monday 9 Nov 2026**, Page3 **Normalkost** table. Right dish column `Korv Stroganoff med ris` runs against the **right table/page edge**; last heading is visibly crowded, making clipping likely if a dish title grows. Print also includes **`Du anvander flera hosts i dev. Anvand bara http://127.0.0.1:5000 for stabila cookies.`** above content, unrelated to kitchen work. Table text is overly heavy/widely tracked (`AVDELNING`, `GAMMELAPAN`, `SUMMA`), while much of page height is unused. Safari auto-generated source URL/date/footer appears at bottom; distinguish browser print header/footer from app DOM. This is **distinct** from AÖ-17 Kitchen Menu Overview print pagination and AÖ-22 on-screen Page3 h1 visual typography. | **CLOSED / OWNER-ACCEPTED / PUSHED 2026-11-13** (supersedes historical OPEN text). Gate 01–03 print-only product change `cbf6e1f1`, 8/8 JS and 27/27 Python UI targeted PASS; owner reviewed actual iPad output and approved readability. Hidden dev-host banner, right-column fixes, compact hierarchy, single end SUMMA; no residence grouping. Exact multipage Safari pagination with 20 departments remains release E2E, not an unverified success. |
| **AÖ-25** | Admin published weekly menu `Veckomeny` card: dish text crushed into narrow columns on iPad portrait / **HIGH tablet UX** | Owner screenshot 2026-11-08 18:11 as `admin` under Fantasikommunen / Fantasiköket, published Week 46 menu page `Meny – vecka 46/2026`: two-column card layout (`Status` beside `Veckomeny`) leaves dish-value links inside **extremely narrow mini-cells**. Dish names such as `Fiskgratäng med räkor och potatis`, `Korv Stroganoff med ris`, and `Silltallrik med kokt potatis` wrap into near-vertical text and some appears to overflow its intended rounded field; unusable on iPad portrait. Owner calls this a missing responsive card/placeholder fit. Separate from kitchen Menu Overview print AÖ-17 and kitchen Weekview layout AÖ-13. | **CLOSED / OWNER-ACCEPTED 2026-11-13 – no new code:** Owner was asked to reproduce the old weekly Admin menu portrait text squeeze on real iPad, logged in as Admin and confirmed the problem is now gone. The original 2026-11-08 screenshot remains historical evidence only. No causal attribution to earlier iPad CSS changes has been verified. Keep the working layout and all published-week menu interactions locked; reopen only if a new live screenshot shows an actual regression. |
| **AÖ-26** | Builder Dish editor modal over-expands on iPad landscape; **blue outer border** around overlay / **MEDIUM-HIGH tablet UX & potential approved modal regression** | Owner screenshot 2026-11-08 18:15 on real iPad Safari **landscape**, after opening dish `Fiskgratäng med räkor och potatis` from Admin published Week 46 menu. `RÄTT` editor is functional-looking but **takes nearly entire iPad viewport**, with a strong **thin blue rectangular outline around the larger host/backdrop container** beyond the rounded white modal, perceived as confusing/unfinished. The outer border/outline appears separate from the actual editor card. This may overlap prior AÖ-08B light-mode Builder-host frame regression, but it is **not established** whether border is an iframe focus ring, host CSS, dialog focus outline or another overlay; avoid assuming a specific cause. The earlier approved Builder editor modal/frame visual behavior is locked. | **OPEN — read-only root-cause and visual regression check first.** Reproduce same modal iPad landscape/portrait and desktop dark/light, inspect iframe/dialog/host bounds, focus outline (including accessibility focus indicators), backdrop, `builder_editor_host.css`, modal host CSS and media queries, `max-width`, `max-height`, viewport safe-area, internal scrolling and keyboard/tab behavior. Keep the legitimate visible focus treatment for keyboard users; remove only unintended *outer host frame* or misplaced border. Propose a sensible comfortable tablet editor width (not edge-to-edge), safe margins and contained vertical scroll without clipping tabs, action controls or content; don't change canonical Builder editor functionality, component tabs, site/tenant scope or accepted dialog-close flow. Correlate with AÖ-08B and test whether same root cause can be fixed once; preserve approved existing desktop visuals. No code change while owner A–Ö collection continues. |

**Historical 2026-11-11 work sequence (superseded by the 2026-11-13 priority matrix):** AÖ-08 original foreign-reference investigation was followed by scoped code fixes and owner-accepted local data repair. Do not reimplement or rerun. Manual authenticated tenant A/B release proof remains a distinct future release check. The previously overlapping AÖ-08B/AÖ-26 modal visual issue was subsequently CLOSED by explicit owner confirmation on 2026-11-13; this historical note is not an active task order.

| **AÖ-27** | Kök → Veckovy: overall visual finish, especially saturated yellow lunch highlights / **MEDIUM visual polish; owner review** | Owner supplied real iPad Safari landscape screenshot 2026-11-11 (week 46, Fantasiköket). Broad solid ochre/yellow highlighted lunch cells dominate the dark view; dense gridlines, tight information and basic table styling make the otherwise functional weekly overview feel visually unfinished and inconsistent with Yuplan's desired premium design. Owner additionally reported 2026-11-11 that **Thursday's day/meal columns still look slightly uneven relative to other days in iPad landscape**, despite the functional AÖ-13C layout being accepted for now; inspect actual rendered column widths and borders as part of the design pass, without reopening AÖ-13 immediately. This is an aesthetic judgement, **not** a claim that the highlighted values or Alt2 logic are wrong. Separate from **AÖ-13** tablet geometry/sticky/day-width bug and **AÖ-KITCHEN-ALT2-01** contrast of the Alt2 label in a different view; related to **AÖ-18** design consistency. | **OPEN — design review after AÖ-13 functional acceptance, no implementation yet.** Inspect actual dark/light rendering on iPad portrait/landscape and desktop. Verify and normalize Thursday versus other day widths as part of the future layout/design sweep; propose a calmer and more cohesive table hierarchy: less visually heavy grid, refined row/day grouping, restrained yet recognizable Alt2/lunch highlights (avoid large harsh solid yellow blocks), consistent spacing/typography, clear separation of dates and meals, readable totals and diet names, distinct done/undone status. Preserve accessible contrast, yellow/Alt2 meaning where required, completion rings/clicks, counts, meal icons, tenant isolation, responsive horizontal scroll and print output. Coordinate with AÖ-18 but keep future implementation narrowly scoped to Kitchen Weekview; show owner a visual proposal before code, then verify real iPad and regression tests. |

### Additional A–Ö follow-ups observed after the initial numbered ledger

| ID | Owner observation | Current disposition |
| --- | --- | --- |
| **AÖ-IPAD-PRINT-01** | Kök → Produktionslistor: printer icons start green, turn grey after touch and sometimes show an unexpected yellow state; suspected sticky iPad `:hover` / `:focus-visible` precedence over `aria-pressed` semantics. | **OPEN.** Reproduce iPad state and fix only print icon CSS/pressed semantics without changing print actions; cross-check AÖ-18 visual consistency. |
| **AÖ-PWA-01** | Home-screen installed app opens `/`, with cook role falling into legacy `/ui/cook/dashboard` instead of the approved modern `/ui/kitchen` entry. | **OPEN.** Verify manifest `start_url`, authenticated role-aware root redirect and legacy dependencies before changing entry; never hardcode cook-only start URL for other roles. |
| **AÖ-KITCHEN-ALT2-01** | Kitchen Overview Lunchalternativ 2 label has poor contrast in dark theme and is too dark in light theme. | **OPEN.** Check theme-specific Alt2 highlight/contrast with owner screenshot and keep the useful Alt2 distinction; do not confuse with AÖ-26 Builder editor modal. |

### Known follow-ups: evidence, not automatic implementation orders

- **Reporting:** The October 31 investigation found several distinct report purposes and possible inconsistent coverage/export labels. At least one existing Weekview report already reads Product2 cohort completion truth; it is **not** accurate to say that every report is completely disconnected. A November 6 focused census showed 184 green non-report pilot tests, a report subset with 1 failure/3 errors and standalone Portal JS tests with 8 passing/11 failing; investigate test-harness drift vs real defects in the final verification. Review negative tenant/site/department report access and PDF/CSV/HTML consistency. Do not build a new reporting engine without an accepted concrete gap.
- **Menyval precedence:** Admin and Portal share canonical department choice persistence; October notes describe separate original/override/effective storage as not established. Preserve existing working choice flow; revisit precedence only when a concrete use case fails acceptance.
- **Portal JS test debt:** after visual checkpoint `1ff5dbef`, `static/tests/portal_department_week_choice.test.js` still reports **9 failures** using legacy `.portal-alt1-cell` / `.portal-alt2-cell` fixtures while the current template uses `button[data-choice-button]`. This is a suspected obsolete test fixture, **not yet formally closed**; examine its original behavioral assertions against the current ETag/choice/submit contract and fix test isolation or any proven product defect before final pilot GO. Preserve the visually approved screen.
- **Event and free menu contexts:** deferred until after Kommun pilot; do not alter weekly publication model to add Event now.

**Documentation governance:** `docs/KOMMUN_1_1_LIVE_ACCEPTANCE.md` owns current status. `docs/roadmap.md` owns phase sequence only. `docs/ground_truth/*` locks architecture/requirements, and their older checkpoint tables are historical snapshots. The separate `docs/kommun-status-review-2026-10-30` and `handoff/*` branches were used as evidence; do not use them as current task queues.

---


## Historical status (October 2026 baseline)

TECHNICAL AUTOMATED GATE = GO

LIVE ACCEPTANCE GATE 01 — CUSTOMER + SITE = GO

LIVE PILOT ACCEPTANCE = PENDING

## Historical baseline

- branch: feat/planera-app-shell-2026-03-03
- HEAD: 04731895afc290b7df4e65bdc15146f2f2b69daa
- 2342 passed
- 15 skipped
- 0 failed
- 3 warnings

## Gate 01 — Clean Customer + Site Onboarding

Status: GO

Manually proven:

- new customer creation
- new site creation
- separate customer Admin login in Firefox
- correct tenant/site context
- clean customer without leaked demo data
- persistence across separate session

## Historical Gate 02 — Departments + Needs

Status: IN PROGRESS

Reached:

- Admin → Avdelningar → Create Department → Department Edit

Department Edit is currently classified as a HIGH UX area and is paused for challenger work before final pilot acceptance.

Gate 02 is not GO yet.

## Section A — Clean Customer E2E

- [ ] New tenant/customer
- [ ] New site/kitchen
- [ ] New departments
- [ ] Resident/current quantities
- [ ] Requirement groups/needs
- [ ] Specialkost
- [ ] Serving adaptations
- [ ] Department login
- [ ] Builder menu import
- [ ] Resolve/build menu content
- [ ] Publish
- [ ] Kitchen Weekview
- [ ] Portal same menu
- [ ] Portal menu choices
- [ ] Explicit submit
- [ ] Portal→Kitchen propagation
- [ ] Planera lunch
- [ ] Planera kvällsmat
- [ ] Planera dessert
- [ ] Production underlag
- [ ] Completion propagation
- [ ] Report
- [ ] Persistence after reload/login

## Section B — Data Truth Assertions

Record these locks:

- Published Builder menu = canonical menu truth
- Department menu choice = canonical choice truth
- Registered needs/current quantities = business truth
- Portal = input/experience layer
- Planera 2.0 = production engine
- Weekview = operational projection
- No manual sync between Portal and Kitchen
- No second production/menu/choice truth

## Section B2 — Product Direction Locks

### Department Edit information model

Current recommended conceptual grouping:

- AVDELNINGEN
  - name
  - residence/facility relationship
  - baseline resident count
  - internal Department.notes / Faktaruta
- BEHOV
  - registered production-relevant needs
  - primary requirement
  - additional deviations
  - quantities
- SERVERINGSANPASSNINGAR
  - serving add-ons / adaptations
- VECKOVARIATIONER
  - varying resident counts
  - other genuinely week/day-specific operational exceptions

Requirement-group is a backend/domain term only; normal Kommun admins should not need to learn that term in the final UI.

### Department Edit UX findings

- UX-13 HIGH: Department Edit lacks a clear mental model/hierarchy.
- UX-14 HIGH: Multiple independent save actions make save scope unclear.
- UX-15 HIGH: Specialkost and Registrerade behov overlap semantically in the UI even though they represent different domain concepts.
- UX-16 HIGH: Requirement-group terminology is too technical for normal Kommun admin.
- UX-17 MEDIUM/HIGH: Serveringstillägg is presented as a technical row editor instead of clear operational information.
- UX-18 MEDIUM: Department list provides weak operational differentiation/status.

### Menu choice direction

The menu-choice operational workflow should not primarily live inside Department Edit.

Preferred primary surface for Kommun 1.1:

- Admin → Menyval

MVP scope:

- choose/view a published week
- show all departments
- status per department: Klar, Delvis klar, Ej påbörjad
- simple filter/segmented control: Alla, Behöver åtgärd
- show the days where a real menu choice is required
- show the department's current choice
- allow admin to change a department's menu choice
- after save, return naturally to the overview

Deferred from Kommun 1.1:

- push/reminder sending
- choice analytics
- popularity statistics
- historical dashboards
- raw-material forecasts
- generic cross-vertical choice analytics
- new statistics engine

### Admin override technical gate

Product intent:

- An admin/kitchen change is authoritative.
- If Admin changes a department choice, the effective production choice must follow the admin decision.

Current implementation note:

- Portal and Admin currently write into the same canonical department_menu_choices truth.
- The current implementation does not yet preserve three separate persisted concepts for original Portal choice, Admin override, and effective choice.

This is an open technical gate and must be revisited before implementing Admin → Menyval at full scope.

## Section C — UI/UX Race

For every major screen capture record:

- route/screen
- screenshot/reference
- task user is trying to complete
- friction
- severity: BLOCKER / HIGH / MEDIUM / LOW
- recommended action
- accepted/fixed/deferred

Initial screens to inspect:

1. Customer creation / onboarding
2. Site/kitchen setup
3. Departments list
4. Department create
5. Department detail
6. Department edit

Known concern:

Department edit is known to be visually and interaction-wise messy and requires serious UX review.

Then:

7. Needs / requirement-group administration
8. Builder import
9. Builder unresolved flow
10. Dish editor
11. Component editor
12. Publish flow
13. Kitchen Weekview
14. Planera entry/day overview
15. Planera review
16. Produktionsunderlag
17. Department Portal Home
18. Department Portal Week
19. Reports

Accepted product privacy distinction:

- Department-facing structured fact area stays visible to unit_portal.
- Department.notes / internal Faktaruta is private and must never render to unit_portal.

The privacy defect on the old compatibility Portal week surfaces was closed in commit 04731895afc290b7df4e65bdc15146f2f2b69daa.

UX principle:

Do not redesign everything blindly. First walk the real task, then screenshot, then identify friction, then challenge or redesign only where justified.

Tablet/iPad-first remains a core acceptance lens.

## Section D — Release Blockers

Only BLOCKER and HIGH issues can stop pilot unless the project lead decides otherwise.

| ID | Area | Finding | Severity | Owner | Status | Evidence |
| --- | --- | --- | --- | --- | --- | --- |

## Section E — Release Exit Criteria

Kommun 1.1 may become final PILOT READY only when:

- clean-customer chain passes
- lunch/kvällsmat/dessert Planera requirement is verified or an explicit product decision is made
- Portal and Kitchen show the same canonical publication and choices
- tenant and department scoping is proven
- no blocker-level UX failure remains
- accepted UX fixes are regression-tested
- final automated suite is green after any product changes
- pilot candidate HEAD is frozen/tagged

Current release sequence:

1. Gate 02 — Departments + needs
2. Department Edit UX challenger
3. Admin menu-choice technical semantics gate
4. Thin Admin → Menyval overview if implementation remains small
5. Continue clean-customer live E2E: published menu, Portal choices, Kitchen propagation, Planera, Produktionsunderlag, completion, Reports, persistence/relogin
6. UX race fixes
7. Final regression
8. Freeze/tag Kommun 1.1
9. Offshore 1.0

## Notes

This document is the working ledger for the live acceptance phase and the UX race.

The live acceptance status above reflects the manually proven customer/site onboarding gate and the currently paused Department Edit / department needs work.
