from __future__ import annotations

import logging
import os
from typing import Any, Dict

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

log = logging.getLogger(__name__)


def load_yaml(path: str) -> dict[str, Any]:
    """Load a YAML file and return dict; return {} on missing file or parse error.

    - Uses yaml.safe_load
    - Returns {} if PyYAML not installed, file missing, or parse error
    """
    if yaml is None:
        log.warning("PyYAML not available; cannot load %s", path)
        return {}
    try:
        if not os.path.exists(path):
            log.warning("YAML file not found: %s", path)
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            if not isinstance(data, dict):
                log.warning("YAML root is not an object: %s", path)
                return {}
            return data
    except Exception:
        log.exception("Failed to load YAML: %s", path)
        return {}


essential_keys = ("paths", "tags", "components")


def _merge_paths(base: Dict[str, Any], extra: Dict[str, Any]) -> None:
    b_paths: Dict[str, Any] = base.setdefault("paths", {})
    e_paths: Dict[str, Any] = extra.get("paths", {}) or {}
    for k, v in e_paths.items():
        if k in b_paths:
            log.warning("OpenAPI merge conflict on path %s — keeping base", k)
            continue
        b_paths[k] = v


def _merge_tags(base: Dict[str, Any], extra: Dict[str, Any]) -> None:
    b_tags = list(base.setdefault("tags", []))
    e_tags = list(extra.get("tags", []) or [])
    # Merge by tag.name uniqueness
    have = {t.get("name") for t in b_tags if isinstance(t, dict)}
    for t in e_tags:
        name = t.get("name") if isinstance(t, dict) else None
        if name and name not in have:
            b_tags.append(t)
            have.add(name)
    base["tags"] = b_tags


def _merge_schemas(base: Dict[str, Any], extra: Dict[str, Any]) -> None:
    b_comp: Dict[str, Any] = base.setdefault("components", {})
    e_comp: Dict[str, Any] = extra.get("components", {}) or {}
    b_schemas: Dict[str, Any] = b_comp.setdefault("schemas", {})
    e_schemas: Dict[str, Any] = e_comp.get("schemas", {}) or {}
    for k, v in e_schemas.items():
        if k in b_schemas:
            log.warning("OpenAPI merge conflict on schema %s — keeping base", k)
            continue
        b_schemas[k] = v


def merge_openapi(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    """Merge OpenAPI dicts.

    Rules:
    - Merge paths, tags, components.schemas
    - On key conflict, keep base and log a warning
    - Return the same base dict for chaining
    """
    if not isinstance(base, dict) or not isinstance(extra, dict):
        return base
    _merge_paths(base, extra)
    _merge_tags(base, extra)
    _merge_schemas(base, extra)
    return base
