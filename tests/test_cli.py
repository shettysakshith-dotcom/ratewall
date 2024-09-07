"""CLI simulation is deterministic thanks to ManualClock."""

from __future__ import annotations

from ratewall.cli import main, simulate


def test_simulate_allows_then_blocks() -> None:
    # capacity 3, rate 1/s, requests fired 0.1s apart => bursts, then blocks.
    lines = simulate(capacity=3, rate=1, requests=5, interval=0.1)
    assert len(lines) == 5
    assert lines[0].count("ALLOW") == 1
    assert "ALLOW" in lines[2]
    assert "BLOCK" in lines[3]
    assert "retry_after" in lines[3]


def test_simulate_recovers_with_wide_interval() -> None:
    # rate 1/s and a 1s interval never exhausts a capacity-1 bucket.
    lines = simulate(capacity=1, rate=1, requests=4, interval=1.0)
    assert all("ALLOW" in line for line in lines)


def test_main_returns_zero() -> None:
    rc = main(["--capacity", "2", "--rate", "1", "--requests", "3", "--interval", "0"])
    assert rc == 0
