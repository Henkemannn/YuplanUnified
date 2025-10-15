<!-- Suggested title: Superuser UI RC1: tokens, login, dashboard + e2e -->

## Summary

Superuser UI RC1: tokens (light/dark + ocean/emerald), login (Problem Details, a11y),
dashboard-skelett + kopplad data (KPI, events, health).

E2E i CI (Playwright) + test‑isolering för feature flags.

## Changes

- superuser_api: GET /summary, GET /events, GET /health (no‑store, RFC7807, superuser‑guard)
- dashboard.html/js: render KPI/events/health; quick actions till /tenants/new, /feature-flags, /audit
- login: a11y/fel‑UX; redirect beroende på roll
- CI: e2e.yml, retries + artifacts
- Bootstrap: ensure_bootstrap_superuser uppdaterar/skapare superuser idempotent

## How to test

1) Seed superuser (env: SUPERUSER_EMAIL/SUPERUSER_PASSWORD). Aktivera inline_ui.
2) /ui/login → felruta & fokusflöde → logga in → redirect /superuser/dashboard.
3) Verifiera: KPI ≠ “—”, events (lista eller tomt state), health‑badges OK.

## Acceptance

- [ ] KPI visar riktiga tal inom ~500ms (mock OK)
- [ ] Events visar lista eller tomt state korrekt
- [ ] Health‑badges visar OK/FAIL
- [ ] E2E Playwright gröna

## Security/guards

- [ ] Superuser‑guard på alla `/api/superuser/*`
- [ ] Feature‑flag guard dokumenterad (test‑only remove, prod no‑op)
- [ ] Inga inline JS/CSS; CSP fortsatt grön
- [ ] Cache‑Control: no‑store på känsliga endpoints

## Artifacts

- Actions: Playwright report/trace/video som artifacts

## Follow‑ups (create issues post‑merge)

- E2E för health‑badges & events med data
- POST flaggtoggle m/ CSRF + audit
- Konsolidera `require_roles` (auth vs app_authz)
- Riktiga källor för `modules_active` på sikt

## PR checklist

- [ ] README + `docs/architecture` uppdaterade (API + flöde)
- [ ] CHANGELOG-post med UI/API + e2e
- [ ] CI grönt (unit + e2e)
- [ ] Secrets/creds inte hårdkodade
- [ ] Screenshots upplagda: `/ui/login` (light/dark, ocean/emerald) + dashboard (en av varje räcker)
## Ändringar
Kort sammanfattning av vad PR:en gör. Lista gärna moduler / filer med större påverkan.
﻿# Beskrivning
<!-- Kort vad som ändras och varför -->

## Typ av ändring
- [ ] Feature
- [ ] Bugfix
- [ ] Docs
- [ ] Security/Hardening
- [ ] CI/CD
- [ ] Other

## Checklista (måste vara ✓ innan merge)
**Kvalitet**
- [ ] Tests gröna lokalt
- [ ] Pre-commit (ruff/mypy) körd: `pre-commit run --all-files`
- [ ] Täcker nya/ändrade kodvägar med tester
- [ ] Coverage ej försämrad märkbart

**Säkerhet**
- [ ] CodeQL grönt i PR
- [ ] `pip-audit` (CI) = **0** kända sårbarheter
- [ ] Inga hemligheter i diffen (secrets scanning)

**Observability**
- [ ] OTEL-metrics/loggar rimliga för nya vägar
- [ ] Dashboards/alerts påverkas ej negativt (eller uppdaterade vid behov)

**API & Docs**
- [ ] RFC7807 följs för fel
- [ ] OpenAPI uppdaterad vid kontraktsförändring
- [ ] README/SECURITY/OBSERVABILITY uppdaterad vid behov
- [ ] Problems-katalogen (**docs/problems.md**) uppdaterad om nya problemtyper

**Frontier (om tillämpligt)**
- [ ] CSRF: skrivande endpoints accepterar **double-submit** + Origin-kontroll
- [ ] CORS: ingen ny wildcard; allowlist uppdaterad vid behov
- [ ] Rate limit: 429 + `Retry-After` korrekt

## GA-relaterat (bockas i release-PRs)
- [ ] Länk till **RELEASE_NOTES_vX.Y.Z.md**
- [ ] **GA_CHECKLIST.md** genomgång (Pre-release, Security, Observability, Docs, QA)
- [ ] Badge/metadata uppdaterad vid behov

## Test & verifikation
<!-- Hur verifierades ändringen? Lägg gärna med manuell testnotering / screenshots -->

## Övrigt
<!-- Risker, rollbacks, migrations, mm. -->

Commit
