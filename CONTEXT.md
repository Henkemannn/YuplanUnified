# Project Context (Living Document)

Short, durable facts that survive chat resets. Keep updated as we learn.

## Invariant Facts
- Unified admin shell classes: `.ua-root`, `.ua-shell`, `.ua-sidebar`, `.ua-nav`.
- Legacy hooks must remain in DOM for tests (e.g., `.admin-sidebar`, `.sidebar-nav`, `.admin-nav`). We visually hide legacy duplicates under unified shell.
- Admin base template: `templates/ui/unified_admin_base.html` renders `admin_main` block.

## UI Rules (Sidebar & Duplicates)
- Show only UA nav under unified shell:
  - CSS: `.ua-root .ua-sidebar.admin-sidebar > nav:not(.ua-nav) { display: none !important; }`
- Keep legacy footer/user-info hidden: `.admin-sidebar .sidebar-footer, .admin-sidebar .user-info { display: none !important; }`
- Dashboard readability: `.ua-topbar-title`, `.dashboard-heading`, `.dashboard-subtitle` use brighter colors.

## Auth Contracts (from tests)
- Endpoints: `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`.
- Login JSON: `{ ok: true, access_token, refresh_token, token_type: "Bearer", expires_in, csrf_token }`.
- Refresh rotates token; reusing old refresh -> `401 invalid token`.
- CSRF cookie: name `csrf_token`; `SameSite=Strict`, `HttpOnly=false`; `Secure` off in tests.
- Unauthorized/Forbidden: legacy envelope `{error, message}`, 401 message normalized to `authentication required`.
- Bearer header overrides session on protected routes.

## Env Flags
- `STAGING_SIMPLE_AUTH=1` enables demo role login UI (non-testing only).
- `DEV_CREATE_ALL=1` (or `YUPLAN_DEV_CREATE_ALL=1`) can auto-create schema in dev for bootstrap tasks.
- `DEV_CSRF_LAX=1` sets CSRF cookie `SameSite=Lax` in non-testing local runs.

## Rate Limiting (login)
- Window: 300s; max failures: 5; lock: 600s; returns 429 with `Retry-After`.

## Testing Notes
- Some tests rely on session cookies (not just Bearer); we persist `session['user_id']` on login.
- Legacy selectors remain in DOM for tests even if visually hidden.

## Recent Decisions
- Unified admin sidebar shows only UA nav; legacy `_admin_sidebar.html` hidden under unified shell.
- Dashboard should prioritize KPIs, tasks, recent activity over duplicating menu links.

## Pinned Selectors (quick ref)
- Keep: `.ua-nav`
- Hide under UA: `.admin-nav`, `.sidebar-nav`
- Welcome title selector: `.ua-topbar-title`

