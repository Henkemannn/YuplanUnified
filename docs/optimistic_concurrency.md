# Optimistic Concurrency Control

YuplanUnified uses ETags and HTTP conditional headers (If-Match / If-None-Match) for optimistic concurrency on admin resources.

## Overview

Optimistic concurrency allows multiple clients to safely update shared resources without exclusive locks. Clients receive an ETag with each resource representation and must provide it in conditional requests to modify the resource.

## Resources with Concurrency Support

- **Admin Users** (`/admin/users/{id}`)
- **Admin Roles** (`/admin/roles/{id}`)
- **Feature Flags** (`/admin/feature-flags/{key}`)

## Headers

### ETag (Response Header)

All GET requests for supported resources return a weak ETag in the response header:

```
ETag: W/"8f3c2a9b4e5d6c1f"
```

### If-Match (Request Header)

Required for all mutation operations (PUT, PATCH, DELETE) on resources with concurrency support:

```
If-Match: W/"8f3c2a9b4e5d6c1f"
```

- **Wildcard**: `If-Match: *` bypasses ETag validation (matches any representation)
- **Multiple tags**: `If-Match: "tag1", "tag2"` matches if any tag is current

### If-None-Match (Request Header)

Optional for GET requests to support conditional caching:

```
If-None-Match: W/"8f3c2a9b4e5d6c1f"
```

Returns **304 Not Modified** (empty body) if the ETag matches.

## Response Codes

### 200 OK
Mutation succeeded. Response includes updated ETag.

### 304 Not Modified
GET request with If-None-Match matched current ETag. No body returned.

### 400 Bad Request
If-Match or If-None-Match header is malformed or invalid.

**Problem Details Shape** (RFC 7807):
```json
{
  "type": "about:blank",
  "title": "Bad Request",
  "status": 400,
  "detail": "Invalid header",
  "invalid_params": [
    {"name": "If-Match", "reason": "invalid_header"}
  ]
}
```

### 412 Precondition Failed
If-Match did not match the current ETag (resource was modified since client last read it).

**Problem Details Shape** (RFC 7807):
```json
{
  "type": "about:blank",
  "title": "Precondition Failed",
  "status": 412,
  "detail": "If-Match did not match",
  "resource": "admin_user",
  "resource_id": "123",
  "expected_etag": "W/\"current\"",
  "got_etag": "W/\"stale\""
}
```

## Mutation Behavior

### DELETE (strict)
- **Always requires** valid If-Match header
- Returns **412** if If-Match is missing or doesn't match
- Returns **204 No Content** on success

### PATCH / PUT (no-op allowed)
- **Requires If-Match only when a change would occur**
- Idempotent no-op requests (same values) succeed without If-Match
- Returns **412** if If-Match is required but missing/mismatched
- Returns **200 OK** with updated ETag on success

## Example Workflow

### 1. Fetch current resource

```http
GET /admin/users/42 HTTP/1.1
Authorization: Bearer <token>
```

Response:
```http
HTTP/1.1 200 OK
ETag: W/"abc123"
Content-Type: application/json

{"id": "42", "email": "user@example.com", "role": "viewer", "updated_at": "2025-01-15T10:30:00Z"}
```

### 2. Update resource

```http
PATCH /admin/users/42 HTTP/1.1
Authorization: Bearer <token>
X-CSRF-Token: <csrf>
If-Match: W/"abc123"
Content-Type: application/json

{"role": "editor"}
```

Success response:
```http
HTTP/1.1 200 OK
ETag: W/"def456"
Content-Type: application/json

{"id": "42", "email": "user@example.com", "role": "editor", "updated_at": "2025-01-15T10:35:00Z"}
```

### 3. Handle conflicts

If another client modified the resource between steps 1 and 2:

```http
HTTP/1.1 412 Precondition Failed
Content-Type: application/problem+json

{
  "type": "about:blank",
  "title": "Precondition Failed",
  "status": 412,
  "detail": "If-Match did not match",
  "resource": "admin_user",
  "resource_id": "42",
  "expected_etag": "W/\"xyz789\"",
  "got_etag": "W/\"abc123\""
}
```

**Resolution**: Re-fetch the resource (step 1) to get the latest ETag and retry.

## Testing Notes

### Windows / Python 3.13

OpenAPI validation tests may be skipped locally on Windows with Python 3.13 due to platform-specific issues with the `openapi-spec-validator` library. CI runs these tests on Ubuntu with Python 3.11.

To skip OpenAPI tests locally:
```bash
pytest -k "not openapi"
```

CI on Ubuntu/Python 3.11 will continue to validate the OpenAPI specification as usual.

## References

- [RFC 7807 - Problem Details for HTTP APIs](https://datatracker.ietf.org/doc/html/rfc7807)
- [RFC 7232 - Conditional Requests](https://datatracker.ietf.org/doc/html/rfc7232)
- [MDN: ETag](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag)
- [MDN: If-Match](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/If-Match)
