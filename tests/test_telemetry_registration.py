import pytest

from core.telemetry import track_event


class DummyCounter:
    def __init__(self):
        self.calls = []
    def add(self, value, labels):  # pragma: no cover - simple capture
        self.calls.append((value, dict(labels)))

@pytest.fixture
def dummy_events(monkeypatch):
    import core.telemetry as telem
    dc = DummyCounter()
    monkeypatch.setattr(telem, "_EVENTS", dc)
    return dc

@pytest.mark.usefixtures("client")
class TestTelemetryRegistration:
    def test_note_create_emits_event(self, client, dummy_events):
        # create note
        r = client.post("/notes/", json={"content":"Hello"}, headers={"X-User-Role":"admin","X-Tenant-Id":"1"})
        assert r.status_code == 200
        # verify track_event path registered a registrering event
        assert any(call[1].get("action") == "registrering" for call in dummy_events.calls)

    def test_direct_track_event(self, dummy_events):
        track_event("registrering", avdelning="A1", maltid="lunch")
        assert dummy_events.calls[-1][1]["avdelning"] == "A1"
        assert dummy_events.calls[-1][1]["maltid"] == "lunch"
