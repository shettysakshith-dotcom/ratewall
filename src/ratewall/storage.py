"""Pluggable storage for per-key bucket state.

The :class:`Storage` Protocol is the extension point. An in-memory backend ships
here; a Redis backend is sketched as :class:`RedisStorage` to document the
interface without taking a hard dependency on ``redis``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ratewall.bucket import BucketState


@runtime_checkable
class Storage(Protocol):
    """Where bucket state lives between requests.

    Implementations must be safe to call once per request. ``get`` returns
    ``None`` for an unknown key; ``set`` overwrites.
    """

    def get(self, key: str) -> BucketState | None:
        """Load the state for ``key`` or ``None`` if never stored."""
        ...

    def set(self, key: str, state: BucketState) -> None:
        """Persist ``state`` for ``key``."""
        ...


class InMemoryStorage:
    """A plain dict-backed store. Perfect for a single process and for tests.

    Not shared across processes — for multi-instance deployments swap in a
    networked backend such as :class:`RedisStorage`.
    """

    def __init__(self) -> None:
        self._data: dict[str, BucketState] = {}

    def get(self, key: str) -> BucketState | None:
        return self._data.get(key)

    def set(self, key: str, state: BucketState) -> None:
        self._data[key] = state

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)


class RedisStorage:
    """Documented stub of a Redis-backed :class:`Storage`.

    This class intentionally does **not** import or require ``redis`` — it exists
    to show exactly what a networked backend would implement. Wire a real client
    in and fill the two methods:

    .. code-block:: python

        import json
        from redis import Redis
        from ratewall.bucket import BucketState

        class RedisStorage:
            def __init__(self, client: Redis, prefix: str = "ratewall:") -> None:
                self._c = client
                self._prefix = prefix

            def get(self, key):
                raw = self._c.get(self._prefix + key)
                if raw is None:
                    return None
                d = json.loads(raw)
                return BucketState(tokens=d["tokens"], last_refill=d["last_refill"])

            def set(self, key, state):
                self._c.set(
                    self._prefix + key,
                    json.dumps({"tokens": state.tokens, "last_refill": state.last_refill}),
                )

    A production version would also use a Lua script (or WATCH/MULTI) so the
    get→consume→set cycle is atomic under concurrency.
    """

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        raise NotImplementedError(
            "RedisStorage is a documented interface stub. Copy the implementation "
            "from the docstring and provide a redis client, or use InMemoryStorage."
        )

    def get(self, key: str) -> BucketState | None:  # pragma: no cover - stub
        raise NotImplementedError

    def set(self, key: str, state: BucketState) -> None:  # pragma: no cover - stub
        raise NotImplementedError
