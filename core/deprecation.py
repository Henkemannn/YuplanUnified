from __future__ import annotations

import os
from collections.abc import Iterable

from flask import Response

from .metrics import increment

DEFAULT_SUNSET = os.getenv("DEPRECATION_NOTES_TASKS_SUNSET", "Wed, 01 Jan 2026 00:00:00 GMT")
DEFAULT_URL = os.getenv(
    "DEPRECATION_NOTES_TASKS_URL", "https://example.com/docs/deprecations#notes-tasks-alias"
)


def apply_deprecation(
    resp: Response,
    *,
    aliases: Iterable[str],
    endpoint: str,
    sunset: str | None = None,
    url: str | None = None,
) -> None:
    """Attach RFC 8594 deprecation headers for legacy alias keys.

    Also emits a telemetry metric capturing endpoint + alias list.
    Safe: never raises (swallows metric backend errors).
    """
    sunset_hdr = sunset or DEFAULT_SUNSET
    url_hdr = url or DEFAULT_URL
    alias_list = ",".join(aliases)
    resp.headers["Deprecation"] = "true"
    resp.headers["Sunset"] = sunset_hdr
    resp.headers["Link"] = f'<{url_hdr}>; rel="deprecation"'
    resp.headers["X-Deprecated-Alias"] = alias_list
    try:  # pragma: no cover - defensive: metric backend may be noop/misconfigured
        increment("deprecation.alias.emitted", {"endpoint": endpoint, "aliases": alias_list})
    except Exception:  # noqa: BLE001
        pass


__all__ = ["apply_deprecation", "DEFAULT_SUNSET", "DEFAULT_URL"]
