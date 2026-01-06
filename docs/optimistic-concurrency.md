# Optimistic Concurrency Control

## Overview

The admin API implements optimistic concurrency control using HTTP ETags and If-Match headers to prevent lost updates when multiple clients modify the same resource concurrently.

## How It Works

### ETag Response Headers

When you fetch or modify a resource (users, roles, feature flags), the server includes an `ETag` header in the response:

```http
GET /admin/users/123
X-User-Role: admin
X-Tenant-Id: 1

HTTP/1.1 200 OK
ETag: W/"a1b2c3d4e5f6"
Content-Type: application/json

{
  "id": "123",
  "email": "user@example.com",
  "role": "editor",
  "updated_at": "2025-01-15T10:30:00Z"
}
```

The ETag represents the current state of the resource. It changes whenever the resource is modified.

### If-Match Request Headers

When modifying a resource, include the `If-Match` header with the ETag value you received:

```http
PATCH /admin/users/123
X-User-Role: admin
X-Tenant-Id: 1
X-CSRF-Token: <token>
If-Match: W/"a1b2c3d4e5f6"
Content-Type: application/json

{
  "role": "admin"
}
```

## Behavior by Operation

### DELETE Operations (Strict)

DELETE requires an `If-Match` header. Without it, you get a 400 Bad Request:

```http
DELETE /admin/users/123
# Missing If-Match header

HTTP/1.1 400 Bad Request
Content-Type: application/problem+json

{
  "type": "about:blank",
  "title": "Bad Request",
  "status": 400,
  "detail": "If-Match header required for DELETE operations",
  "invalid_params": [
    {"name": "If-Match", "reason": "required"}
  ]
}
```

### PATCH/PUT Operations (Lenient)

PATCH and PUT operations allow operation without `If-Match` (no-op mode), but if you do provide it and it doesn't match, you get a 412:

```http
PATCH /admin/users/123
If-Match: W/"outdated-etag"

HTTP/1.1 412 Precondition Failed
Content-Type: application/problem+json

{
  "type": "about:blank",
  "title": "Precondition Failed",
  "status": 412,
  "detail": "Resource has been modified. Please fetch the latest version and retry."
}
```

## Affected Endpoints

| Endpoint | DELETE | PATCH | PUT |
|----------|--------|-------|-----|
| `/admin/users/<id>` | ✅ Strict | ✅ Lenient | ✅ Lenient |
| `/admin/roles/<id>` | N/A | ✅ Lenient | N/A |
| `/admin/feature-flags/<key>` | N/A | ✅ Lenient | N/A |

## Client Workflow

### Basic Flow

1. **Fetch** the resource (GET) and save the ETag
2. **Modify** locally
3. **Send** update with `If-Match: <saved-etag>`
4. **Handle** responses:
   - `200 OK`: Success, save new ETag
   - `412 Precondition Failed`: Resource changed, refetch and merge/retry
   - `400 Bad Request`: Missing If-Match (DELETE only)

### Example: Safe User Update

```python
import requests

# 1. Fetch current state
resp = requests.get(
    "https://api.example.com/admin/users/123",
    headers={"X-User-Role": "admin", "X-Tenant-Id": "1"}
)
user = resp.json()
etag = resp.headers["ETag"]

# 2. Modify
user["role"] = "admin"

# 3. Update with ETag
resp = requests.patch(
    "https://api.example.com/admin/users/123",
    json={"role": "admin"},
    headers={
        "X-User-Role": "admin",
        "X-Tenant-Id": "1",
        "X-CSRF-Token": "<token>",
        "If-Match": etag
    }
)

if resp.status_code == 412:
    # Resource was modified by another client
    # Refetch, merge changes, and retry
    print("Conflict detected - resource was modified")
elif resp.status_code == 200:
    # Success - save new ETag for future updates
    new_etag = resp.headers["ETag"]
    print(f"Updated successfully, new ETag: {new_etag}")
```

## ETag Format

ETags are weak entity tags in the format `W/"<hash>"`:

- Weak ETags (`W/`) indicate semantic equivalence
- The hash is computed from the resource ID and `updated_at` timestamp
- Changes to `updated_at` will generate a new ETag

## Benefits

- **Prevents lost updates**: Concurrent modifications are detected
- **No locking required**: Resources remain available to all clients
- **Clear failure modes**: 412 responses clearly indicate conflicts
- **HTTP standard**: Uses standard HTTP caching/concurrency headers

## Best Practices

1. **Always include If-Match for DELETE**: Required by the API
2. **Include If-Match for PATCH/PUT when possible**: Prevents accidental overwrites
3. **Handle 412 gracefully**: Implement conflict resolution (merge or user prompt)
4. **Store ETags with cached data**: Associate ETags with your local copies
5. **Refetch on 412**: Get the latest state before retrying

## Testing

The concurrency behavior is covered by tests in `tests/admin/test_admin_etag_concurrency.py` and `tests/test_concurrency.py`.

## Implementation

The concurrency control is implemented in `core/concurrency.py` with helpers for:
- `compute_etag()`: Generate ETags from entity state
- `validate_if_match()`: Validate If-Match headers (strict/lenient modes)
- `set_etag_header()`: Add ETag to responses
- `make_precondition_failed_response()`: Generate 412 responses
- `make_bad_request_response()`: Generate 400 responses
