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
