"""Per-tenant rate limit registry (strict pocket).

Resolves (tenant_id, name) -> LimitDefinition with resolution order:
1. Tenant override (key: tenant:<id>:<name>)
2. Global default (key: <name>)
3. Fallback safe default (quota=5, per_seconds=60)

Environment configuration:
- FEATURE_LIMITS_JSON: JSON object of tenant overrides + optionally defaults (mixed allowed)
- FEATURE_LIMITS_DEFAULTS_JSON: JSON object of global defaults

Public API:
- parse_limits(raw) -> (tenant_overrides, defaults)
- get_limit(tenant_id, name) -> (LimitDefinition, source)
- refresh(raw_overrides, raw_defaults) to reload in place (idempotent)

Clamps:
- quota >= 1 (values <=0 -> 1)
- per_seconds in [1, 86400]

Thread-safety: simple module-level dicts; acceptable for current single-process usage.
"""
from __future__ import annotations

from json import loads
from typing import Any, Dict, Mapping, MutableMapping, Tuple, TypedDict

from . import metrics as metrics_mod

class LimitDefinition(TypedDict):
    quota: int
    per_seconds: int

_TenantMap = Dict[str, LimitDefinition]
_DefaultMap = Dict[str, LimitDefinition]

_tenant_limits: _TenantMap = {}
_default_limits: _DefaultMap = {}

_FALLBACK: LimitDefinition = {"quota": 5, "per_seconds": 60}
_MAX_WINDOW = 86400


def _clamp(q: Any, p: Any) -> LimitDefinition:
    try:
        quota = int(q)
    except Exception:
        quota = _FALLBACK["quota"]
    if quota < 1:
        quota = 1
    try:
        per = int(p)
    except Exception:
        per = _FALLBACK["per_seconds"]
    if per < 1:
        per = 1
    if per > _MAX_WINDOW:
        per = _MAX_WINDOW
    return {"quota": quota, "per_seconds": per}


def parse_limits(raw: str | Mapping[str, Any]) -> Tuple[_TenantMap, _DefaultMap]:
    if isinstance(raw, str):
        try:
            data = loads(raw or "{}")
        except Exception:
            return {}, {}
    else:
        data = dict(raw)
    tenant: _TenantMap = {}
    default: _DefaultMap = {}
    for k, v in data.items():
        if not isinstance(v, Mapping):
            continue
        quota = v.get("quota")
        per = v.get("per") or v.get("per_seconds")
        ld = _clamp(quota, per)
        if k.startswith("tenant:"):
            tenant[k] = ld
        else:
            default[k] = ld
    return tenant, default


def load_from_env(overrides_raw: Any, defaults_raw: Any) -> None:
    # Helper to load from two raw sources (string or dict)
    tenant_map: _TenantMap = {}
    default_map: _DefaultMap = {}
    t_over, t_def = parse_limits(overrides_raw) if overrides_raw else ({}, {})
    d_over, d_def = parse_limits(defaults_raw) if defaults_raw else ({}, {})
    # overrides may contain both tenant + defaults; defaults_raw only defaults
    tenant_map.update(t_over)
    tenant_map.update(d_over)  # unlikely
    default_map.update(t_def)
    default_map.update(d_def)
    _tenant_limits.clear(); _tenant_limits.update(tenant_map)
    _default_limits.clear(); _default_limits.update(default_map)


def refresh(overrides_raw: Any, defaults_raw: Any) -> None:
    load_from_env(overrides_raw, defaults_raw)


def get_limit(tenant_id: int, name: str) -> Tuple[LimitDefinition, str]:
    t_key = f"tenant:{tenant_id}:{name}"
    if t_key in _tenant_limits:
        ld = _tenant_limits[t_key]
        metrics_mod.increment("rate_limit.lookup", {"name": name, "source": "tenant"})
        return ld, "tenant"
    if name in _default_limits:
        ld = _default_limits[name]
        metrics_mod.increment("rate_limit.lookup", {"name": name, "source": "default"})
        return ld, "default"
    metrics_mod.increment("rate_limit.lookup", {"name": name, "source": "fallback"})
    return _FALLBACK, "fallback"

__all__ = [
    "LimitDefinition",
    "parse_limits",
    "get_limit",
    "refresh",
    "load_from_env",
]
