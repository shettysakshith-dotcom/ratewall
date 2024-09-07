"""Storage backends: in-memory behaviour and the documented Redis stub."""

from __future__ import annotations

import pytest

from ratewall.bucket import BucketState
from ratewall.storage import InMemoryStorage, RedisStorage, Storage


def test_in_memory_get_set_roundtrip() -> None:
    store = InMemoryStorage()
    assert store.get("missing") is None

    state = BucketState(tokens=3.0, last_refill=1.5)
    store.set("k", state)
    assert store.get("k") == state
    assert len(store) == 1


def test_in_memory_clear() -> None:
    store = InMemoryStorage()
    store.set("k", BucketState(tokens=1.0, last_refill=0.0))
    store.clear()
    assert len(store) == 0
    assert store.get("k") is None


def test_in_memory_satisfies_protocol() -> None:
    assert isinstance(InMemoryStorage(), Storage)


def test_redis_stub_refuses_to_instantiate() -> None:
    with pytest.raises(NotImplementedError, match="documented interface stub"):
        RedisStorage()
