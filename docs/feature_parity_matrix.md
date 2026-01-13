# Feature Parity Matrix — Legacy (Kommun + Offshore) vs Unified

Columns: Module | Feature | Source (legacy) | Unified equivalent | Status | Notes

| Module | Feature | Source | Unified equivalent | Status | Notes |
|---|---|---|---|---|---|
| Admin | Department management | kommun: /meny_avdelning_admin, tables avdelningar/kosttyper | Admin API Phase A: /api/admin/departments (skeleton) | Partial | Writes 501 in Phase A; persistence in Phase B |
| Admin | Site management | (none explicit in legacy Kommun), offshore rigs/users | Admin API Phase A: /api/admin/sites (skeleton) | Planned | Data model alignment in Phase B |
| Admin | Diet defaults per department | kommun: avdelning_kosttyp (implicit) | /api/admin/departments/{id}/diet-defaults (skeleton) | Partial | Requires schema + persistence |
| Admin | Menu import (admin) | kommun: /meny_import, upload/save; offshore: /admin/menu/upload | Unified Import API (/import/*, /import/menu) | Partial | Endpoints exist; additional mappers needed |
| Weekview | Render weekly view | kommun: /veckovy | /api/weekview (GET) | Partial | Read-only defined; data service TBD |
| Weekview | Planning (Alt1/Alt2 selection) | kommun: /planera/<vecka> | /api/weekview/alt2 (PATCH), /api/weekview (PATCH) | Planned | Requires ETag/412 + persistence |
| Report | Aggregated statistics | kommun: /rapport, /export_rapport | /api/report (GET), /api/report/export (GET) | Partial | Read-only endpoints defined |
| Attendance | Resident counts | kommun: boende_antal | /api/weekview/residents (PATCH) | Planned | With If-Match and 412 on stale |
| Alt2 | Department/day flags | kommun: alt2_markering | /api/weekview/alt2 (PATCH), /api/admin/alt2 (PUT bulk) | Partial | Bulk admin planned; day-level via weekview patch |
| Menus | Daily/weekly menus | offshore: /menus/*, public exports | Unified menu service + import/export | Partial | Further alignment needed |
| Recipes | CRUD + linking | offshore: /recipes/* | N/A (Phase A) | Gap | Candidate for separate module later |
| Turnus | Rotation planning | offshore: /turnus/* | N/A (Phase A) | Gap | Out of scope; potential module |
| Messaging | Admin/user messaging | offshore: /messages/* | N/A | Gap | Not planned in Unified core |

Status codes:
- Complete — fully implemented in Unified
- Partial — endpoints or docs exist; data service/persistence pending
- Planned — in scope for upcoming phases
- Gap — not currently planned
