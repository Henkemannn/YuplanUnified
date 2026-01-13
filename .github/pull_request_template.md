## Summary

ops(deploy): v0.4 container & staging-ready (Docker, healthz, env, guides)

## What changed

- Dockerfile (Python slim, non-root) running gunicorn on port 8080
- gunicorn.conf.py (timeout=60, loglevel=info)
- Health endpoint: GET /healthz -> {"status":"ok"}
- .env.example with DB/secret/feature flags
- tools/init_db.py (alembic + minimal seed), tools/seed_weekview.py (dev-only)
- fly.toml with /healthz healthcheck
- CI: pytest + docker build
- README: staging deploy guide + smoke tests

## DoD

- [x] Dockerfile + gunicorn + /healthz på plats
- [x] .env.example och README-guide
- [x] tools/init_db.py (+ valfri seed_weekview.py)
- [x] Fly.io manifest klart
- [x] CI kör tests + docker build
- [x] Inga funktionella ändringar i app-logik

## Notes

Fly-only staging for v0.4; Render manifest can be added later if we need a second environment.
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
