import os


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))


def test_weekview_spec_doc_exists_and_has_key_sections():
    path = os.path.join(ROOT, 'docs', 'weekview.md')
    assert os.path.exists(path), f"Missing spec doc: {path}"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    # Key markers
    assert 'ff.weekview.enabled' in content
    assert 'ETag' in content and 'If-Match' in content
    assert 'RBAC' in content
    assert 'i18n' in content


def test_weekview_openapi_draft_exists_and_has_endpoints():
    path = os.path.join(ROOT, 'openapi', 'parts', 'weekview.yml')
    assert os.path.exists(path), f"Missing OpenAPI draft: {path}"
    with open(path, 'r', encoding='utf-8') as f:
        y = f.read()
    # Minimal string presence checks to avoid YAML dependency
    assert '/api/weekview' in y
    assert 'get:' in y
    assert 'patch:' in y
    assert '/api/weekview/resolve' in y
    assert 'post:' in y


def test_weekview_ui_mock_exists_and_mentions_grid():
    path = os.path.join(ROOT, 'ui', 'prototypes', 'weekview_mock.html')
    assert os.path.exists(path), f"Missing UI mock: {path}"
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    assert 'weekview-grid' in html or 'Department × Day × Meal' in html
