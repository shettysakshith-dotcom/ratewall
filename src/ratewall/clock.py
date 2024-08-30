"""Time sources for the rate limiter.

The whole point of factoring this out is deterministic testing: production code
uses :class:`SystemClock`, tests use :class:`ManualClock` and never sleep.
"""

from __future__ import annotations

import time
from typing import Protocol


class Clock(Protocol):
    """A monotonic-ish source of wall-clock seconds."""

    def now(self) -> float:
        """Return the current time in seconds as a float."""
        ...


class SystemClock:
    """Real time, backed by :func:`time.monotonic`."""

    def now(self) -> float:
        return time.monotonic()


class ManualClock:
    """A clock you drive by hand. Test-only, but importable anywhere."""

    def __init__(self, start: float = 0.0) -> None:
        self._t = start

    def now(self) -> float:
        return self._t

    def advance(self, seconds: float) -> float:
        """Move time forward and return the new value."""
        if seconds < 0:
            raise ValueError("cannot move time backwards")
        self._t += seconds
        return self._t

    def set(self, seconds: float) -> None:
        self._t = seconds
