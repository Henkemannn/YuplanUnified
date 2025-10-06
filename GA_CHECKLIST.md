# GA Checklist (Yuplan v1.0.0)

## Legend
- [ ] = Pending
- [x] = Completed / Verified

---
## 1. Pre-release
- [ ] All feature tickets in milestone closed or explicitly deferred
- [ ] RELEASE_NOTES_v1.0.0.md reviewed by engineering + product
- [ ] Version/tag agreed (`v1.0.0`)

## 2. Security
- [ ] CodeQL workflow green (no new high / critical alerts)
- [ ] `pip-audit` zero vulnerabilities (or documented allowlist)
- [ ] SBOM (`sbom.json`) generated & archived
- [ ] JWT secrets rotated / verified (primary + any staged rotation secrets present)
- [ ] CSRF production mode verified (sample POST with and without header → 403 on missing)
- [ ] Security headers validated (curl + check: HSTS, X-Frame-Options, Referrer-Policy, Permissions-Policy, X-Content-Type-Options)
- [ ] CORS allow-list matches deployment domains
- [ ] Rate limits configured (brute force login, admin endpoints) & tested

## 3. Observability
- [ ] Dashboards imported (`observability/dashboards.json` adapted to stack)
- [ ] Alerts configured: p95 latency, 5xx rate, 429 rate (warn thresholds per docs)
- [ ] OTEL exporter configured OR decision to defer documented
- [ ] Baseline metrics captured (24h pre-GA snapshot) for regression comparison
- [ ] Support endpoints reachable (/admin/support/ & /admin/support/ui)
- [ ] ETag responses working (two consecutive GETs → 304) for `/kommun/rapport` & `/kommun/veckovy`

## 4. Documentation
- [ ] `SECURITY.md` reviewed & up to date
- [ ] `OBSERVABILITY.md` updated with domain events section
- [ ] `README` badges (coverage, build) current
- [ ] Deprecations listed & timelines noted
- [ ] GA_CHECKLIST.md committed

## 5. QA / Testing
- [ ] Full test suite green (≥ 250 tests) in main branch
- [ ] Strict subset (CSRF) job green (pytest -m "not csrf_legacy")
- [ ] Manual smoke: login, create note, list tasks, export endpoints
- [ ] Negative tests: invalid JWT (rejected), missing CSRF header (blocked), exceeded rate limit (429 + Retry-After)
- [ ] OpenAPI spec validated (CI artifact present)

## 6. Release Steps
- [ ] Freeze merges (except release critical fixes)
- [ ] Bump version constant / metadata (if maintained) to 1.0.0
- [ ] Tag commit: `git tag -a v1.0.0 -m "Yuplan v1.0.0 GA" && git push --tags`
- [ ] Publish GitHub Release using `RELEASE_NOTES_v1.0.0.md`
- [ ] Deploy to production environment
- [ ] Run DB migrations (`alembic upgrade head`)
- [ ] Warm caches / prime any critical endpoints (optional)

## 7. Post-release Monitoring (First 24h)
- [ ] p95 latency stable (within +20% of pre-release baseline)
- [ ] 5xx error rate < 1%
- [ ] 429 rate within acceptable envelope (<5% overall)
- [ ] `security.jwt_rejected_total` anomaly check (no unexpected spike)
- [ ] `security.csrf_blocked_total` baseline understood (expected noise only)
- [ ] No unplanned elevation in brute-force lockouts
- [ ] Support logs show no recurring WARN pattern
- [ ] Confirm backups / retention jobs ran successfully (if applicable)

## 8. Follow-ups (Post GA Planning)
- [ ] Remove `csrf_legacy` markers (incrementally) & enable strict mode by default
- [ ] Harden CSP (restrict script origins) & add Subresource Integrity
- [ ] Add real data to `/kommun/rapport` and `/kommun/veckovy`
- [ ] Expand domain events (attendance_submit, meal_log, task_complete)
- [ ] Add auto-refresh to support UI (if not already merged)
- [ ] Evaluate RS256 or JWKS public key distribution for JWT (longer-term)

---
**Done criteria for GA:** All mandatory boxes in sections 1–6 checked; Section 7 monitoring started with no blocker anomalies after 24h.
