# Yuplan v1.0.0 (GA)

## Highlights
- General Availability release establishing a hardened, observable, and upgradeable platform baseline.
- Consistent error contract via RFC 7807 for security/CSRF problems; legacy JSON preserved where required.
- Secure authentication stack: JWT with multi-secret rotation, strict claim validation (iss, aud, nbf, iat, exp, max_age, future iat guard) and detailed rejection metrics.
- Environment-aware CSRF (test bypass vs production enforcement) + opt-in strict rollout path.
- Feature-flagged modular architecture prepared for incremental enablement.
- Lightweight domain event telemetry (`yuplan.events_total`) and admin support console for rapid pilot feedback.

## Security & Compliance
- `SECURITY.md` documents: JWT rotation model, CSRF double-submit, cookie policy (Secure + SameSite), CORS allow-list, security headers (HSTS, CSP placeholder, X-Frame-Options, Referrer-Policy, Permissions-Policy), rate limiting, and deprecation process.
- JWT hardening: enforced issuer/audience, max token age, future iat rejection, multi-secret validation sequence, deterministic `kid`.
- CSRF: production double-submit (cookie + header) and origin fallback; metrics on denials (`security.csrf_blocked_total{reason=...}`).
- Metrics for security posture: `security.jwt_rejected_total{reason}`, `security.csrf_blocked_total{reason}`, and `http.405_mapped_to_404_total` (tracks method sanitization mapping).
- Brute-force login rate limiting with `Retry-After` header and test coverage.
- Rate limit registry + per-endpoint/admin limits.
- Code scanning & supply chain:
  - CodeQL (expected green before release)
  - `pip-audit` enforced in CI (0 known vulnerabilities requirement)
  - CycloneDX SBOM generation (`sbom.json`) published as CI artifact.
- Pre-commit integration (format/lint/type) ensuring consistent code hygiene.

## Observability
- OpenTelemetry (optional) counters for JWT rejections, CSRF denials, 405→404 mappings, domain events.
- Structured JSON request logging (includes `request_id`, tenant/user, path, status, latency ms) + correlation with audit events.
- Admin Support endpoints:
  - `/admin/support/` (JSON) summarizing version, env, top events and recent WARN logs.
  - `/admin/support/ui` (HTML) interactive view (export + lookup) with auto-refresh (optional).
- Domain event counter (`yuplan.events_total`) with panels suggested: rate per minute & top avdelningar 24h.
- ETag + 304 caching for `/kommun/rapport` and `/kommun/veckovy` placeholders (foundation for low-latency UX).
- `observability/dashboards.json` vendor-agnostic starter (latency p95, 5xx rate, 429, RPS, registration panels).
- RFC 7807 adoption aligns error correlation via `instance` ↔ `request_id`.

## Developer Experience
- Clear app factory & modular blueprint registration.
- Consistent pagination & deprecation alias responses (notes/tasks legacy keys preserved with deprecation warnings).
- Automated test matrix for gradual CSRF hardening (`STRICT_CSRF_IN_TESTS` + `csrf_legacy` marker).
- Central cookie helper, JWT utilities, telemetry module, support logging ring buffer.
- Comprehensive test suite (>250 tests) covering auth, security, rate limits, OpenAPI spec, pagination, and telemetry.

## Breaking Changes
- None intentionally introduced in v1.0.0.
- Legacy behaviors retained behind environment/test gating (CSRF leniency, deprecated alias fields).

## Deprecations
- Legacy note/task response alias fields flagged via deprecation headers (target removal post v1.x with notice).
- Non-strict test-only CSRF bypass slated for removal once all tests migrate off `csrf_legacy` marker.
- Placeholder legacy UI endpoints (`/kommun/*`) subject to replacement by unified views.

## Upgrade Notes
1. Pull latest code: `git fetch --tags && git checkout v1.0.0` (after release tag created).
2. Environment: ensure required env vars exist (see `.env.example` if provided / config docs):
   - `DATABASE_URL`
   - `JWT_PRIMARY_SECRET` (and rotation secrets if any)
   - `CORS_ALLOW_ORIGINS` (comma-list) if differing from defaults
   - `STRICT_CSRF_IN_TESTS` (only for CI/test runs)
3. Database:
   - Run migrations: `alembic upgrade head` (schema includes audit + feature flags + token models as applicable).
   - If coming from pre-migration dev DB, rebuild or apply `0001_init` → head.
4. Optional OTEL:
   - Install/exporter packages; set `OTEL_EXPORTER_OTLP_ENDPOINT` etc. Without them metrics gracefully fallback.
5. CI expectations:
   - CodeQL passes, `pip-audit` zero vulns, SBOM artifact present.
6. Caching considerations:
   - Downstream proxies should honor ETag on `/kommun/rapport` & `/kommun/veckovy` (max-age=60); adjust if upstream aggregator refresh differs.
7. Rollout safety:
   - Start with low traffic slice; monitor p95 latency, 5xx%, 429 rate, and `security.jwt_rejected_total` spikes for 24h.

## Known Issues / Limitations
- Placeholder `/kommun/rapport` & `/kommun/veckovy` logic returns synthetic data until real aggregation integrated.
- CSRF strict mode not yet enforced across whole test corpus (`csrf_legacy` marker phase-in ongoing).
- No persistent metrics store included (OTEL optional; local counters reset on restart).
- Support UI refresh currently manual (auto-refresh optional patch available / planned).
- CSP presently minimal (tightening policy pending asset inventory).

## How to Upgrade (Concise)
1. Update code & dependencies: `git pull && pip install -r requirements.txt`.
2. Run migrations: `alembic upgrade head`.
3. Set/verify secrets + env (JWT, DB, CORS, OTEL if used).
4. Restart application / redeploy containers.
5. Monitor key metrics (latency, 5xx, jwt_rejected_total, csrf_blocked_total) for anomalies during first hour.
6. Begin incremental CSRF strict migration (remove `csrf_legacy` markers) post-stabilization.

---
Thanks for piloting Yuplan! Please file issues for any post-GA regressions or security findings.
