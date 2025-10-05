# Developer convenience targets (POSIX systems)
# Usage: make <target>
# Override PY, PORT, HOST via environment if needed.

PY ?= python
PORT ?= 5000
HOST ?= 127.0.0.1

.PHONY: install dev test lint format spectral openapi smoke ci clean

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

clean:
	rm -f openapi.json
