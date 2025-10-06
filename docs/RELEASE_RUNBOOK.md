## v1.0.0-beta – Release Runbook

### Preconditions
- Target branch ready (usually `main`).
- CI green on latest commit.
- Baseline present: `specs/openapi.baseline.json`.

### 1) Local sanity
```bash
make openapi
make ready
# => ✅ Release readiness OK.
```

### 2) Merge to main

Open/Update PR → ensure OpenAPI diff comment is ✅ (stable) or 🟡 (additions only).

### 3) Tag
```bash
git checkout main && git pull
git tag -a v1.0.0-beta -m "v1.0.0-beta"
git push origin v1.0.0-beta
```

### 4) Release workflow

Auto-triggers: “Release OpenAPI Changelog”.

Manual fallback: Actions → “Release OpenAPI Changelog” → Run (target_branch=main, force_fallback=true if needed).

### 5) Verify

`CHANGELOG.md` prepended with “OpenAPI changes (YYYY-MM-DD)”.

Artifacts present: `openapi.json`, `openapi-extras/*`, `openapi-diff/*`.

### 6) GitHub Release

Tag: `v1.0.0-beta`

Body: paste `openapi-extras/openapi-changelog.md`.

### 7) Post-release

Manually run “Security Audit” once (pip-audit).

### Common scenarios

❌ unintended breaking → fix or do coordinated baseline update + MAJOR bump.

Missing artifact → workflow uses fallback (starts app, generates diff/snippet).

### Rollback
```bash
git tag -d v1.0.0-beta
git push origin :refs/tags/v1.0.0-beta
```

---

All steps above presume a clean semantic diff (no ❌) and a frozen baseline matching the generated spec.