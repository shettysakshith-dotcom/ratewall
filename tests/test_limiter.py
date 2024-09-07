"""RateLimiter wiring: storage persistence, per-key isolation, clock-driven refill."""

from __future__ import annotations

from ratewall.clock import ManualClock
from ratewall.limiter import RateLimiter
from ratewall.storage import InMemoryStorage


def test_persists_state_between_calls() -> None:
    clock = ManualClock()
    limiter = RateLimiter(capacity=2, refill_rate=1, clock=clock)
    assert limiter.check("a").allowed
    assert limiter.check("a").allowed
    assert not limiter.check("a").allowed  # bucket drained across calls


def test_keys_are_isolated() -> None:
    clock = ManualClock()
    limiter = RateLimiter(capacity=1, refill_rate=1, clock=clock)
    assert limiter.check("alice").allowed
    assert not limiter.check("alice").allowed
    # Bob is untouched by Alice's spending.
    assert limiter.check("bob").allowed


def test_recovers_after_time_passes() -> None:
    clock = ManualClock()
    limiter = RateLimiter(capacity=1, refill_rate=1, clock=clock)
    assert limiter.check("k").allowed
    assert not limiter.check("k").allowed
    clock.advance(1.0)  # one token refilled
    assert limiter.check("k").allowed


def test_uses_supplied_storage() -> None:
    store = InMemoryStorage()
    clock = ManualClock()
    limiter = RateLimiter(capacity=3, refill_rate=1, storage=store, clock=clock)
    limiter.check("x")
    assert len(store) == 1
    assert store.get("x") is not None
