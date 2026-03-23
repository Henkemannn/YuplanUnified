from __future__ import annotations

import re


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_key(value: str) -> str:
    normalized = _NON_ALNUM_RE.sub("_", str(value).strip().lower())
    normalized = normalized.strip("_")
    return normalized


def build_combination_key(form: str, category_keys: list[str]) -> str:
    normalized_form = normalize_key(form)
    normalized_categories = sorted(
        key for key in (normalize_key(category) for category in category_keys) if key
    )
    if not normalized_categories:
        return normalized_form
    return "__".join([normalized_form, *normalized_categories])
