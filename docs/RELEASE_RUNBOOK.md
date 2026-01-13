# Release Runbook

## Pre-flight
- [ ] CI green on `master`
- [ ] Changelog updated
- [ ] README updated (if needed)

## Tagging

RC:

```pwsh
# creates v<VERSION>-rcN and pushes
pwsh -File tools/release.ps1 -Kind rc
```

GA:

```pwsh
git tag -a v1.0.0 -m "GA release v1.0.0"
git push origin v1.0.0
```

## Validation
- [ ] CI “Validate Tag → Release” workflow passes
- [ ] RFC7807 smoke test green
- [ ] Ruff + mypy checks clean

## Publish Release (GitHub UI)
- Releases → Draft new release
- Tag: v1.0.0
- Body: paste from `docs/RELEASE_BODY_v1.0.0.md`
- Attach artifacts (if any)
- Publish

## Post-publish
- [ ] Open GA checklist issue via template
- [ ] Open v1.1 roadmap kickoff via template
- [ ] Create `release/<version>` branch if you need patch fixes

## Hotfix flow
```pwsh
git checkout -b hotfix/<name> master
# commit, PR to master, tag v1.0.1, push, publish
```
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