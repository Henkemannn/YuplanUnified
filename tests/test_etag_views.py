import pytest

# Basic ETag caching tests for /kommun/rapport (JSON) and /kommun/veckovy (HTML)
# These rely on placeholder implementations added in legacy_kommun_ui.

@pytest.mark.usefixtures("client")
class TestETagCaching:
    def test_rapport_etag_200_then_304(self, client):
        r1 = client.get("/kommun/rapport", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
        assert r1.status_code == 200
        etag = r1.headers.get("ETag")
        assert etag and etag.startswith('"') and etag.endswith('"')
        r2 = client.get("/kommun/rapport", headers={"X-User-Role":"admin","X-Tenant-Id":"1","If-None-Match": etag})
        assert r2.status_code == 304
        assert not r2.data  # empty body
        # ETag must echo
        assert r2.headers.get("ETag") == etag

    def test_veckovy_etag_200_then_304(self, client):
        r1 = client.get("/kommun/veckovy", headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
        assert r1.status_code == 200
        etag = r1.headers.get("ETag")
        assert etag
        r2 = client.get("/kommun/veckovy", headers={"X-User-Role":"admin","X-Tenant-Id":"1","If-None-Match": etag})
        assert r2.status_code == 304
        assert r2.headers.get("ETag") == etag
        assert not r2.data
