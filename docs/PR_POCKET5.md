# PR: chore(types): strict pocket 5 (tasks) + unified error envelope

## Motivation
Continue incremental strict typing rollout ("pockets") to reduce regression risk and make RBAC/service boundaries explicit. Tasks domain previously mixed concerns (session access, inline serialization); this PR isolates logic, introduces explicit contracts, and unifies error envelopes.

## Summary of Changes
- Strict typing (`strict = True`) for `core.tasks_api` and new `core.tasks_service` (0 mypy errors).
- New contracts in `core/api_types.py`:
  - `TaskId` (NewType), `TaskStatus` (`"todo"|"doing"|"blocked"|"done"|"cancelled"`)
  - `TaskSummary`, `TaskListResponse`, `TaskCreateRequest/Response`, `TaskUpdateRequest/Response`.
- Unified error envelope repo-wide: `{ "ok": false, "error": <code>, "message": <text?> }` via central handlers + `require_roles`.
- Added `PATCH /tasks/{id}` (keeps `PUT` temporarily; deprecation planned once clients migrate).
- RBAC/ownership tightened: consistent 403 for role/tenant mismatch (404 only for true absence).
- SQLAlchemy 2.x compatibility: `Query.get()` → `Session.get()` (in tasks module).
- Legacy `done=True` create payload preserved and mapped to `status="done"`.

## Backward Compatibility / Risk
- Breaking changes: **none**.
- Error responses add `ok: false` (existing clients unchanged; additive field).
- `PUT` still accepted; `PATCH` now preferred.
- No schema migrations.

## Quality Gates
| Gate | Status |
|------|--------|
| mypy (tasks pocket) | PASS (0 errors) |
| tests (tasks) | PASS (13 new + existing) |
| total tests | 90 passed, 1 skipped |
| lint (scoped) | Clean (legacy/migrations excluded) |
| new `# type: ignore` | None (only existing justified ignore in create path) |

## Test Coverage (Tasks)
Scenarios covered:
- Create (happy) + Location header (201)
- List (happy) returns TaskSummary list
- Invalid status (string variants)
- Invalid status type (int)
- Missing title (validation)
- Not found update (404 envelope)
- Tenant isolation (list) 
- Role forbidden (create/update)
- Ownership enforcement (cook vs other creator)
- Legacy `done=True` mapping to `status=done`
- Rate-limit (existing infra tested elsewhere; dedicated test optional follow-up)

## Review Checklist
- [ ] Public TypedDicts / NewTypes have no `Any`
- [ ] `TaskStatus` exhaustive literal matches runtime validation
- [ ] API/service return annotations match actual JSON shapes
- [ ] Error envelope consistent (401/403/404/429 paths)
- [ ] No unintentional behavior change (201 + Location preserved)
- [ ] Legacy `done` flag still works
- [ ] No stray `Query.get()` left in modified modules

## Diff Guide
| Area | File(s) | Notes |
|------|---------|-------|
| Contracts | `core/api_types.py` | Added task-related TypedDicts & status enum expansion |
| Service layer | `core/tasks_service.py` | New centralized logic + serialization helper |
| API | `core/tasks_api.py` | Delegation to service, typed payload narrowing, PATCH added, 201 restore |
| Error envelope | `core/app_factory.py`, `core/auth.py` | Central handler yields `ok: false` + role mismatch envelope |
| Docs | `README.md`, `DECISIONS.md`, `CHANGELOG.md` | Updated pockets, decisions, unreleased notes |
| Tests | `tests/test_tasks_api.py` (+ existing suites) | Added matrix + edge cases |

## Follow-ups (Not in this PR)
- Consolidate PUT removal once clients migrated
- Expand `TaskSummary` (assignee/due) after field stabilization
- Eliminate remaining assignment ignore via refined payload TypedDict
- Add dedicated rate-limit test (optional) if needed

## Commands (Local Verification)
```
mypy core/tasks_api.py core/tasks_service.py
pytest -k tasks -q
pytest -q
```

## Acknowledgements
Pocket 5 continues the staged strict adoption pattern (1 module cluster per PR) to keep review load minimal while increasing type safety.
