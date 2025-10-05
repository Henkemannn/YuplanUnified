
from core.rate_limiter_token_bucket_memory import MemoryTokenBucketRateLimiter


class FakeClock:
    def __init__(self, start: float = 0.0):
        self._t = start
    def time(self) -> float:  # mimic time.time
        return self._t
    def advance(self, sec: float) -> None:
        self._t += sec


def _rl(quota: int, per: int, burst: int | None = None):
    clock = FakeClock(0.0)
    rl = MemoryTokenBucketRateLimiter(now_func=clock.time)
    # We currently treat quota as both rate & capacity; simulate custom burst by calling internal buckets directly if needed later.
    return rl, clock


def test_tb_allows_within_burst_then_blocks():
    rl, clock = _rl(5, 60)
    key = "k1"
    # First 5 allowed
    for i in range(5):
        assert rl.allow(key, quota=5, per_seconds=60), f"should allow {i}"
    # 6th blocks (tokens empty)
    assert not rl.allow(key, quota=5, per_seconds=60)


def test_tb_refills_over_time():
    rl, clock = _rl(2, 10)
    key = "k2"
    assert rl.allow(key, 2, 10)
    assert rl.allow(key, 2, 10)
    assert not rl.allow(key, 2, 10)
    # advance half window (5s) -> + (quota/per_seconds)*dt = (2/10)*5 = 1 token => next should allow
    clock.advance(5)
    assert rl.allow(key, 2, 10)


def test_tb_burst_defaults_to_quota():
    rl, _clock = _rl(3, 30)
    key = "k3"
    assert all(rl.allow(key, 3, 30) for _ in range(3))
    assert not rl.allow(key, 3, 30)


def test_tb_retry_after_calculation_placeholder():
    # Current memory backend retry_after returns 1 when blocked; ensure non-negative.
    rl, _clock = _rl(2, 10)
    key = "rx"
    assert rl.allow(key, 2, 10)
    assert rl.allow(key, 2, 10)
    assert not rl.allow(key, 2, 10)
    ra = rl.retry_after(key, 10)
    assert isinstance(ra, int)
    assert ra >= 0
