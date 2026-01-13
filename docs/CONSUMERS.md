# API Consumers – Getting Started

> This guide helps client developers integrate safely with the API and avoid breaking changes.

## Base URL & Versioning
- **Base URL:** `https://api.example.com`
- **Versioning:** Semantic Versioning (SemVer)
  - **MAJOR** = breaking change (detected by OpenAPI semantic diff)
  - **MINOR** = additive (new endpoints/fields)
  - **PATCH** = fixes/clarifications

See `README.md` section "Versioning & Release" for baseline and release workflow details.

## Authentication
- **Scheme:** Bearer tokens
- **Header:** `Authorization: Bearer <token>`
- Tokens may expire; handle 401 by refreshing / re‑authenticating.

## Content Types
- Requests: `application/json` unless explicitly file upload (`multipart/form-data`)
- Responses: `application/json`
- 415 is standardized as: `Unsupported Media Type` (OpenAPI component)

## Errors
Unified envelope (simplified example):
```json
{ "error": "bad_request", "message": "Invalid input" }
```
Guidelines:
- Do not branch on HTTP reason phrases; use the `error` code.
- 429 responses include `Retry-After` header (integer seconds, ceil).

Problem style (future compatible): Some endpoints may evolve toward RFC 7807 structure; existing fields stay stable.

## Rate Limiting
- Certain endpoints are flag / config gated (e.g., exports, imports) with limits per tenant & user.
- On 429: inspect `Retry-After`; implement exponential backoff with jitter.
- Idempotent POSTs (if any) should be safely retried after backoff.

## Contracts & Stability
Our CI enforces semantic diff on the committed OpenAPI baseline:
Breaking (fails CI):
- Removed paths/operations/responses/content-types
- Removed enum values
- Removed properties or newly required properties
- Type / `$ref` / `format` change
- Array: `minItems` increase, `maxItems` decrease
- String: `minLength` introduction/increase, `maxLength` introduction/decrease, `pattern` addition/change

Additions (allowed): new optional properties, new enum values, new endpoints/content-types.

Best practice:
- Monitor CHANGELOG (release workflow prepends latest diff summary).
- Maintain automated contract tests against `/openapi.json`.

## Example – Import Menu (JSON)
**Endpoint:** `POST /import/menu`

Accepts either `multipart/form-data` file upload or raw JSON. Example minimal JSON:
```bash
curl -X POST https://api.example.com/import/menu \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data '{"items":[{"name":"Spaghetti Bolognese"}]}'
```

Successful Response (illustrative):
```json
{
  "ok": true,
  "rows": [ { "title": "Soup", "description": "Tomato", "priority": 1 } ],
  "meta": { "count": 1, "format": "menu" }
}
```

Common Errors:
- 400 invalid payload (missing required field)
- 415 content type / extension mismatch
- 429 rate limited (retry with backoff)

## Change Tracking
CI attaches artifacts:
- `openapi.json` (normalized spec)
- `openapi-extras/openapi-changelog.md`
- `openapi-extras/api-badge.md`

PRs include an OpenAPI diff comment (✅ / 🟡 / ❌) + labels (`api:breaking` / `api:changed`).

## Support
Contact: `henrikjonsson031@gmail.com` (or the address specified in README).
Please include: endpoint, `X-Request-Id` (response header), UTC timestamp, minimal reproduction payload.

## Handling RFC 7807 problems

Clients SHOULD:
1. Branch on HTTP `status` (e.g. 401 → re-auth, 403 → permission UI, 429 → backoff).
2. Display `detail` when safe (validation issues) but avoid exposing raw internal error messages.
3. For validation (422) map `errors.<field>[]` to form field helpers / inline messages.
4. Log `type`, `status`, and `instance` (correlate with server logs via `request_id`).
5. Treat unknown `type` values as generic error (fallback UI) while still logging.

Pseudocode:
```ts
if (resp.status === 422 && body.errors) {
  for (const [field, msgs] of Object.entries(body.errors)) {
    showFieldError(field, msgs.join("; "));
  }
} else if (resp.status === 429) {
  scheduleRetry(resp.headers['Retry-After']);
} else if (resp.status >= 500) {
  toast("Temporary server issue. Please retry.");
}
```

Se även: `docs/problems.md` för alla problemtyper och exempel.
