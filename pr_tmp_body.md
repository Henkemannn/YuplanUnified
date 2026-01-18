PR-beskrivning

Resultat

✅ Fullt grönt testläge: 918 passed, 12 skipped, 0 failures

Ändringar

Kommun UI

- Aktiverade legacy-ändpunkter med korrekt ETag/304-stöd
- (core/legacy_kommun_ui.py, blueprint registrerad i core/app_factory.py)

RFC7807 / ProblemDetails

- Centraliserad felhantering för validering, paginering och rate-limit
- Koder: 401 / 403 / 404 / 429
- Implementerat i core/app_errors.py

Tasks API

- Normaliserade valideringssvar:
	- Skapa: 422 med typ som slutar på /validation_error
	- Uppdatera status: 400 med typ som slutar på /bad_request
- Ändringar i core/tasks_api.py

OpenAPI

- Lade till ProblemDetails (inkl. request_id)
- Återanvändbara responses: Problem401, Problem403, Problem429
- Uppdaterat i core/app_factory.py

SQLite bootstrap

- Säkrad kompatibilitet för departments.version
- Befintlig bootstrap-strategi bibehållen

Verifiering

- ETag-tester (tests/test_etag_views.py)
- Notes & Tasks-validering
- OpenAPI security/spec
- Full körning: pytest -q

Slutsats

Den här PR:en återställer alla kontraktytor efter merge, utan refactors, och lämnar projektet i ett stabilt, verifierat läge.
