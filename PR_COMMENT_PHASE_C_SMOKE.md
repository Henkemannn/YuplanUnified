# Phase C – Staging smoke checklist

Quick checks after deploy to staging:

## Departments
- Open Departments page, edit name or fixed count
- Save once → expect toast "Sparat"
- Save same data again quickly → expect either no-op or brief info toast (no change)
- Perform conflicting save from another tab, then save here → expect conflict toast and automatic refetch (412)

## Diet Defaults
- Load defaults for a department
- Change one value and Save → toast "Sparat"; ETag updates
- Save without changes → info toast "Inga ändringar"
- Make conflicting change in another tab → expect conflict toast + refresh

## Alt2 Bulk
- Select a week (e.g. 202401)
- Toggle a cell → Save → toast "Sparat"; collection ETag changes
- Save again without any changes → info toast "Inga ändringar"
- Create conflict from another tab, then Save → conflict toast and refresh

## General
- 403 Forbidden (impersonate or lower-priv) → toast from AuthzError
- Refresh page; ensure list queries repopulate and ETags retained for subsequent writes

Notes:
- Concurrency flow: On 412, client updates stored ETag from `current_etag`, invalidates the query key(s), and prompts user
- Tests: `npm test` runs Vitest (5/5 passing)