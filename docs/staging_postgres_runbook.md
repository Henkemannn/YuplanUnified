# Fly.io Postgres Staging Runbook

Goal: Maintain and (re)create the Yuplan Unified staging environment backed by Postgres on Fly.io.

## Overview
- App: `yuplan-unified-staging-icy-wave-9332` (region `arn`)
- Database: single-node Fly Postgres cluster (sized minimal for staging)
- Expected monthly cost: ~USD $10 (subject to Fly pricing changes). Keep data volume small; scale down when idle.
- Failure domain: single region; acceptable for staging.

## 1. Create Postgres Cluster
Provision a minimal cluster (1 node, 5GB volume). Adjust name if already exists.
```powershell
fly postgres create --name yuplan-staging-db --initial-cluster-size 1 --volume-size 5 --region arn
```
If using Bash:
```bash
fly postgres create --name yuplan-staging-db --initial-cluster-size 1 --volume-size 5 --region arn
```

## 2. Attach Database to App
Attaching sets `DATABASE_URL` secret automatically.
```powershell
fly postgres attach --app yuplan-unified-staging-icy-wave-9332 yuplan-staging-db
```
```bash
fly postgres attach --app yuplan-unified-staging-icy-wave-9332 yuplan-staging-db
```

## 3. Verify Secret
```powershell
fly secrets list --app yuplan-unified-staging-icy-wave-9332
```
Look for `DATABASE_URL`. If absent, re-run attach.

## 4. Run Migrations In Container
Use SSH console to execute the migration + minimal seed script.
```powershell
fly ssh console --app yuplan-unified-staging-icy-wave-9332 -C "python tools/init_db.py"
```
This runs Alembic `upgrade heads` and seeds tenant `demo` with units `Alpha`, `Bravo`.

## 5. Optional: Week View Seed
```powershell
fly ssh console --app yuplan-unified-staging-icy-wave-9332 -C "python tools/seed_weekview.py --tenant demo --year 2025 --week 45 --departments Alpha Bravo"
```
Adjust year/week/departments as needed.

## 6. Health Checks
```powershell
curl -s https://yuplan-unified-staging-icy-wave-9332.fly.dev/healthz
```
Should return `{"status":"ok"}`.

For a fuller snapshot:
```powershell
curl -s https://yuplan-unified-staging-icy-wave-9332.fly.dev/health | jq .
```

## 7. Common Operations

### View Logs
```powershell
fly logs --app yuplan-unified-staging-icy-wave-9332
```

### Restart Machine
```powershell
fly apps restart yuplan-unified-staging-icy-wave-9332
```

### Deploy New Image
From repo root after building changes (CI usually handles build):
```powershell
fly deploy
```

## 8. Rotation / Reset
If you need a clean staging DB:
1. Detach (or rename app) and create a new Postgres cluster.
2. Re-run steps 2–6.

## 9. Rollback Strategy (Lightweight)
Staging is non-critical; rollback is normally "redeploy previous image":
```powershell
fly releases --app yuplan-unified-staging-icy-wave-9332   # find prior release version
fly deploy --image <previous-image-ref>
```
Database rollback is not automated—prefer forward-fix migrations. For destructive tests, use a new cluster.

## 10. Notes
- Do not store production data here.
- Secrets other than `DATABASE_URL` can be added via `fly secrets set KEY=value`.
- Ensure migrations never rely on vendor-specific SQL not supported by Postgres without guards.

## 11. Troubleshooting
| Symptom | Action |
|---------|--------|
| `alembic` errors about multiple heads | Confirm `tools/init_db.py` uses `upgrade heads`; check for newly branched revisions needing merge. |
| Foreign key errors on migration | Ensure constraints named (already addressed in revision 0005). |
| Health check fails after deploy | Inspect logs (`fly logs`) for Gunicorn binding; confirm container still uses port 8080 and `gunicorn core.wsgi:app`. |
| `DATABASE_URL` missing | Re-run attach; verify app name.

## 12. Future Enhancements
- Automated migration task in CI triggered on deploy.
- Metrics and tracing exporters gated behind feature flags.
- Multi-region staging for latency tests (optional).

---
Last updated: 2025-11-06
