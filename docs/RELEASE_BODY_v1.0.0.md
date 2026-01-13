## What’s new
- Core strict typing pockets are solid for GA; noisy modules deferred and tracked in the GA checklist.
- Unified RFC7807 error responses with examples in README.

## Breaking changes
- None.

## Upgrade notes
- Pull the tag `v1.0.0`, run `ruff check .` and `mypy`.
- If you maintain decorators, confirm they use `ParamSpec`.

## Checks
- CI green with lint + type checks.
- Problem+json verified on representative 4xx/5xx endpoints.

## Links
- README: Strict typing pockets (RC1)
- GA checklist issue (when opened)
