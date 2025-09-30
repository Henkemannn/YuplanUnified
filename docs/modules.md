# Modules

## Municipal Module
Purpose: Weekly menu alt1/alt2 workflow + per-unit selection UI.
Endpoints (planned):
- GET /municipal/menu/week
- POST /municipal/menu/variant
- GET /municipal/report/diet-distribution

Depends on features: menus, diet, attendance, export.docx (optional)

## Offshore Module
Purpose: Shift scheduling (turnus), waste metrics, prep/freezer tasks, messaging.
Endpoints (planned):
- GET /offshore/turnus/slots
- POST /offshore/turnus/generate
- GET /offshore/metrics/recommendation
- POST /offshore/metrics/log
- GET /offshore/tasks
- POST /offshore/tasks
- POST /offshore/messages

Depends on: turnus, waste.metrics, prep.tasks, freezer.tasks, messaging

## Feature Flag Strategy
- Module blueprint only registers if its module flag present in DEFAULT_ENABLED_MODULES or tenant override.
- Endpoint-level decorators later to further granularly gate (e.g., waste.metrics vs generic offshore).
