"""Redis-backed token bucket implementation.

Atomicity via Lua script to avoid race conditions.
Key layout: <prefix>tb:<logical_key>
Value stored as: tokens|last_refill_ms (packed string) or two fields in a hash; we use a simple string for speed.

Lua responsibilities:
1. Read current value (if nil: initialize full bucket - 1 token on first consume).
2. Refill based on elapsed ms.
3. If tokens >= 1: decrement, store updated state, return {1, tokens_remaining, retry_after_ms=0}
4. Else: store state (unchanged tokens), return {0, tokens, retry_after_ms_needed}

Retry-after ms = ceil((1 - tokens)/refill_rate) * 1000.
"""

from __future__ import annotations

import time
from collections.abc import Callable

try:  # pragma: no cover - optional dependency
    import redis  # type: ignore
except Exception:  # pragma: no cover
    redis = None  # type: ignore

from .rate_limiter import RateLimiter

_LUA = """
local key = KEYS[1]
local now_ms = tonumber(ARGV[1])
local capacity = tonumber(ARGV[2])
local refill_rate = tonumber(ARGV[3])  -- tokens per ms * 1000 scaled
local per_ms = tonumber(ARGV[4])
-- fetch existing
local raw = redis.call('GET', key)
local tokens
local last_ms
if not raw then
  tokens = capacity
  last_ms = now_ms
else
  local sep = string.find(raw, ':')
  tokens = tonumber(string.sub(raw, 1, sep-1))
  last_ms = tonumber(string.sub(raw, sep+1))
  if not tokens or not last_ms then
    tokens = capacity
    last_ms = now_ms
  end
end
-- refill
if now_ms > last_ms then
  local elapsed = now_ms - last_ms
  local add = elapsed * refill_rate / 1000.0  -- since refill_rate expressed in tokens/sec *1000 upstream
  tokens = math.min(capacity, tokens + add)
  last_ms = now_ms
end
local allowed = 0
local retry_after_ms = 0
if tokens >= 1.0 then
  tokens = tokens - 1.0
  allowed = 1
else
  local deficit = 1.0 - tokens
  local rate_per_ms = (refill_rate / 1000.0)
  if rate_per_ms <= 0 then
    retry_after_ms = per_ms
  else
    retry_after_ms = math.ceil(deficit / rate_per_ms)
  end
end
-- persist
redis.call('SET', key, string.format('%f:%d', tokens, last_ms), 'PX', per_ms)
return {allowed, string.format('%f', tokens), retry_after_ms}
"""


class RedisTokenBucketRateLimiter(RateLimiter):  # type: ignore[misc]
    def __init__(self, url: str, prefix: str, now_ms_fn: Callable[[], int] | None = None) -> None:
        if redis is None:
            raise RuntimeError("redis library not available")
        self._client = redis.Redis.from_url(url, decode_responses=True)
        self._prefix = f"{prefix}tb:"
        self._script = self._client.register_script(_LUA)
        self._now_ms = now_ms_fn or (lambda: int(time.time() * 1000))

    def _rk(self, logical_key: str) -> str:
        return f"{self._prefix}{logical_key}"

    def allow(self, key: str, quota: int, per_seconds: int) -> bool:
        capacity = quota
        now_ms = self._now_ms()
        per_ms = per_seconds * 1000
        refill_rate = quota  # tokens per second
        result = self._script(keys=[self._rk(key)], args=[now_ms, capacity, refill_rate, per_ms])  # type: ignore[arg-type]
        allowed = int(result[0]) == 1
        return allowed

    def retry_after(self, key: str, per_seconds: int) -> int:
        return 1


__all__ = ["RedisTokenBucketRateLimiter"]
