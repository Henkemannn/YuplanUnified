Release 0.3.0 — Branding, Menyval, CSV export/preview, PDF

Highlights
- Branding & PWA: Added manifest.webmanifest, favicon, apple-touch, and icons; linked in templates with cache-busting. Correct MIME served via explicit routes.
- Static reliability: Explicit Flask routes for /manifest.webmanifest and /favicon.ico (proper caching + MIME). Safari pinned tab added. Optional WhiteNoise static fallback wired for robustness.
- Pass B — Menyval: ETag/If-None-Match behavior, idempotent updates, weekend 422 rule; focused smoke script for /menu-choice.
- Pass C — Report CSV export: Client CSV export with UTF‑8 BOM, stable headers and totals fallback.
- Pass D — PDF print: Client print flow using existing styles; accessible output.
- Pass F — Admin CSV import (preview): Client-only parsing (BOM stripping, delimiter autodetect ';' or ',', RFC4180 quotes), mapping UI, preview + week summary; unit tests. Gated in prod.

Ops/Deploy
- Staging is green: /, /demo, manifest, favicon, icon-192 and /menu-choice smoke passed. CSRF included in smoke writes.
- Feature flags: Menyval ON; CSV export/PDF ON; CSV import preview OFF in prod (ON in staging).
- No DB migrations in this cut; release is app-level.

Notes
- CSRF: X-CSRF-Token cookie/header required on admin/menu writes; demo and smokes updated accordingly.
- Rollback: `flyctl releases -a yuplan-unified-prod` → revert to previous release if needed.
- Tag: v0.3.0

Links
- Staging app: https://yuplan-unified-staging.fly.dev/
- Tag: https://github.com/Henkemannn/YuplanUnified/releases/tag/v0.3.0
