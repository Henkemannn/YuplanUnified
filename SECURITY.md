# Security Policy

This document describes how we handle vulnerabilities, security controls in code & CI, and expectations for responsible disclosure.

## Supported Versions
Only the latest released (tagged) minor version and the current `master` (development) branch receive security fixes. After GA (`v1.x`), previous minors may receive critical patches at our discretion.

| Version | Status | Security Fixes |
|---------|--------|----------------|
| `v1.0.0-beta` | Beta (baseline frozen) | Yes (critical + high) |
| `master` | Active development | Yes (all severities) |

## Reporting a Vulnerability
Email: `security@exempel.tld` (preferred)  
Alternative: Create a private GitHub Security Advisory ("Report a vulnerability" in the repo Security tab).

Please include (when possible):
* Affected endpoint / component
* Steps to reproduce (curl or minimal script)
* Observed vs. expected result
* Potential impact assessment
* Any CVSS vector you propose

Do NOT create a public issue for unpatched vulnerabilities.

### Response Targets
| Phase | Target SLA |
|-------|------------|
| Triage | 2 business days |
| First response / clarification | 5 business days |
| Fix for Critical | 7 days (best effort) |
| Fix for High | 14 days |
| Fix for Medium | 30 days |
| Fix for Low | 60 days |

We use a CVSS v3.1 inspired severity mapping. If exploitability is low and there is no data exposure, we may extend timelines.

### Disclosure Timeline
1. Reporter submits privately.
2. We acknowledge (≤ 5 business days).
3. Patch developed & reviewed under a private branch / fork.
4. Release fix + coordinated disclosure (CHANGELOG + optional security advisory). Credit given if desired.
5. If active exploitation is observed, we may accelerate release and publish limited interim guidance.

## Security Controls (CI & Runtime)
| Control | Description |
|---------|-------------|
| OpenAPI Baseline Enforcement | Prevents accidental breaking contract changes / unvetted surface expansion. |
| Semantic Diff (scripts/openapi_diff.py) | Detects narrowing & structural changes (type, format, required fields). |
| Rate Limiting (fixed + token bucket) | Mitigates brute force & abusive scraping patterns. |
| Audit Logging | Admin & limit changes persisted with retention cleanup script. |
| Feature Flags | Allows gradual, principal-of-least-change rollout. |
| Pre-commit Hooks | Lint + type guard before code lands. |
| pip-audit Workflow | Identifies vulnerable dependencies. |
| Release Readiness Script | Ensures baseline, tests, lint, diff status before tagging. |

## Dependencies (pip-audit)
Before each release:
1. Run `pip-audit --strict` locally (or `make ready` if integrated later).
2. Fix or pin any Critical/High issues; document accepted Medium/Low in `SECURITY-NOTES.md` (future) if deferring.
3. CI soft gate example:
```yaml
- name: pip-audit
  run: |
    pip install pip-audit
    pip-audit || true  # TODO: remove '|| true' to hard fail later
```

## GitHub Actions Permissions
Principle: Default to `read-all` and explicitly widen per job only as needed.

Global restriction example:
```yaml
permissions: read-all
jobs:
  openapi-status:
    permissions:
      contents: write
      pull-requests: write
```
Remove `issues: write` unless actually posting issues. For PR comments use `pull-requests: write`.

## Secrets Handling
| Practice | Notes |
|----------|-------|
| Minimal secrets | Prefer short-lived tokens or environment-provided creds. |
| No secrets in repo | Validate via secret scanning (GitHub Advanced Security / trufflehog). |
| Rotation cadence | Quarterly for static tokens / credentials (✅ checklist). |
| Principle of Least Privilege | Scope tokens to required repo or environment only. |

## Rate Limiting & Abuse Mitigation
* Fixed window and token bucket strategies supported per limit registry.
* 429 responses include `Retry-After` for polite backoff.
* Metrics: `rate_limit.hit` (`allow|block`) and `rate_limit.lookup` sources to monitor systemic pressure.
* Adjust per-tenant limits under feature flags for burst containment.

## Data Handling (PII / Telemetry)
| Aspect | Approach |
|--------|----------|
| PII in logs | Avoid user supplied free‑form fields; redact tokens / secrets. |
| Request IDs | `request_id` correlates across logs & problems `instance`. |
| Multi-tenancy | Tenant ID tag in logs & metrics (partitioning & forensic filtering). |
| Metrics | Aggregate numeric / categorical (no raw content bodies). |
| Retention | Audit events truncated via retention cleanup script (configurable). |

## Responsible Disclosure Checklist (Maintainers)
| ✅ | Task |
|----|------|
| ✅ | Triage new report within 2 business days |
| ✅ | Classify severity (CVSS rough score) |
| ✅ | Create private fix branch (no public issue) |
| ✅ | Run `pip-audit` before release cut |
| ✅ | Review workflow permissions (least privilege) each release |
| ✅ | Rotate tokens quarterly |
| ✅ | Verify rate limit protections (simulate abusive pattern) |
| ✅ | Confirm audit retention job run |

## Maintainer Release Security Checklist
| ✅ | Step |
|----|------|
| ✅ | `make ready` green (tests, diff, lint) |
| ✅ | `pip-audit` shows no unmitigated Critical/High |
| ✅ | Secrets scan (periodic) shows no leaks |
| ✅ | Baseline `specs/openapi.baseline.json` matches current spec |
| ✅ | Review new dependencies for license & security posture |
| ✅ | Rate limit changes documented in CHANGELOG |
| ✅ | Deprecation headers (if any) validated |

## CVSS Inspired Severity Mapping (Guidance)
| Severity | Typical Impact |
|----------|----------------|
| Critical | RCE, auth bypass, sensitive data exfiltration |
| High | Privilege escalation, significant data tampering |
| Medium | Limited data exposure, authorization edge cases |
| Low | Information disclosure (non-sensitive), minor spoofing |
| Informational | Hardening opportunity / best practice deviation |

## Contact & Attribution
If you wish to be credited, include the preferred name or handle. We will not publish reporter details without consent.

Thank you for helping keep the platform secure.
