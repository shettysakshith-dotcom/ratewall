"""Refill/consume arithmetic for TokenBucket. No sleeping — time is a float."""

from __future__ import annotations

import pytest

from ratewall.bucket import BucketState, TokenBucket


def test_new_bucket_starts_full() -> None:
    bucket = TokenBucket(capacity=5, refill_rate=1)
    d = bucket.consume(None, now=0.0)
    assert d.allowed
    assert d.limit == 5
    assert d.remaining == 4  # spent one of five


def test_drains_to_empty_then_blocks() -> None:
    bucket = TokenBucket(capacity=3, refill_rate=1)
    state: BucketState | None = None
    for expected_remaining in (2, 1, 0):
        d = bucket.consume(state, now=0.0)
        assert d.allowed
        assert d.remaining == expected_remaining
        state = d.state

    # Fourth request at the same instant: no tokens, must block.
    blocked = bucket.consume(state, now=0.0)
    assert not blocked.allowed
    assert blocked.remaining == 0


def test_retry_after_is_deficit_over_rate() -> None:
    # Empty bucket, rate 2 tokens/s. Need 1 token => 0.5s wait.
    bucket = TokenBucket(capacity=4, refill_rate=2)
    empty = BucketState(tokens=0.0, last_refill=10.0)
    d = bucket.consume(empty, now=10.0)
    assert not d.allowed
    assert d.retry_after == pytest.approx(0.5)


def test_refill_accrues_over_time() -> None:
    bucket = TokenBucket(capacity=10, refill_rate=1)
    empty = BucketState(tokens=0.0, last_refill=0.0)
    # After 3 seconds, 3 tokens are back; spending 1 leaves 2.
    d = bucket.consume(empty, now=3.0)
    assert d.allowed
    assert d.remaining == 2


def test_refill_never_exceeds_capacity() -> None:
    bucket = TokenBucket(capacity=5, refill_rate=100)
    empty = BucketState(tokens=0.0, last_refill=0.0)
    # A huge gap would over-fill, but capacity caps it. Spend 1 => 4 left.
    d = bucket.consume(empty, now=1000.0)
    assert d.remaining == 4
    assert d.state.tokens == pytest.approx(4.0)


def test_fractional_tokens_tracked_but_remaining_floored() -> None:
    bucket = TokenBucket(capacity=10, refill_rate=1)
    empty = BucketState(tokens=0.0, last_refill=0.0)
    # 2.5s => 2.5 tokens; spend 1 => 1.5 left, floored to 1 for reporting.
    d = bucket.consume(empty, now=2.5)
    assert d.allowed
    assert d.state.tokens == pytest.approx(1.5)
    assert d.remaining == 1


def test_cost_greater_than_one() -> None:
    bucket = TokenBucket(capacity=10, refill_rate=1)
    d = bucket.consume(None, now=0.0, cost=4)
    assert d.allowed
    assert d.remaining == 6


def test_backwards_time_does_not_add_tokens() -> None:
    bucket = TokenBucket(capacity=5, refill_rate=1)
    state = BucketState(tokens=2.0, last_refill=100.0)
    d = bucket.consume(state, now=50.0)  # clock went backwards
    assert d.allowed
    assert d.state.tokens == pytest.approx(1.0)  # 2 - 1, no phantom refill


@pytest.mark.parametrize(
    ("capacity", "rate"),
    [(0, 1), (-1, 1), (5, 0), (5, -2)],
)
def test_invalid_config_rejected(capacity: float, rate: float) -> None:
    with pytest.raises(ValueError):
        TokenBucket(capacity=capacity, refill_rate=rate)


def test_invalid_cost_rejected() -> None:
    bucket = TokenBucket(capacity=5, refill_rate=1)
    with pytest.raises(ValueError):
        bucket.consume(None, now=0.0, cost=0)
