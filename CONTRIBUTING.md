# Contributing

## Issue templates
Use New Issue → GA checklist (v1.0.0) for GA readiness, and New Issue → v1.1 roadmap kickoff for the next milestone.
Assign an owner and set the milestone before starting work.

## Branching
- master: protected, release-only
- dev: integration branch
- Feature branches: feature/<area>-<short-name>
- Hotfix branches: hotfix/<short-name>

## Pull requests
- Title: concise, imperative (e.g., "Add RFC7807 smoke test")
- Link to an issue (GA checklist or roadmap item)
- Checks required: Ruff, mypy, tests (CI must be green)
- Require 1 approval; no direct pushes to master

## Code quality
- Lint: ruff check .
- Types: mypy (strict pockets must pass)
- Error model: all 4xx/5xx return application/problem+json (RFC7807)

## Secrets & privacy
- No credentials in code. Use GitHub Actions secrets.
- Repo is private; do not share source externally without approval.
