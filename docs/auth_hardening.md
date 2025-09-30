# Auth Hardening

Implemented: basic in-memory rate limiting for /auth/login

Config key: AUTH_RATE_LIMIT (placed directly in Flask config)
Example:
```
AUTH_RATE_LIMIT = {
  'window_sec': 300,      # sliding window period for counting failures
  'max_failures': 5,      # number of failed attempts allowed inside window before lock
  'lock_sec': 900         # lock duration once threshold hit
}
```

Behavior:
1. Keyed by combination: email + remote IP.
2. On each failed attempt failures += 1. When failures >= max_failures account is locked immediately (response 429 rate_limited) and lock_until set to now + lock_sec.
3. While locked further attempts (even with correct password) return 429 until lock_until passes.
4. Successful login clears the entry entirely (failures reset).
5. Window sliding: if current_time - first_attempt_time > window_sec we reset failures/start time.

Notes & Limitations:
- In-memory only; restarts clear state; multiple processes not synchronized.
- Remote IP may be a proxy; integrate X-Forwarded-For parsing behind trusted proxy later.
- Does not yet track per-tenant global lockouts or exponential backoff.
- Could promote to Redis or DB table for horizontal scaling.

Future Enhancements:
- Add per-IP global counters.
- Add optional captcha trigger after threshold.
- Alerting hook (e.g. to metrics) on lock events.
- Optionally store hashed email tokens instead of plaintext keys.
