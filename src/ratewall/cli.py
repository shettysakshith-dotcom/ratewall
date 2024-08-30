"""A tiny CLI that simulates a burst of requests against a bucket.

Run ``ratewall --capacity 5 --rate 1 --requests 8`` to watch the bucket drain
and refuse. Uses a :class:`ManualClock` so output is fully deterministic.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from ratewall.clock import ManualClock
from ratewall.limiter import RateLimiter


def simulate(
    capacity: float,
    rate: float,
    requests: int,
    interval: float,
) -> list[str]:
    """Fire ``requests`` calls ``interval`` seconds apart; return one line each."""
    clock = ManualClock(start=0.0)
    limiter = RateLimiter(capacity=capacity, refill_rate=rate, clock=clock)
    lines: list[str] = []
    for i in range(requests):
        decision = limiter.check("demo")
        verdict = "ALLOW" if decision.allowed else "BLOCK"
        extra = "" if decision.allowed else f"  retry_after={decision.retry_after:.2f}s"
        lines.append(
            f"t={clock.now():5.1f}s  req#{i + 1:<2} {verdict}  "
            f"remaining={decision.remaining}/{decision.limit}{extra}"
        )
        clock.advance(interval)
    return lines


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ratewall",
        description="Simulate a token-bucket rate limiter over a burst of requests.",
    )
    parser.add_argument("--capacity", type=float, default=5.0, help="burst size")
    parser.add_argument("--rate", type=float, default=1.0, help="tokens per second")
    parser.add_argument("--requests", type=int, default=8, help="how many requests")
    parser.add_argument(
        "--interval",
        type=float,
        default=0.2,
        help="seconds between requests",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    for line in simulate(args.capacity, args.rate, args.requests, args.interval):
        print(line)
    return 0
