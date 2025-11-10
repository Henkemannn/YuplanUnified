from __future__ import annotations

import re


def make_collection_etag(resource: str, scope: str, version: int) -> str:
    """Create a weak ETag for collections.

    Pattern per Phase D spec: W/"<resource>:<scope>:v<MAX(version)>"
    Caller is responsible for composing resource (e.g. "admin:departments") and scope
    (e.g. "site:<site_id>" or "week:<week>").
    """
    return f'W/"{resource}:{scope}:v{int(version)}"'


def make_etag(namespace: str, kind: str, ident: str, version: int) -> str:
    """Create a weak ETag string like: W/"admin:dept:{uuid}:v{n}"""
    return f'W/"{namespace}:{kind}:{ident}:v{int(version)}"'


# Allow identifier to include colons (e.g., "week:51") by capturing greedily until the last ":v<digits>" segment
_IF_MATCH_RE = re.compile(r"W/\"(?P<ns>[^:]+):(?P<kind>[^:]+):(?P<id>.+):v(?P<v>\d+)\"")


def parse_if_match(raw: str | None) -> tuple[str | None, str | None, str | None, int | None]:
    """Parse If-Match header and return (namespace, kind, id, version).

    Returns (None,None,None,None) if not parseable.
    """
    if not raw:
        return None, None, None, None
    m = _IF_MATCH_RE.fullmatch(raw.strip())
    if not m:
        return None, None, None, None
    ns = m.group("ns")
    kind = m.group("kind")
    ident = m.group("id")
    v = int(m.group("v"))
    return ns, kind, ident, v


class ConcurrencyError(RuntimeError):
    pass
