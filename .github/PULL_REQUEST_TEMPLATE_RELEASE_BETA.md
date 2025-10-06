## Goal
Cut `v1.0.0-beta` (first public baseline freeze).

## Checkpoints
- [ ] `make openapi && make ready` → ✅
- [ ] OpenAPI diff comment shows ✅ or 🟡 (no unintended ❌)
- [ ] Baseline `specs/openapi.baseline.json` matches generated `openapi.json`
- [ ] `CHANGELOG.md` contains latest snippet on top
- [ ] Security Audit (pip-audit) clean or accepted
- [ ] No TODO/FIXME left in touched files

## Semantic Diff Summary
<!-- Paste from PR comment or openapi-diff.txt -->

## Notable Additions
- …

## Deferred / Known Gaps (post-beta)
- …

## Release Steps (reminder)
1) Merge to `main`  
2) Tag + push: `git tag -a v1.0.0-beta -m "v1.0.0-beta" && git push origin v1.0.0-beta`  
3) Publish release with the changelog snippet

## Rollback Plan
Delete tag + revert merge if critical regression:
`git tag -d v1.0.0-beta && git push origin :refs/tags/v1.0.0-beta`