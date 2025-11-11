# Developer convenience targets (POSIX systems)
# Usage: make <target>
# Override PY, PORT, HOST via environment if needed.

PY ?= python
PORT ?= 5000
HOST ?= 127.0.0.1

.PHONY: install dev test lint format spectral openapi smoke ci ready clean

install:
	$(PY) -m pip install --upgrade pip
	pip install -r requirements.txt

# Optional extras (fail soft if tools missing)
	- pip install openapi-spec-validator requests > /dev/null 2>&1 || true

dev:
	$(PY) run.py

test:
	pytest -q

lint:
	ruff check .

format:
	ruff format .

spectral:
	@command -v spectral >/dev/null 2>&1 || npm install -g @stoplight/spectral-cli
	spectral lint openapi.json || echo "(Hint) Run 'make openapi' first to fetch spec."

openapi:
	curl -fsS http://$(HOST):$(PORT)/openapi.json | jq -S . > openapi.json

smoke:
	echo '{"items":[{"name":"Spaghetti Bolognese"}]}' > /tmp/menu.json
	curl -fsS -X POST http://$(HOST):$(PORT)/import/menu \
		-H 'Content-Type: application/json' \
		--data @/tmp/menu.json -o /tmp/smoke.json
	test -s /tmp/smoke.json && echo "smoke ok"

ci: lint test openapi spectral smoke

ready:
	$(PY) scripts/check_release_ready.py

seed-varberg:
	DATABASE_URL="${DATABASE_URL}" $(PY) -m scripts.seed_varberg_midsommar || exit 1

clean:
	rm -f openapi.json

# --- Release helpers ---
SHELL := /bin/bash
VERSION_FILE := VERSION

.PHONY: check-clean
check-clean:
	@test -z "$$(git status --porcelain)" || { echo "Working tree not clean"; exit 1; }

.PHONY: release-major release-minor release-patch
release-major: KIND=major
release-minor: KIND=minor
release-patch: KIND=patch

release-major release-minor release-patch: check-clean
	@set -e; \
	new="$$( $(PY) tools/bump_version.py $(KIND) )"; \
	echo "New version: $$new"; \
	git add $(VERSION_FILE); \
	git commit -m "chore(release): bump version to $$new"; \
	git tag "v$$new"; \
	git push; \
	git push --tags; \
	echo "Tag v$$new pushed. Release workflow will run." 
