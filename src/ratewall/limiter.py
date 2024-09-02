"""The user-facing rate limiter: bucket config + storage + clock."""

from __future__ import annotations

from ratewall.bucket import Decision, TokenBucket
from ratewall.clock import Clock, SystemClock
from ratewall.storage import InMemoryStorage, Storage


class RateLimiter:
    """Ties a :class:`TokenBucket` policy to a :class:`Storage` and a :class:`Clock`.

    Args:
        capacity: burst size — max tokens a key can hold.
        refill_rate: tokens replenished per second (the sustained rate).
        storage: where per-key state lives; defaults to in-memory.
        clock: time source; defaults to the system monotonic clock.
    """

    def __init__(
        self,
        capacity: float,
        refill_rate: float,
        storage: Storage | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.bucket = TokenBucket(capacity, refill_rate)
        self.storage: Storage = storage if storage is not None else InMemoryStorage()
        self.clock: Clock = clock if clock is not None else SystemClock()

    def check(self, key: str, cost: float = 1.0) -> Decision:
        """Consume ``cost`` tokens for ``key`` and persist the result."""
        now = self.clock.now()
        state = self.storage.get(key)
        decision = self.bucket.consume(state, now, cost=cost)
        self.storage.set(key, decision.state)
        return decision
