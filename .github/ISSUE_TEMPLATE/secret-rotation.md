---
name: Secret Rotation
about: Quarterly rotation of sensitive credentials
labels: [security, rotation]
---

## Secret to rotate
- **Name (GitHub Secret):**
- **Owner/team:**
- **Location(s):** (GitHub, cloud provider, CI)
- **Last rotated:**
- **Next rotation date:**

## Checklist
- [ ] Generate new secret in provider
- [ ] Update **GitHub → Settings → Secrets and variables → Actions**
- [ ] Update any infra / OTLP exporter tokens (collector/backend)
- [ ] Validate CI runs green
- [ ] Update docs (SECURITY.md / runbooks)
- [ ] Revoke old secret

## Inventory (example)
| Secret | GitHub Name | Provider | Owner | Last Rotated | Notes |
|--------|-------------|----------|-------|--------------|-------|
| OTLP API Token | OTEL_EXPORTER_TOKEN | Observability SaaS | Platform | 2025-07-01 | Rotate quarterly |

## Procedure
1. Generate new credential in source system (SaaS / cloud provider).
2. In GitHub repository: Settings → Secrets and variables → Actions → Update secret value.
3. If used in infrastructure manifests, update and deploy (Terraform / Helm / etc.).
4. Trigger a CI run; confirm no authentication or 401/403 failures.
5. Remove or revoke old secret in provider (ensure no active workloads still referencing it).
6. Update documentation & rotation schedule.

## Notes
- Rotate quarterly (create follow-up issue if blocked).
- If secret impacts customer traffic, schedule low-risk window.
- Consider staging test prior to production rotation.
