# Roadmap

## Phase 1 (Current)
- Scaffold project + core models
- Module blueprints registered
- Basic health endpoint

## Phase 2
- Add Alembic migrations
- Implement MenuService with SQLAlchemy
- Implement Authentication & password hashing
- Diet + Attendance endpoints (read-only)

## Phase 3
- Write municipal module endpoints (alt1/alt2 workflow)
- Implement DOCX import/export adapters
- Basic reporting (diet distribution, menu coverage)

## Phase 4
- Offshore turnus scheduling port (Shift generation strategies)
- Tasks + Messaging endpoints
- Waste metrics log + recommendation algorithm

## Phase 5
- Full migration execution from legacy DBs
- Feature flag admin UI
- Role-based access control decorators

## Phase 6
- Testing suite expansion (pytest + coverage)
- Performance tuning (indices, query plans)
- Multi-tenancy security hardening

## Phase 7
- SSO integration (OAuth2)
- Real-time notifications (WebSocket/SSE)
- Advanced analytics exports

## Next up (post-RC1)

1) UI-click E2E för org-enheter
	 - Beskrivning: Lägg till ett UI-test som kör hela flödet via flikar/modaler: skapa org‑enhet (modal), visa slug i listan (flik Org‑enheter), byt namn och verifiera att slug uppdateras, radera posten.
	 - Acceptance:
		 - Testen körs i chromium och iPad-projektet utan flakighet (retry 0 i lokal körning; CI kan ha retries=2).
		 - Selektorer använder data-testid där möjligt; dialoghantering stabil.

2) Seed/förteckning av grundmoduler (om saknas)
	 - Beskrivning: Vid uppstart ska `modules` auto-seedas om tabellen saknas eller är tom, baserat på konfig (`DEFAULT_ENABLED_MODULES`) med fallback till en definierad lista.
	 - Acceptance:
		 - Lokalt SQLite och i CI initierar seeds utan migrationssteg.
		 - GET `/api/superuser/tenants/{id}/modules` returnerar minst 3 modulrader initialt.

3) Feature Flags: snabb-filter/sök
	 - Beskrivning: UI-sök/filter för flagglistan så att superuser snabbt kan hitta en flagg på namn/nyckel.
	 - Acceptance:
		 - Filtrering sker klient-side utan omladdning, accentuerar matchning.
		 - Fungerar med 100+ flaggor utan märkbar lagg.

4) (Valfritt) E2E: CSRF-enforcement check (superuser-API)
	 - Beskrivning: Lägg till e2e som provar att POST/PATCH/DELETE mot `/api/superuser/*` utan `X-CSRF-Token` och förväntar RFC7807-fel (`csrf_missing`), samt att samma anrop med korrekt token lyckas.
	 - Acceptance:
		 - Testen verifierar `Cache-Control: no-store` och rätt `content-type` på fel.

## Next PR — Mikromilstolpar

1) Migrera admin-routes till `app_authz` + RFC7807
	- Byt till `core/app_authz.py::require_roles` och låt central `core/errors.py` mappa Authz/Session errors.
	- Förväntad effekt: Enhetliga 401/403-problem + `required_role` och `invalid_params`.

2) Impersonation audit + OpenAPI-exempel
	- Audit events: `impersonation_started` / `impersonation_ended` (actor_user_id, tenant_id, reason).
	- Lägg exempel under components → responses/Problem… och paths för superuser impersonation endpoints.

3) UI (Superuser → Tenants → Detail → Flags/Modules/Org‑enheter)
	- POST/PUT visar tydligt CSRF‑krav inline (tooltip eller hjälpttext).
	- Länka till ProblemDetails-hjälp vid `csrf_missing`/`csrf_invalid` fel.
