### Alt2: portal day view sparar site-scope korrekt

- Fixar att Alt2-markering tidigare kunde sparas utan site-scope och därför inte synas
- Lägger e2e-test för Alt2-flödet i portal/day-view

Tagg: alt2-site-scope-2026-01-27

### Weekview: smidigare veckonavigering

- Ny veckodropdown med “Gå till vecka”
- Pilar finns kvar som komplement
- Fungerar i både site-vy och avdelningsvy
- Ingen funktionsändring i data/logik

Tagg: weekview-week-dropdown-2026-01-26

### Ändrat – Weekview-rapport / debiterbar specialkost

- Rapporter (UI, CSV, XLSX) använder nu fältet "debiterbar specialkost" i stället för generisk `special_count`.
- Debiterbar specialkost = antal måltider som faktiskt behövt specialanpassas (baserat på marks + "markeras alltid"), inte bara antal boende med specialkost.
- Normalkost i exporterna beräknas som `boendeantal − debiterbar_specialkost`.
- XLSX-kolumnrubriker uppdaterade till: Site, Avdelning, År, Vecka, Måltid, Boende totalt, Gjorda specialkoster, Normalkost.
# v1.0.0 (GA) — Release Notes

## Highlights
- ✨ Core stabilized: strict typing pockets for critical modules (`core.errors`, `core.http_errors`, `core.csrf`, `core.app_factory`, `core.rate_limit`, `core.limit_registry`, `core.audit_events`, `core.audit_repo`, `core.jwt_utils`, `core.db`).
- 🧰 RFC7807 error responses standardized across 4xx/5xx.
- 🧹 Lint baseline clean with Ruff; RC noise isolated.

## Breaking Changes
- None.

## Upgrade Guide
1. Update to the new tag: `v1.0.0`.
2. Rebuild clients if they depend on the error model (RFC7807).
3. Verify custom middleware/decorators compile with stricter typing (use `ParamSpec`/`Concatenate`).
4. Run: `ruff check . && mypy`.

## New / Improved
- Error model docs and examples in README.
- RC1 strict typing pockets table in README.
- Release script: `-Kind rc` path added (kept for future RCs).

## Deprecations
- None.

## Quality Gates
- Lint: Ruff required in CI and pre-commit.
- Types: “strict pocket” modules must pass mypy with zero warnings.
- Errors: All 4xx/5xx must return `application/problem+json`.

## Known Issues
- Temporary mypy relaxations in `core.*_api`, `core.ui_blueprint`, `legacy/*`, `importers/*`, `telemetry/*`.

## Acknowledgements
- Thanks to everyone who helped drive RC → GA.
