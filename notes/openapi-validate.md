# OpenAPI validation

CI command:

```bash
# Fetch spec from running app
curl -fsS http://127.0.0.1:5000/openapi.json > openapi.json

# Normalize (optional for diff)
jq -S . openapi.json > /tmp/openapi.sorted.json

# Semantic diff vs baseline
python scripts/openapi_diff.py specs/openapi.baseline.json /tmp/openapi.sorted.json \
  --report /tmp/openapi-diff.txt \
  --json-report /tmp/openapi-diff.json

# Lint
spectral lint openapi.json

# OpenAPI tests
pytest -q tests/test_openapi_*.py
```

Notes:
- The workflow also starts the app (python run.py), waits for health, then fetches the spec.
- Baseline lives at `specs/openapi.baseline.json` and must exist for the diff step.
