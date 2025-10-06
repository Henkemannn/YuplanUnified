# Problem Types

This page documents the RFC 7807 `application/problem+json` problem detail types the API emits.

See also: README.md section "Error model (RFC 7807)" for the canonical description and registry rationale.

## Overview Table

| type (URI) | title | http status | Beskrivning | Exempel |
|------------|-------|-------------|-------------|---------|
| https://api.example.com/problems/validation | Validation failed | 400 / 422 | Ogiltig payload eller query-parametrar | [Example](#validation) |
| https://api.example.com/problems/unauthorized | Unauthorized | 401 | Saknar eller ogiltig auktorisering | [Example](#unauthorized) |
| https://api.example.com/problems/forbidden | Forbidden | 403 | Otillräckliga rättigheter / roll | [Example](#forbidden) |
| https://api.example.com/problems/not-found | Resource not found | 404 | Resursen finns inte | [Example](#not-found) |
| https://api.example.com/problems/unsupported-media-type | Unsupported media type | 415 | Fel `Content-Type` | [Example](#unsupported-media-type) |
| https://api.example.com/problems/rate-limited | Rate limit exceeded | 429 | För många anrop (Retry-After ges) | [Example](#rate-limited) |
| https://api.example.com/problems/internal | Internal error | 500 | Oväntat fel (anonymiserat) | [Example](#internal) |

## Validation
```json
{
  "type": "https://api.example.com/problems/validation",
  "title": "Validation failed",
  "status": 422,
  "detail": "title must not be empty",
  "errors": {"title": ["must not be empty", "min length is 1"]},
  "instance": "urn:request:123e4567-e89b-12d3-a456-426614174000"
}
```

## Unauthorized
```json
{
  "type": "https://api.example.com/problems/unauthorized",
  "title": "Unauthorized",
  "status": 401,
  "detail": "Bearer token missing or invalid",
  "instance": "urn:request:2c2c1d2b-aaaa-bbbb-cccc-ddddeeeeffff"
}
```

## Forbidden
```json
{
  "type": "https://api.example.com/problems/forbidden",
  "title": "Forbidden",
  "status": 403,
  "detail": "Requires role admin",
  "instance": "urn:request:778899aa-bb11-cc22-dd33-ee44ff55aa66"
}
```

## Not-Found
```json
{
  "type": "https://api.example.com/problems/not-found",
  "title": "Resource not found",
  "status": 404,
  "detail": "Menu item 999 not found",
  "instance": "urn:request:a1b2c3d4-e5f6-1122-3344-556677889900"
}
```

## Unsupported-Media-Type
```json
{
  "type": "https://api.example.com/problems/unsupported-media-type",
  "title": "Unsupported media type",
  "status": 415,
  "detail": "Expected Content-Type application/json",
  "instance": "urn:request:0f1e2d3c-4b5a-6978-8899-aabbccddeeff"
}
```

## Rate-Limited
```json
{
  "type": "https://api.example.com/problems/rate-limited",
  "title": "Rate limit exceeded",
  "status": 429,
  "detail": "Try again later",
  "instance": "urn:request:123abc45-678d-9012-ef34-56789abc0000"
}
```
Headers (example): `Retry-After: 37`

## Internal
```json
{
  "type": "https://api.example.com/problems/internal",
  "title": "Internal error",
  "status": 500,
  "detail": "Unexpected server error",
  "instance": "urn:request:deadbeef-dead-beef-dead-beefdeadbeef"
}
```

## Client Handling Cheatsheet
1. Branch on `status` (401 re-auth, 403 permission UI, 429 backoff with Retry-After, 5xx retry or failover).
2. Display `detail` when safe; never show raw stack traces.
3. For 422 map `errors.<field>[]` to form field inline messages.
4. Log `type`, `status`, `instance` (correlate with server logs via `request_id`).

## Versioning Note
This document mirrors the registry in README. Additions (new problem types) are additive & backwards compatible. Removals or semantic changes require a deprecation cycle per the Deprecation policy.
