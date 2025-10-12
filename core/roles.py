"""Role adapter (Pocket 6 harmonization).

Defines a narrow canonical role set and a mapping from legacy/app roles.

CanonicalRole: roles used internally for authorization logic
AppRole: legacy / external labels currently present in the system
RoleLike: union accepted at API boundary; converted via to_canonical()
"""

from __future__ import annotations

from typing import Literal

CanonicalRole = Literal["superuser", "admin", "editor", "viewer"]
AppRole = Literal["cook", "unit_portal"]  # extend if/when more legacy labels appear
RoleLike = CanonicalRole | AppRole

# Mapping legacy roles -> canonical baseline
ROLE_MAP: dict[AppRole, CanonicalRole] = {
    "cook": "viewer",  # read-mostly; limited modification rights historically
    "unit_portal": "editor",  # elevated edit capabilities within a unit
}


def to_canonical(role: RoleLike) -> CanonicalRole:
    if role in ROLE_MAP:  # type: ignore[operator]
        return ROLE_MAP[role]  # type: ignore[index]
    return role  # type: ignore[return-value]


__all__ = [
    "CanonicalRole",
    "AppRole",
    "RoleLike",
    "ROLE_MAP",
    "to_canonical",
]
