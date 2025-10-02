from __future__ import annotations

import datetime as dt
import os
from typing import Protocol


class WarnLimiter(Protocol):  # pragma: no cover - protocol
    def allow(self, tenant_id: int, today: dt.date) -> bool: ...

class InProcessWarnLimiter:
    """Simple per-tenant-per-day limiter (process local)."""
    def __init__(self) -> None:
        self._last: dict[int, dt.date] = {}
    def allow(self, tenant_id: int, today: dt.date) -> bool:
        last = self._last.get(tenant_id)
        if last == today:
            return False
        self._last[tenant_id] = today
        return True

_limiter: WarnLimiter = InProcessWarnLimiter()

def set_warn_limiter(limiter: WarnLimiter) -> None:
    global _limiter
    _limiter = limiter

_DEF_ENV_FLAG = "LEGACY_COOK_WARN"

def warn_phase_enabled() -> bool:
    return os.getenv(_DEF_ENV_FLAG, "").lower() in ("1","true","yes","on")

def should_warn(tenant_id: int) -> bool:
    if not warn_phase_enabled():
        return False
    today = dt.date.today()
    return _limiter.allow(tenant_id, today)
