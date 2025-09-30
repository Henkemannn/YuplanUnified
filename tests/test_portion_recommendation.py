import pytest

# Legacy POST-based portion recommendation tests have been superseded by
# test_service_recommendation.py (GET endpoint & new algorithm). This file is
# intentionally kept minimal to avoid re-introduction via tooling or cached
# references. It is skipped at collection time.
pytest.skip("Legacy portion recommendation tests removed; using test_service_recommendation instead", allow_module_level=True)
