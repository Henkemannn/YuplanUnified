# ✅ GA checklist (v1.0.0)

**Goal:** Flip from RC → GA with zero typing noise, verified RFC7807 coverage, and clean CI.

---

## 🧩 Typing & Lint
- [ ] Zero **mypy** errors in `core.*_api`.
- [ ] Remove temporary `# type: ignore` lines (narrow any remaining to specific error codes).
- [ ] Re-enable next strict pockets: `core.auth`, `core.ui_blueprint`.
- [ ] Verify decorator wrappers use `ParamSpec` / `Concatenate`.
- [ ] Ruff enabled in pre-commit and CI (`ruff check .` passes clean).

---

## ⚙️ Error Model (RFC7807)
- [ ] All 4xx/5xx responses return `application/problem+json`.
- [ ] Example 415 path verified in tests (see `test_rfc7807_smoke.py`).
- [ ] README updated with problem+json examples and field definitions.

---

## 🚀 Build & Release
- [ ] RC validation complete for `v1.0.0-rc1`.
- [ ] Release tag **v1.0.0** published successfully (GA).
- [ ] Release notes finalized (see `RELEASE_NOTES.md`).
- [ ] CI workflow passes (Ruff, mypy, tests).

---

## 📚 Docs & Communication
- [ ] README includes “Strict typing pockets (RC1)” table.
- [ ] CHANGELOG updated with `[1.0.0] — 2025-10-10`.
- [ ] GA release notes committed and linked in release body.
- [ ] Quickstart and contributor docs mention how to expand strict pockets.

---

## 🧪 Quality Gates
- [ ] Pre-commit hook runs Ruff + mypy.
- [ ] CI workflow enforces zero lint/type errors.
- [ ] Problem+json smoke test included in test suite.

---

## 🧭 Optional / Nice-to-Have
- [ ] Add OpenAPI examples for `task create/update`.
- [ ] Mark legacy `done` field as `readOnly: true` in spec.
- [ ] Document error envelope for custom middleware.
- [ ] Seed examples for tenant/module setup in README.

---

🗓️ **Target:** Lock GA validation within this sprint.  
🧑‍💻 **Owner:** (assign to release manager / maintainer)  
🔗 **References:** `GA_CHECKLIST_ISSUE.md`, `RELEASE_NOTES.md`, CI logs for v1.0.0.
