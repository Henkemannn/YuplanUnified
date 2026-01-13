Motivation:
- pip-audit flags vulnerabilities in gunicorn 21.2.0 (e.g., GHSA-w3h3-4rj7-4ph4, GHSA-hc5x-x2vx-497g).

Change:
- Bump gunicorn → 22.0.0 in requirements.txt.

Verification:
- Full pytest suite on local env with gunicorn 22.0.0 installed: 353 passed, 7 skipped.

Notes:
- Security hygiene ahead of 0.3.0; no runtime code changes.