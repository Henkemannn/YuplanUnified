# 🚧 v1.1 roadmap kickoff

Goal: Build on v1.0.0 GA by expanding strict typing, solidifying telemetry, and cleaning up importers—without breaking contracts.

## 🧩 Typing expansion
- [ ] Re-enable strict pocket for `core.auth` (remove ignore and fix trivial annotations)
- [ ] Re-enable strict pocket for `core.ui_blueprint` (stabilize DTO/view-models)
- [ ] Gradually remove `ignore_errors` for `core.*_api` (one blueprint per PR)
- [ ] Introduce `ParamSpec` / `Concatenate` for decorators to eliminate untyped-call noise
- [ ] Promote `warn-return-any` globally once API handlers are clean

## 📈 Telemetry & Observability
- [ ] Decide on OTEL exporter (OTLP HTTP/gRPC) and configure minimal pipeline
- [ ] Dashboards: p95 latency, 5xx rate, 429 rate, jwt_rejected_total, csrf_blocked_total
- [ ] Alerts: thresholds for error rate & latency (warn/crit)
- [ ] Expand domain metrics for import/export throughput and admin limits

## 📦 Importers & Contracts
- [ ] Consolidate importer modules under strict pocket (CSV, DOCX)
- [ ] Deprecate legacy importer path; document replacements in README
- [ ] Add OpenAPI examples for import payloads and errors
- [ ] Strengthen 415/422 tests (mismatched content-type, invalid schema)

## 🧪 CI & Developer Experience
- [ ] Make pre-commit mandatory in CI (verify `pre-commit run -a`)
- [ ] Quality workflow gates: Ruff, mypy, tests (fail fast on new violations)
- [ ] Add a quickstart for strict pocket expansion (snippet + examples)
- [ ] Optional: add coverage summary badge artifacts

## 🚀 Delivery
- [ ] Milestone planning and triage labels ready
- [ ] Draft v1.1 release notes template
- [ ] Track contract changes via baseline diff (no breakage; additive only)

Notes:
- Keep PRs small; one module per PR when enabling strict.  
- Prefer `TypedDict` / `Protocol` adapters over deep refactors.  
- Reuse rate limit/CSRF RFC7807 helpers to keep error model consistent.
