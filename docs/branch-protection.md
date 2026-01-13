Branch protection snapshot

We keep a small, public snapshot of branch protection rules in `infra/bp.json`.
It’s non-secret and intended for infra/repo-admin only. The snapshot helps us:

- document the required status checks and settings for `master`
- review changes over time via PRs (audit trail)
- optionally drive an automated sync script later

Note: if we package or distribute artifacts, ensure `infra/` is excluded.
