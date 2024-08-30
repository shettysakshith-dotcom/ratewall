"""Pure token-bucket math.

:class:`TokenBucket` holds only *configuration* (capacity + refill rate). The
mutable per-key state lives in :class:`BucketState`, which storage backends
persist. Keeping the two apart means the refill arithmetic is a pure function of
``(config, state, now)`` — trivial to test and safe to share across keys.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BucketState:
    """Per-key mutable state: how many tokens are left and when we last refilled."""

    tokens: float
    last_refill: float


@dataclass(frozen=True)
class Decision:
    """Outcome of a single ``consume`` attempt."""

    allowed: bool
    remaining: int
    limit: int
    retry_after: float
    state: BucketState


class TokenBucket:
    """A leaky/token bucket parameterised by capacity and refill rate.

    Args:
        capacity: maximum number of tokens the bucket can hold (burst size).
        refill_rate: tokens added per second.
    """

    def __init__(self, capacity: float, refill_rate: float) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0:
            raise ValueError("refill_rate must be positive")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)

    def initial_state(self, now: float) -> BucketState:
        """A fresh bucket starts full."""
        return BucketState(tokens=self.capacity, last_refill=now)

    def _refill(self, state: BucketState, now: float) -> float:
        """Return the token count after lazily refilling up to ``now``."""
        elapsed = now - state.last_refill
        if elapsed <= 0:
            return min(state.tokens, self.capacity)
        return min(self.capacity, state.tokens + elapsed * self.refill_rate)

    def consume(
        self, state: BucketState | None, now: float, cost: float = 1.0
    ) -> Decision:
        """Attempt to spend ``cost`` tokens.

        ``state`` may be ``None`` for a never-seen key, in which case a full
        bucket is assumed. The returned :class:`Decision` carries the new state
        the caller must persist.
        """
        if cost <= 0:
            raise ValueError("cost must be positive")
        if state is None:
            state = self.initial_state(now)

        tokens = self._refill(state, now)

        if tokens >= cost:
            new_state = BucketState(tokens=tokens - cost, last_refill=now)
            return Decision(
                allowed=True,
                remaining=int(new_state.tokens),
                limit=int(self.capacity),
                retry_after=0.0,
                state=new_state,
            )

        # Not enough tokens: reject, but still record the refill so time keeps
        # accruing. retry_after is how long until we have `cost` tokens.
        deficit = cost - tokens
        retry_after = deficit / self.refill_rate
        new_state = BucketState(tokens=tokens, last_refill=now)
        return Decision(
            allowed=False,
            remaining=int(tokens),
            limit=int(self.capacity),
            retry_after=retry_after,
            state=new_state,
        )
