# SECURITY_SETUP.md — Yuplan

Syfte: Skydda upphovsrätt och förhindra kodläckor.
Ägare: Henrik Jonsson (Yuplan).
Statusmål: Privat repo, stark åtkomstkontroll, juridiska skyddstexter, CI/sekretess på plats.

## 0) Snabbstatus (frivilligt)
Lokal kontroll av uppenbara hemligheter i senaste 50 commits (grovt filter):

```pwsh
git log -50 -p | Select-String -Pattern '(?i)(api[_-]?key|secret|token|password|pwd|client[_-]?secret)' || Write-Host "✅ No obvious secrets in last 50 commits"
```

## 1) Repo-synlighet (MANUELLT i GitHub)
- Settings → General → Danger Zone → Change repository visibility → Private. Bekräfta.

## 2) Åtkomstkontroll (MANUELLT i GitHub)
- Settings → Collaborators & teams → Ta bort alla som inte absolut behöver åtkomst.
- Endast Read/Write. Undvik Admin.
- Aktivera 2FA på GitHub-kontot (kräv gärna 2FA i org: Settings → Authentication security).

## 3) Branch-protection (MANUELLT i GitHub)
- Settings → Branches → Add rule → Pattern: master
  - Require pull request before merging
  - Require approvals: 1
  - Require status checks to pass (Ruff, mypy, tests)
  - Require branches to be up to date
  - Include administrators
- (Upprepa för dev om du använder den.)

## 4) Hemligheter & CI-secrets (MANUELLT i GitHub)
- Settings → Secrets and variables → Actions
- Ta bort oanvända secrets. Lägg bara in nödvändiga nycklar.
- Använd aldrig hemligheter i kod/commits. Lägg i secrets + läs via env vars.

## 5) .gitignore (känsliga filer)
Tillägg (nu applicerat i repo):
```
.env
.env.*
secrets.*
credentials.*
coverage/
```

## 6) Juridiska skyddstexter
Filer skapade i repo:
- LICENSE (All Rights Reserved)
- COPYRIGHT.txt
- TRADEMARK.md
- NOTICE.txt
- .github/SECURITY.md

README uppdaterad med Confidentiality Notice.

## 7) CI-begränsning & kvalitetsgrindar
- .github/workflows/quality.yml (kör Ruff + mypy på master/dev när repo är privat)

## 8) Pre-commit
- .pre-commit-config.yaml finns. Kör lokalt:
```pwsh
pip install pre-commit
pre-commit install
```

## 9) Staging/demo-säkerhet
- docs/STAGING_SECURITY.md (lösenordsskydd, NDA, separata secrets, no-index)

## 10) NDA
- docs/NDA_TEMPLATE.md (kort mall)

## 11) Slutlig checklista
- Repo Private
- Collaborators rensade, minimerade rättigheter
- Branch protection aktiv för master (PR, 1 approval, status checks, include admins)
- Secrets rensade/uppdaterade, inga nycklar i kod
- .gitignore blockerar .env, databaser och secrets.*
- LICENSE, COPYRIGHT.txt, TRADEMARK.md, NOTICE.txt, SECURITY.md skapade
- README har Confidentiality Notice
- CI-workflow begränsad till master/dev och kör kvalitet (Ruff, mypy)
- Pre-commit på plats
- Staging är lösenordsskyddad och delas endast efter NDA

## 12) Underhåll
- Kvartalsvis säkerhetsgenomgång: åtkomster, secrets, CI, beroenden.
- Rotera tokens/secrets minst var 6:e månad.
- Dokumentera vem som har access och varför (audit-logg).

Kontakt: henrik@yuplan.se  
© 2025 Henrik Jonsson — All Rights Reserved
