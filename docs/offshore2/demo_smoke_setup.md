# Offshore Demo Smoke Setup

`flask offshore-demo-seed` creates a small, tenant-scoped Offshore demo dataset for manual smoke testing.

The command is intentionally narrow and idempotent. It only touches the dedicated demo tenant and site, then rebuilds the Offshore rows for that scope:

- tenant `9001` named `Demo Offshore`
- site `demo-offshore` named `Demo Offshore Site`
- Offshore installation settings
- work positions
- menu cycle and slots
- period template and generated work period
- service events and menu-context rows
- Builder components, compositions, menu rows, link rows, and publication pin rows
- prep tasks for the generated service events

Safety rules:

- The command refuses to run in `production`, `prod`, or `pilot` environments.
- It allows the seed in `development`, `testing`, or any local SQLite-backed setup.
- `--force` is available for local override when you know the current database is disposable.
- `--reset` clears only the scoped demo rows and exits.

Usage:

```bash
flask offshore-demo-seed
flask offshore-demo-seed --reset
flask offshore-demo-seed --force
```

Manual smoke flow after seeding:

1. Open `/offshore` and confirm the demo tenant/site is available.
2. Open `/offshore/operations` and check that the current period and Builder-linked summary render.
3. Open `/offshore/operations/prep` and verify the prep groups and task transitions are visible.

The command uses the existing Offshore services and Builder persistence layer. It does not depend on startup seeding or ad-hoc fixtures.