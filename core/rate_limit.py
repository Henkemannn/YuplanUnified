from __future__ import annotations

import time
from typing import Dict, Tuple

from flask import request

# In-memory simple rate limiter (per-process). For production scale: replace with Redis.
# Key: (tenant_id, user_id, bucket, minute_epoch)
_store: Dict[Tuple[int|None,int|None,str,int], int] = {}

class RateLimitExceeded(Exception):
    def __init__(self, bucket: str, limit: int):
        super().__init__(bucket)
        self.bucket = bucket
        self.limit = limit

def rate_limited_response(retry_after: int | None = None):  # lightweight central helper
    from flask import jsonify
    payload: dict[str, str | int | None] = {'error': 'rate_limited', 'message': 'Too many requests'}
    if retry_after is not None:
        payload['retry_after'] = int(retry_after)
    resp = jsonify(payload)
    resp.status_code = 429
    if retry_after is not None:
        resp.headers['Retry-After'] = str(retry_after)
    return resp


def allow(tenant_id: int|None, user_id: int|None, bucket: str, limit_per_minute: int, *, testing: bool=False):
    # In testing mode we often skip limits; allow override via special header to force enforce for tests
    force_header = request.headers.get('X-Force-Rate-Limit') if request else None
    if testing and not force_header:
        return
    if force_header is not None:
        try:
            forced_limit = int(request.headers.get('X-Force-Rate-Limit-Limit', '3'))
            limit_per_minute = min(limit_per_minute, forced_limit)
        except Exception:
            limit_per_minute = min(limit_per_minute, 3)
    now = int(time.time())
    minute = now // 60
    key = (tenant_id, user_id, bucket, minute)
    cnt = _store.get(key, 0) + 1
    _store[key] = cnt
    if cnt > limit_per_minute:
        raise RateLimitExceeded(bucket, limit_per_minute)


def remaining(tenant_id: int|None, user_id: int|None, bucket: str, limit_per_minute: int):
    now = int(time.time())
    minute = now // 60
    key = (tenant_id, user_id, bucket, minute)
    return max(0, limit_per_minute - _store.get(key, 0))
