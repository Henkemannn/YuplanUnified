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
python run.py auth-reset --email you@example.com --role superuser --password-env YP_RESET_PW
```

Notes:
- Roles allowed: superuser, admin, cook
- Avoid putting passwords directly in command history; prefer --password-env.

PowerShell example:

```powershell
$env:YP_RESET_PW="SomeStrongPw!123"
python run.py auth-reset --email you@x --role superuser --password-env YP_RESET_PW
Remove-Item Env:\YP_RESET_PW
```

Bash example:

```bash
export YP_RESET_PW='SomeStrongPw!123'
python run.py auth-reset --email you@x --role superuser --password-env YP_RESET_PW
unset YP_RESET_PW
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
