## Superuser UI wireframe

Lightweight wireframe to align the current implementation and guide near-term iteration. This focuses on tenants list, create/disable, and modules toggle.

### Dashboard (entry)

- KPIs (health, events, tenants count) + quick links
- Nav: Dashboard · Tenants · Feature Flags · Modules

### Tenants list

```
[ Search … ]                                (+) New tenant

┌─────────┬──────────────┬──────────┬────────────┬─────────┐
│ ID      │ Name         │ Slug     │ Created    │ Enabled │
├─────────┼──────────────┼──────────┼────────────┼─────────┤
│ 12      │ Sundbyberg   │ s-barkar │ 2025-10-10 │  Yes    │  [Open]
│ 7       │ Rederi AB    │ red-ab   │ 2025-09-05 │   No    │  [Open]
└─────────┴──────────────┴──────────┴────────────┴─────────┘
```

Row actions: Open → tenant detail (tabs). Enabled shows a badge; click on detail to toggle.

### Tenant detail (tabs)

- Overview | Modules | Feature Flags | Org-enheter

Overview:
- Basic metadata, enable/disable toggle (POST /api/superuser/tenants/{id}/enable|disable)

Modules:
- Checklist of available modules with on/off toggle per row (POST toggle). Save is immediate; CSRF header sent by fetch wrapper.

Feature Flags:
- Table of tenant-scoped flags with quick search. Toggle writes to `/admin/feature_flags` with `tenant_id` set.

Org-enheter:
- CRUD for units with slug generation and visual confirmation.

Notes:
- Mutations require `X-CSRF-Token`; our fetch helper injects it when strict mode is active.
