Status: LOCKED
Last reviewed: 2026-10-10

# User Provisioning and Authentication Flow

## Purpose
This is Yuplan Ground Truth for user provisioning, scope binding, login routing, account lifecycle, and credential revocation. It is platform-level and must be reusable by Kommun, Offshore, and future products.

Core rule: **one shared User/auth model; business modules bind that user to the correct operational scope.** REUSE-BEFORE-BUILD applies. Do not create vertical-specific authentication systems.

## Canonical A-Z flow
Tenant -> Site -> operational scope -> User -> role/scope binding -> login -> correct Yuplan surface -> account lifecycle.

For Kommun:
1. Tenant and Site exist.
2. Departments are created/configured.
3. Tenant Admin opens user management.
4. Admin creates Admin, Kitchen, or Department user.
5. Yuplan stores the identity in the shared User model.
6. Scope is bound by user type.
7. Initial credentials are supplied.
8. User logs in through shared auth.
9. Yuplan resolves tenant/site/department from server-side identity.
10. User is routed to the correct surface.
11. Authorization prevents cross-tenant/site/department escape.
12. Change/reset/logout/deactivate/delete use the shared account lifecycle.

## Current shared user model
Relevant current User state includes:
- tenant_id
- username
- email
- password_hash
- role
- full_name
- is_active
- department_id
- unit_id
- refresh_token_jti
- auth_version
- must_change_password
- updated_at
- deleted_at

Role is single-valued.

There is no canonical ORM User.site_id field.

### Site/scope binding
- Department Portal user: users.department_id -> departments.site_id. Tenant Admin may choose only Departments in the authenticated tenant + active authorized Site; same-tenant cross-site and foreign-tenant bindings fail closed.
- Kitchen/admin site access: current pilot code uses existing site-binding infrastructure, primarily kitchen_user_sites; current 1.0 contract is one Kitchen user -> one Site with user_id as the unique key. Older DB variants may still have guarded users.site_id compatibility.
- Superuser is not restricted to one operational site in the same way.

The historical users.site_id compatibility path is not the future canonical model.

## Product user types

### Admin
Tenant/site administration. Expected landing: Admin application.

### Kitchen
Operational kitchen user. Expected landing: /ui/kitchen. Scope: tenant + site binding. Existing kitchen/cook compatibility details must not become product UX.

### Department
Kommun external unit user. Active role: unit_portal. Expected landing: /ui/portal/department/week. Scope: users.department_id; site derives from Department. Normal Department users cannot override Department identity.

### Superuser
Yuplan/platform bootstrap and support. Not an ordinary tenant user type.

## Current provisioning surfaces
Canonical tenant-facing browser surface:
**Admin -> Användare -> + Skapa användare**

Canonical route:
- /ui/admin/users

Product choices exposed to tenant Admin:
- Admin
- Kök
- Avdelning

Current behavior:
- no product-level technical username field; tenant-facing creation derives the internal username from normalized email;
- Admin reuses the current pilot-safe tenant/site scope;
- Kök reuses the existing one-user/one-site kitchen binding and active authorized Site;
- Avdelning selects exactly one already-registered Department from the current tenant + active Site; site derives from Department;
- create/edit/deactivate/reset are exposed through the unified surface;
- inactive users currently have no reactivation control in the browser UI.

Compatibility:
- /ui/admin/kitchen-users may remain as a legacy compatibility route, but is not the primary tenant navigation surface.
- Systemadmin customer/site bootstrap remains a separate platform concern for initial site/admin provisioning.
- /admin/users remains the existing JSON API contract with canonical API role semantics.

Checkpoint:
`f23f96dc690f3c7933bdf5b201b0592e06c409e5`
`feat(admin): unify tenant user management`

This consolidates existing capabilities. It is not a new auth system. Do not build a third provisioning flow.

## Department authorization contract
For unit_portal:
authenticated User -> tenant -> department_id -> Department -> site -> Department Portal.

Locked:
- users.department_id is the normal Department identity anchor.
- client query/path values do not override a normal Department user's scope.
- missing/invalid Department binding fails closed.
- tenant/site mismatch fails closed.
- Department A cannot act as Department B.
- support/admin override is only for explicitly authorized support workflows.

## Login routing
- Admin -> Admin
- Kitchen/cook compatibility roles -> Kitchen
- unit_portal -> Department Portal
- Superuser -> Systemadmin

Routing follows authenticated server-side identity.

## Account-state security contract — CLOSED
Checkpoint:
5b301e8d4fdf184e340c449953b739fc1c8cafd9
fix(auth): block inactive and deleted accounts

Authentication eligibility requires:
is_active == True
AND
deleted_at IS NULL

This is enforced centrally for login, refresh, and protected authenticated requests before normal role authorization. No normal production role bypasses this state.

## Authentication artifacts
Yuplan currently uses:
- Access JWT: short-lived (currently about 10 min), client-held, protected requests reload User and check account state.
- Refresh JWT: longer-lived (currently about 14 days), with users.refresh_token_jti as the server-side replay/revocation anchor.
- Flask/browser session: signed client-side session state; protected requests reload current User and check account state.

## Credential revocation architecture — CLOSED
The revocation census proved refresh_token_jti is sufficient for refresh-token revocation but does not invalidate old browser sessions or access JWTs after credential change/reset.

Checkpoint:
129d2b8d4ea38a479c754866bb1bf1aa08e8907b
fix(auth): revoke stale credentials after password changes

Implemented platform primitive:
**auth_version**

Target contract:
- integer, non-null, backfill/default 1;
- increment exactly once when credentials are changed/reset;
- browser session stores the auth_version it was issued under;
- access JWT carries the auth_version it was issued under;
- protected auth compares presented version with current User.auth_version;
- missing legacy version fails closed and requires a new login;
- refresh_token_jti remains the refresh replay/revocation primitive.

### Admin reset target
After Admin resets User A:
- old credential secret fails; new one works;
- auth_version increments;
- refresh_token_jti is invalidated;
- old browser session/access/refresh artifacts fail;
- other users are unaffected.

### Self-service credential change target
After successful change:
- current credential must be verified;
- auth_version increments;
- refresh_token_jti is invalidated;
- current browser session is cleared;
- user logs in again;
- older sessions/access/refresh artifacts fail.

For Yuplan 1.0, requiring a new login is preferred over special logic to preserve the current session.

### Logout target
Normal logout must:
- clear the local Flask/browser session;
- invalidate the matching refresh token/JTI when present.

Current Truth: this credential-revocation contract is implemented and checkpointed at `129d2b8`.

## Initial credential and first-login policy
Current creation flows accept an initial credential and store only its hash. A self-service change route exists.

Current Truth — CLOSED at checkpoint:
`9873ca3cbec762d752660c84b3f11e87a3e193ed`
`fix(auth): require password change for temporary credentials`

Implemented:
- `must_change_password` boolean state;
- migrated existing users default/backfill `false`;
- admin-issued initial credentials set it `true`;
- admin/systemadmin password reset sets it `true`;
- forced-change users are restricted to the password-change flow and logout until they choose a new password;
- the forced first-login page is a standalone auth gate without normal Admin/Kitchen/Department App Shell navigation;
- successful self-service password change clears the flag, increments `auth_version`, clears refresh JTI, clears the browser session, and requires login again;
- normal role-specific Yuplan shell appears only after successful password change + re-login;
- inactive/deleted account-state checks remain prior authority.

Still not implemented:
- complete forgot-credential token/email recovery.

Locked separation:
- `must_change_password` = required user action/state.
- `auth_version` = revocation generation.
Do not overload one field to do both jobs.

## Account lifecycle
Direction:
Create -> authenticate -> edit identity/scope as authorized -> credential change/reset -> deactivate/reactivate -> soft-delete where applicable.

Known UX gap: reactivation exists below the UI but is not consistently exposed in browser user management.

## Clean-customer acceptance flow
Before Kommun pilot freeze, prove in a real browser on a clean customer/site:

Admin:
1. Log in.
2. Open Användare.
3. Create Kitchen user.
4. Create Department user for a real Department.
5. Supply initial credentials.
6. Log out.

Department:
7. Log in with the admin-issued temporary credential.
8. If `must_change_password=true`, complete the standalone password-change auth gate and re-login.
9. Reach only the bound Department Portal.
10. Cannot access another Department.
11. See published menu.
12. Make allowed menu choice.
13. Submit week.

Kitchen:
14. Log in.
15. Land in Kitchen.
16. See the Department's propagated menu-choice state downstream.

Lifecycle:
17. Admin resets or deactivates the Department user.
18. Old auth artifacts follow the locked revocation/account-state contract.
19. Recovery/reactivation is understandable enough for pilot operations.

## Implementation sequence
1. Account-state guard — CLOSED at 5b301e8.
2. Credential revocation/auth_version — CLOSED at `129d2b8`.
3. First-login policy — CLOSED at `9873ca3`.
4. Unified Admin -> Användare UX — CLOSED at `f23f96d`.
5. Identity/browser proof for Department creation -> standalone forced password change -> re-login -> correct Department Portal scope — CLOSED during the 33A acceptance work leading to `f23f96d`.
6. Clean-customer A-Z Kommun acceptance continues with the published-menu -> Department choice -> Kitchen -> Planera -> Produktionsunderlag chain.
7. Pilot freeze.

## Explicitly parked beyond first pilot
- MFA
- SSO/SAML/OIDC enterprise onboarding
- invitation-email engine
- full forgot-credential email/token delivery
- multi-role users
- complex multi-site assignment UI
- identity-provider administration
- device/session management dashboard
- general token denylist
- enterprise IAM console

## Guardrails
- REUSE-BEFORE-BUILD.
- One canonical User/auth model.
- No Kommun-only or Kitchen-only authentication system.
- Scope derives from authenticated server-side identity, never trusted client query parameters.
- Department scope is Kommun-specific adapter scope, not generic platform identity.
- auth_version is platform-level.
- Security rules live in central auth seams, not page-by-page guards.
- UX consolidation must not mutate established tenant/site/Department authorization contracts.
