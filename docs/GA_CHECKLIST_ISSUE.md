# GA checklist (v1.0.0)

**Goal:** Flip from RC to GA with zero typing noise and guaranteed RFC7807 coverage.

## Typing & Lint
- [ ] Zero mypy errors in `core.*_api`.
- [ ] Remove temporary `# type: ignore` and narrow any remaining to the exact error code.
- [ ] Promote next pocket(s) to strict: `core.auth`, `core.ui_blueprint` (or adjust order).
- [ ] Ensure decorator wrappers have precise `ParamSpec`/`Concatenate` as needed.
- [ ] Ruff: enable in pre-commit and CI; repo runs clean.

## Error Model
- [ ] All 4xx/5xx return `application/problem+json` (RFC7807).
- [ ] Document problem fields & examples in README.
- [ ] Add one CI test asserting a 415 example path returns problem+json.

## Build & Release
- [ ] Release notes drafted for v1.0.0 (highlights, breaking changes, upgrade notes).
- [ ] RC validation: smoke tests on tag `v1.0.0-rc1` artifacts.
- [ ] Release script: flip from `-Kind rc` to GA path; verify version bump & tag creation.

## Docs
- [ ] README table “Strict typing pockets (RC1)” present and current.
- [ ] Add quickstart for local type checking + how to expand strict pockets.
- [ ] Changelog updated from RC → GA.

## Nice-to-have (optional)
- [ ] OpenAPI examples for task create/update bodies.
- [ ] Mark legacy `done` field as `readOnly: true` in spec if applicable.

---

### Gradual mypy re-enable (notes)
Start with core.auth endpoints. Add trivial return annotations and narrow dict[str, Any] to TypedDict where feasible.

Wrap decorators with ParamSpec to eliminate “no-untyped-call” in strict pockets.

For noisy request/response shapes, introduce Protocol/TypedDict adapters rather than refactoring handlers.

### Handy verifications
```pwsh
# Confirm the tag exists locally and remotely
git tag --list 'v1.0.0-rc1'
git ls-remote --tags origin | Select-String 'v1\.0\.0-rc1'

# Re-run lint & type checks
./.venv/Scripts/ruff.exe check .
C:/Users/Henri/unified_platform/.venv/Scripts/python.exe -m mypy
```
