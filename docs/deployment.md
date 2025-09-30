# Deployment Strategy

## Environments
- local: SQLite, debug on
- staging: PostgreSQL, debug off, feature flags experimental
- production: PostgreSQL HA

## Recommended Stack
- Reverse proxy: Nginx or Traefik
- WSGI server: gunicorn (linux) / waitress (windows)
- Process model: 2-4 workers initial, scale horizontally

## Environment Variables
- SECRET_KEY
- DATABASE_URL (postgresql+psycopg://user:pass@host/dbname)
- DEFAULT_ENABLED_MODULES
- (future) FEATURE_FLAGS_SOURCE=db

## Build & Run (example)
1. python -m venv .venv
2. .venv/Scripts/activate (Windows) or source .venv/bin/activate
3. pip install -r requirements.txt
4. (future) alembic upgrade head
5. flask --app core.app_factory:create_app run

## Logging
- Use JSON formatter in production (future enhancement)
- Forward stdout to centralized logging (CloudWatch, ELK, etc.)

## Scaling Notes
- Stateless app allows container orchestration (Docker + ECS/Kubernetes)
- Shared DB; consider read replicas for heavy reporting later

## Backups
- Daily logical dump (pg_dump) + WAL archive

## Monitoring
- Health endpoint /health
- Future: metrics endpoint for Prometheus

---

# Deployment Guide (Extended)

## Production Steps
1. Provision PostgreSQL (UTF8, timezone UTC)
2. Set environment (systemd unit, container env, or .env):
   - SECRET_KEY (strong random)
   - DATABASE_URL
   - DEFAULT_ENABLED_MODULES (e.g. "municipal,offshore")
3. Install dependencies
4. Run Alembic migrations (after added): `alembic upgrade head`
5. Launch via gunicorn:
   - `gunicorn 'core.app_factory:create_app()' --bind 0.0.0.0:8000 --workers 3`
6. Put Nginx in front (TLS termination + caching static when introduced)

## Security Hardening (Phase 2+)
- Argon2 password hashing
- Rate limiting (Flask-Limiter or custom)
- CSRF protection for form endpoints
- Audit log table (user_id, action, ts, meta)

## Disaster Recovery
- Nightly dump + weekly restore test
- Keep last 30 dumps + encrypted offsite copy

## Observability Roadmap
| Layer | Tool (planned) |
|-------|----------------|
| Logs | JSON stdout -> aggregator |
| Metrics | /health + future /metrics (Prometheus) |
| Traces | Optional (OpenTelemetry) |

## Zero-Downtime Migration Strategy
- Use Alembic revision scripts (no destructive changes inline)
- Add new columns nullable → backfill → set NOT NULL
- For large backfills: chunked updates (batch size 500–1000)
