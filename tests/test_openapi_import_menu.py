import json
from flask import Flask
from core.app_factory import create_app

def _app():
    return create_app({'TESTING': True, 'FEATURE_FLAGS': {'openapi_ui': True}})

def test_openapi_has_import_menu():
    app: Flask = _app()
    with app.test_client() as client:
        resp = client.get('/openapi.json')
        assert resp.status_code == 200
        spec = json.loads(resp.data)
        paths = spec.get('paths', {})
        assert '/import/menu' in paths, 'missing /import/menu path'
        post = paths['/import/menu']['post']
        # dry_run query param
        params = post.get('parameters', [])
        names = {p['name'] for p in params}
        assert 'dry_run' in names
        # responses
        resps = post.get('responses', {})
        for code in ('200','400','415','429'):
            assert code in resps, f'missing response {code}'
        # schema meta supports dry_run
        ok_resp = resps['200']['content']['application/json']['schema']
        # Reference check
        assert ok_resp.get('$ref') == '#/components/schemas/ImportOkResponse'
        # components meta schema has dry_run property
        meta_props = spec['components']['schemas']['ImportOkResponse']['properties']['meta']['properties']
        assert 'dry_run' in meta_props
