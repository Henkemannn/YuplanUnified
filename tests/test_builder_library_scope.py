from core.builder.library_scope import (
    ActorContext,
    COMMUNITY_SHARING_ENABLED,
    ObjectScope,
    can_fork_object,
    can_read_object,
    can_write_object,
    fork_object_scope,
    inherit_canonical_scope,
    is_community_sharing_enabled,
)


def test_tenant_a_cannot_read_tenant_b_organisation_object() -> None:
    actor = ActorContext(tenant_id=1, user_id=101, site_id="site-a", role="cook")
    object_scope = ObjectScope(
        tenant_id=2,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
    )

    assert can_read_object(actor, object_scope) is False


def test_tenant_a_cannot_read_tenant_b_community_object_while_disabled() -> None:
    actor = ActorContext(tenant_id=1, user_id=101, site_id="site-a", role="cook")
    object_scope = ObjectScope(
        tenant_id=2,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="community",
    )

    assert COMMUNITY_SHARING_ENABLED is False
    assert is_community_sharing_enabled() is False
    assert can_read_object(actor, object_scope) is False


def test_same_tenant_cannot_read_community_object_while_disabled() -> None:
    actor = ActorContext(tenant_id=1, user_id=101, site_id="site-a", role="cook")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="community",
    )

    assert is_community_sharing_enabled() is False
    assert can_read_object(actor, object_scope) is False


def test_cook_a_can_read_own_private_user_object() -> None:
    actor = ActorContext(tenant_id=1, user_id=101, site_id="site-a", role="cook")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id="site-a",
        owner_user_id=101,
        visibility="private",
    )

    assert can_read_object(actor, object_scope) is True


def test_cook_b_cannot_read_cook_a_private_object() -> None:
    actor = ActorContext(tenant_id=1, user_id=202, site_id="site-a", role="cook")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id="site-a",
        owner_user_id=101,
        visibility="private",
    )

    assert can_read_object(actor, object_scope) is False


def test_cook_b_same_site_can_read_cook_a_site_visible_object() -> None:
    actor = ActorContext(tenant_id=1, user_id=202, site_id="site-a", role="cook")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id="site-a",
        owner_user_id=101,
        visibility="site",
    )

    assert can_read_object(actor, object_scope) is True


def test_cook_b_cannot_write_cook_a_site_visible_object() -> None:
    actor = ActorContext(tenant_id=1, user_id=202, site_id="site-a", role="cook")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id="site-a",
        owner_user_id=101,
        visibility="site",
    )

    assert can_write_object(actor, object_scope) is False


def test_cook_a_can_write_own_personal_object() -> None:
    actor = ActorContext(tenant_id=1, user_id=101, site_id="site-a", role="cook")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id="site-a",
        owner_user_id=101,
        visibility="private",
    )

    assert can_write_object(actor, object_scope) is True


def test_cook_can_read_same_tenant_organisation_object() -> None:
    actor = ActorContext(tenant_id=1, user_id=202, site_id="site-b", role="cook")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
    )

    assert can_read_object(actor, object_scope) is True


def test_cook_cannot_write_organisation_original_merely_because_visible() -> None:
    actor = ActorContext(tenant_id=1, user_id=202, site_id="site-b", role="cook")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
    )

    assert can_write_object(actor, object_scope) is False


def test_privileged_editor_can_write_organisation_owned_object() -> None:
    actor = ActorContext(tenant_id=1, user_id=303, site_id="site-b", role="editor")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
    )

    assert can_write_object(actor, object_scope) is True


def test_site_visible_object_is_not_visible_at_another_site() -> None:
    actor = ActorContext(tenant_id=1, user_id=202, site_id="site-b", role="cook")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id="site-a",
        owner_user_id=101,
        visibility="site",
    )

    assert can_read_object(actor, object_scope) is False


def test_readable_shared_object_can_be_forked() -> None:
    actor = ActorContext(tenant_id=1, user_id=202, site_id="site-a", role="cook")
    source_scope = ObjectScope(
        tenant_id=1,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )

    assert can_fork_object(actor, source_scope) is True
    forked_scope = fork_object_scope(actor, source_scope, "composition-001")
    assert forked_scope.owner_scope == "user"
    assert forked_scope.owner_user_id == actor.user_id
    assert forked_scope.owner_site_id is None
    assert forked_scope.visibility == "private"
    assert forked_scope.source_object_id == "composition-001"


def test_fork_does_not_mutate_source_scope() -> None:
    actor = ActorContext(tenant_id=1, user_id=202, site_id="site-a", role="cook")
    source_scope = ObjectScope(
        tenant_id=1,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="organisation",
        source_object_id=None,
    )

    original_snapshot = source_scope
    forked_scope = fork_object_scope(actor, source_scope, "composition-001")

    assert source_scope == original_snapshot
    assert forked_scope != source_scope
    assert forked_scope.owner_scope == "user"
    assert forked_scope.source_object_id == "composition-001"
    assert source_scope.owner_scope == "organisation"
    assert source_scope.visibility == "organisation"
    assert source_scope.source_object_id is None


def test_inheritance_contract_preserves_canonical_scope() -> None:
    canonical_scope = ObjectScope(
        tenant_id=1,
        owner_scope="organisation",
        owner_site_id=None,
        owner_user_id=None,
        visibility="site",
        source_object_id="composition-001",
    )

    child_scope = inherit_canonical_scope(canonical_scope)

    assert child_scope is canonical_scope
    assert child_scope == canonical_scope
    assert child_scope.source_object_id == "composition-001"
    assert canonical_scope.source_object_id == "composition-001"
    assert canonical_scope.owner_scope == "organisation"


def test_inherited_child_does_not_create_new_lineage() -> None:
    canonical_scope = ObjectScope(
        tenant_id=1,
        owner_scope="site",
        owner_site_id="site-a",
        owner_user_id=None,
        visibility="site",
        source_object_id="composition-002",
    )

    child_scope = inherit_canonical_scope(canonical_scope)

    assert child_scope is canonical_scope
    assert child_scope.source_object_id == canonical_scope.source_object_id
    assert child_scope.visibility == canonical_scope.visibility
    assert child_scope.owner_scope == canonical_scope.owner_scope


def test_visibility_does_not_equal_ownership() -> None:
    actor = ActorContext(tenant_id=1, user_id=202, site_id="site-a", role="cook")
    object_scope = ObjectScope(
        tenant_id=1,
        owner_scope="user",
        owner_site_id="site-a",
        owner_user_id=101,
        visibility="site",
    )

    assert object_scope.owner_scope == "user"
    assert object_scope.visibility == "site"
    assert can_read_object(actor, object_scope) is True
    assert can_write_object(actor, object_scope) is False
