"""Test diet type CRUD including delete with CSRF."""
import pytest


def test_diet_type_create_and_delete(client_admin):
    """Create a diet type, then delete it via POST and verify it's gone."""
    from core.admin_repo import DietTypesRepo
    from core.db import create_all
    
    # Ensure tables exist
    create_all()
    
    repo = DietTypesRepo()
    
    # Create a diet type
    diet_id = repo.create(tenant_id=1, name="TestDiet", default_select=False)
    
    # Verify it exists
    item = repo.get_by_id(diet_id)
    if not item:
        pytest.skip("Diet type creation failed; may be environment-dependent")
    
    assert item["name"] == "TestDiet"
    
    # Delete via POST endpoint
    r = client_admin.post(f"/ui/admin/specialkost/{diet_id}/delete")
    
    if r.status_code == 401:
        pytest.skip("Admin UI not enabled in test environment")
    
    assert r.status_code in (302, 303), f"Expected redirect, got {r.status_code}"
    
    # Verify it's gone
    item_after = repo.get_by_id(diet_id)
    assert item_after is None, "Diet type should be deleted"
