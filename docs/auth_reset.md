# Auth reset (break-glass)

When login fails after a merge, use the CLI in run.py. These commands only touch the DB and do not change any UI flow.

## Quick check

```bash
python run.py auth-doctor
```

This prints:
- DB_PATH + EXISTS + SIZE_BYTES
- counts for users, tenants, sites
- whether a superuser exists

## Create/reset a user

```bash
python run.py auth-reset --email you@example.com --role superuser
```

Notes:
- A temporary password is printed once. Copy it immediately.
- Roles allowed: superuser, admin, cook

Example output:

```text
User ready: you@example.com (role=superuser)
TEMP_PASSWORD: <printed once>
WARNING: copy now - shown only here.
```

## Ensure superuser from env

Set env vars, then run:

```bash
python run.py auth-ensure-superuser
```

Required env:
- SUPERUSER_EMAIL
- SUPERUSER_PASSWORD

If env vars are missing, the command prints instructions and does nothing.

## Important

- dev.db is never committed.
- Seed data and DB contents can differ between runs and after merges.
