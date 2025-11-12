# feat(admin): Phase C — ETag-aware admin UI writes

## Summary
Implements Admin Phase C frontend:

- React + Vite app with React Query
- ETag-aware fetch layer and global concurrency handler
- UI pages for:
  - Departments (zod-validated editor with If-Match PUT)
  - Diet Defaults (diffed bulk save)
  - Alt2 Bulk (week selector + grid with collection ETag logic)
- Toast system for success/info/error feedback
- Unit tests covering ETag capture/update, 412 flow, Alt2 collection ETag, and 403 AuthzError.

## What’s in
- `src/lib/etagStore.ts`, `src/lib/fetchWithEtag.ts`, `src/lib/errors.ts`
- `src/api/admin.ts` for thin API wrappers
- `src/hooks/admin/*` React Query hooks
- `src/pages/admin/*` pages: DepartmentsPage, DietDefaultsPage, Alt2BulkPage
- `src/ui/toast/ToastProvider.tsx` + `src/hooks/admin/concurrency/useHandleConcurrency.ts`
- Vitest config (jsdom) + ETag tests (`src/__tests__/admin_etag.test.ts`)
- Branding assets and favicon wiring under `static/logo/`

## Checklist
- [x] Departments/Diet Defaults/Alt2 UI functional
- [x] ETag / If-Match sent on writes and updated from response
- [x] 412 → toast + refetch/etag refresh
- [x] Alt2 identical save → same ETag; toggle → new ETag
- [x] 403 → AuthzError handled
- [x] All Vitest tests green (5/5)
- [x] Build and TypeScript strict PASS

## Notes
Unit tests stub fetch calls for deterministic ETag flows; MSW integration tests can be added later.
Backend remains compatible with OpenAPI 1.8.0.

## Risk / Rollback
Frontend-only; no schema changes. Rollback via branch revert is safe.

## Labels
`area:ui`, `module:admin`, `type:feature`, `ready-for-review`
