# Staging access and demo

App: https://yuplan-unified-staging.fly.dev/

## Simple auth (staging-only)
Simple auth is enabled via env var and sets a demo cookie-based session.
- Enable: set secret `STAGING_SIMPLE_AUTH=1` and deploy; the app auto-enables `ff.admin.enabled`.
- Login: POST /auth/login with a JSON body, e.g. `{ "role": "admin" }`.
- Logout: POST /auth/logout

When simple auth is active, you can use the built-in demo UI at `/demo` (see DEMO_UI below) to:
- List departments for a site and exercise ETag/If-None-Match
- Update a department with If-Match + CSRF
- Inspect and toggle Alt2 flags for a week with If-Match

## CSRF on writes
All modifying requests must include `X-CSRF-Token` with the value from the `csrf_token` cookie.
- The token is set on first visit or after login.
- Example (curl on Windows PowerShell requires careful quoting):
  - Use the PowerShell smoke: `pwsh -File scripts/smoke.ps1 -BaseUrl https://yuplan-unified-staging.fly.dev -SiteId <SITE> -Week 51`

## Scripts
- Login: `pwsh -File scripts/login.ps1 -BaseUrl https://yuplan-unified-staging.fly.dev`
- Smoke: `pwsh -File scripts/smoke.ps1 -BaseUrl https://yuplan-unified-staging.fly.dev -SiteId <SITE_ID> -Week 51`

Makefile convenience targets (if pwsh is available):
- `make login-ps`
- `make smoke-ps`

## Demo UI env guard
The demo UI is disabled by default and only intended for staging.
- Enable: set secret `DEMO_UI=1` and deploy
- Disable: unset the secret and redeploy

## Disable after demo
Unset or remove `STAGING_SIMPLE_AUTH` when the demo period is over and redeploy. Admin endpoints will then require real auth and features.
