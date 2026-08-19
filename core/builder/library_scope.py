"""Pure Builder library scope policy.

This module defines a small, immutable contract for future Builder library
ownership, visibility, and lineage rules. It is intentionally framework-free
and does not touch repositories, requests, sessions, or roles mapping.

The policy is conservative:
- tenant isolation is absolute
- community visibility is reserved but disabled in this ticket
- visibility does not imply ownership
- user-owned objects remain private to their owner unless explicitly shared
- shared objects may be readable without becoming writable
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

OwnerScope = Literal["organisation", "site", "user"]
Visibility = Literal["private", "site", "organisation", "community"]

PRIVILEGED_WRITE_ROLES = frozenset({"admin", "editor", "superuser"})
COMMUNITY_SHARING_ENABLED = False


@dataclass(frozen=True, slots=True)
class ActorContext:
    tenant_id: int
    user_id: int
    site_id: str | None
    role: str


@dataclass(frozen=True, slots=True)
class ObjectScope:
    tenant_id: int
    owner_scope: OwnerScope
    owner_site_id: str | None
    owner_user_id: int | None
    visibility: Visibility
    source_object_id: str | None = None


def is_community_sharing_enabled() -> bool:
    """Return whether community sharing is enabled.

    Community is reserved for future use in this ticket and remains disabled.
    """

    return COMMUNITY_SHARING_ENABLED


def can_read_object(actor: ActorContext, object_scope: ObjectScope) -> bool:
    """Return whether the actor may discover/read the object."""

    if actor.tenant_id != object_scope.tenant_id:
        return False

    if object_scope.visibility == "community":
        return False

    if object_scope.visibility == "private":
        return (
            object_scope.owner_user_id is not None
            and actor.user_id == object_scope.owner_user_id
        )

    if object_scope.visibility == "site":
        return (
            object_scope.owner_site_id is not None
            and actor.site_id is not None
            and actor.site_id == object_scope.owner_site_id
        )

    if object_scope.visibility == "organisation":
        return True

    return False


def can_write_object(actor: ActorContext, object_scope: ObjectScope) -> bool:
    """Return whether the actor may mutate the object scope's source object."""

    if actor.tenant_id != object_scope.tenant_id:
        return False

    if object_scope.owner_scope == "user":
        return (
            object_scope.owner_user_id is not None
            and actor.user_id == object_scope.owner_user_id
        )

    if object_scope.owner_scope == "site":
        return (
            actor.role in PRIVILEGED_WRITE_ROLES
            and object_scope.owner_site_id is not None
            and actor.site_id is not None
            and actor.site_id == object_scope.owner_site_id
        )

    if object_scope.owner_scope == "organisation":
        return actor.role in PRIVILEGED_WRITE_ROLES

    return False


def can_fork_object(actor: ActorContext, source_scope: ObjectScope) -> bool:
    """Return whether the actor may fork the source object."""

    return can_read_object(actor, source_scope)


def fork_object_scope(
    actor: ActorContext,
    source_scope: ObjectScope,
    source_object_id: str,
) -> ObjectScope:
    """Build the scope for a forked object.

    Forks are user-owned and private by default. The source object's ownership is
    unchanged; this function only models the new scope/lineage contract.
    """

    canonical_source_id = str(source_object_id).strip()
    if not canonical_source_id:
        raise ValueError("source_object_id must be a non-empty string")

    return ObjectScope(
        tenant_id=actor.tenant_id,
        owner_scope="user",
        owner_site_id=actor.site_id,
        owner_user_id=actor.user_id,
        visibility="private",
        source_object_id=canonical_source_id,
    )


def inherit_canonical_scope(canonical_scope: ObjectScope) -> ObjectScope:
    """Return a child scope that inherits visibility/access from its canonical parent.

    This helper documents the contract for Component details, recipe/method data,
    Component aliases, and Composition aliases: they do not get independent
    ownership and instead inherit the canonical object's scope.
    """

    return canonical_scope
