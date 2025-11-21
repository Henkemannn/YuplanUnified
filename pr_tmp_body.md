## Sammanfattning
Implementerar Planera Phase P1.1: dag- och vecka-aggregation via ny `PlaneraService`, hashed weak ETags (sha1 över kanonisk JSON), samt feature flag-gating med `ff.planera.enabled` (404 när avstängd). UI (day & week) använder nu riktiga data istället för placeholders. Skeleton-tester uppdaterade så de aktiverar flaggan. Full pytest-suite passerar: 363 passed, 7 skipped.

## Detaljer
- Ny fil: `core/planera_service.py` för day/week aggregation (räknar marked special diets och normal-diet residual).
- API `/api/planera/day` och `/api/planera/week`: utbytt dummy till riktig aggregation + sha1-baserad ETag + 404 om flagga disabled.
- UI-rutter `/ui/planera/day`, `/ui/planera/week`: feature flag-gating + riktig data; week UI har TODO för department-filter.
- Tester: skeleton justeras att lägga till flaggan innan anrop. Negativa tester (404 + 304 conditional + diet name mapping tolerans) planeras i nästa mini-PR (P1.1.1).
- ETag-format: `W/"planera:<kind>:<sha1prefix>"`.

## Referenser
Se `docs/planera_module_functional_spec.md` för ursprunglig funktionell spec.

## TODO (P1.1.1 / P1.2)
- Department-filter i week UI (kommentar i kod).
- Negativa tester (flag disabled 404 + If-None-Match 304).
- Diet name mapping (ersätta placeholder med registry).
- Export (print + CSV) kommer i P1.2.

## Kvalitet
- Pytest: 363 passed, 7 skipped, inga fel.
- Ingen ändring av befintliga weekview/report-moduler.
- Feature flag är opt-in: ej tillagd i seed => modul avstängd tills explicit aktiverad.

## Labels
module:planera, phase:P1.1, area:api, area:ui, type:feature, ready-for-review
