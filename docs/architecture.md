# Unified Yuplan Platform Architecture

## Goals
- Single codebase powering multiple customer verticals (Municipal, Offshore, future sectors)
- Core domain: Menus, Diets, Attendance, Users/Tenants, Export/Import
- Optional modules (feature flagged): Turnus Scheduling, Waste Metrics, Prep/Freezer Tasks, Messaging, Alt1/Alt2 variant workflow

## High-Level Components
1. Core API (Flask) with App Factory
2. SQLAlchemy ORM (PostgreSQL target; SQLite dev)
3. Feature Registry & Module Loader
4. Service Layer (Menu, Scheduling, Metrics, Diet, Reporting)
5. Modules as Blueprints + Service Extensions
6. Migration Layer (Alembic)
7. Export/Import Adapters (docx, excel, future pdf)

## Request Flow
Client -> Flask Blueprint (module or core) -> Service Layer -> ORM -> DB

## Tenancy Model
- tenants table anchors all multi-customer isolation
- units per tenant (rigs / avdelningar)
- user.role + optional unit_id
- future: row level security or per-tenant schema (phase 2+)

## Feature Flags
- In-memory registry initially
- Future: tenant_feature_flags table and admin UI

## Module Isolation Rules
- Modules never mutate core tables schema directly (only through migrations)
- Shared utilities live in core.utils (to be added)
- Cross-module events routed via lightweight in-process dispatcher

## Data Ownership
| Domain | Owner |
|--------|-------|
| Users, Tenants, Units | Core |
| Menus & Variants | Core |
| Diet Assignments & Attendance | Core |
| Shift / Turnus | Offshore Module |
| Waste Metrics | Offshore Module |
| Tasks (prep/freezer) | Offshore Module |
| Alt1/Alt2 Workflow | Municipal Module |
| Messaging | Offshore Module (could move Core later) |

## Security / Auth (Phase 1 Simplified)
- Session cookie (Flask) + hashed passwords
- Role checks decorator (planned core.auth module)
- Phase 2: JWT for external integrations

## Scaling & Deployment
- WSGI via gunicorn / waitress behind reverse proxy
- Postgres for production; connection pooling via SQLAlchemy
- Horizontal scale: stateless app; background jobs (later) via Celery/RQ

## Logging & Observability
- Structured JSON logging in production mode
- Health endpoint /health listing registered modules

## Future Extensions
- Real-time notifications (WebSocket or SSE)
- External SSO (OAuth2 / SAML)
- Analytics warehouse export

## Dataflöde: Superuser Dashboard

```text
[Client] dashboard.js
	├─ GET /api/superuser/summary  → KPI (Tenants/Modules/Flags)
	├─ GET /api/superuser/events   → Lista (senaste 20) / Empty state
	└─ GET /api/superuser/health   → Badges (API/DB/Queue)

[Server] superuser_api (guard: superuser)
	├─ summary:
	│   ├ tenants_total    ← SELECT COUNT(*) FROM tenants
	│   ├ modules_active   ← (config‑driven tills modulmodell finns)
	│   └ feature_flags_on ← COUNT(*) FROM tenant_feature_flags WHERE enabled=TRUE
	├─ events:
	│   ├ hämta senaste audit_events ORDER BY id DESC LIMIT N
	│   └ badge‑heuristik: TENANT / FLAG / USER / GEN
	└─ health:
			├ API OK (routelogik nådd)
			├ DB ping (SELECT 1)
			└ Queue placeholder (framtida djup / latency)

Cache:   no-store på alla svar
Fel:     RFC7807 (problem+json)
CSRF:    Krävdes endast för framtida POST / toggle endpoints
```

### Eventformattering (heuristik)
| Kind                | Titelexempel                                 | Badge |
|---------------------|-----------------------------------------------|-------|
| TENANT_CREATED      | Tenant skapad – {name} skapad                 | TENANT|
| TENANT_UPDATED      | Tenant uppdaterad – {name} uppdaterad         | TENANT|
| FLAG_TOGGLED        | Flagga ändrad – {flag} på|av                  | FLAG  |
| MODULE_INSTALLED    | Modul installerad – {module} installerad      | MODUL |
| MODULE_ENABLED      | Modul aktiverad – {module} aktiverad          | MODUL |
| (fallback)          | Händelse – {KIND}                             | INFO  |

Badge-regler: ^TENANT_ → TENANT, ^MODULE_ → MODUL, 'FLAG' i kind/payload → FLAG, annars INFO.

### KPI-källor (framtida normaliserade tabeller)
* Tenants: `tenants` (lägg ev. `deleted_at` för soft delete)
* Modules: `modules`, `tenant_modules` (relationer aktivering)
* Feature Flags: `feature_flags` (+ overrides per tenant i `tenant_feature_flags`)
* Aggregering sker synkront (COUNT/DISTINCT) tills volym kräver materialiserad vy / cache.

Cache policy: 5s in-memory cache i servern för summary; klient får alltid färskt (no-store header hindrar delning nedströms).
