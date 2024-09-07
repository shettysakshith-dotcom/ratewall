"""Middleware behaviour via Starlette's TestClient. Deterministic — no sleeping."""

from __future__ import annotations

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from ratewall.clock import ManualClock
from ratewall.limiter import RateLimiter
from ratewall.middleware import RateLimitMiddleware


def build_client(
    limiter: RateLimiter,
    key_func: object | None = None,
) -> TestClient:
    async def hello(request: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    app = Starlette(routes=[Route("/", hello)])
    kwargs = {"limiter": limiter}
    if key_func is not None:
        kwargs["key_func"] = key_func  # type: ignore[assignment]
    app.add_middleware(RateLimitMiddleware, **kwargs)  # type: ignore[arg-type]
    return TestClient(app)


def test_allows_within_capacity() -> None:
    clock = ManualClock()
    limiter = RateLimiter(capacity=3, refill_rate=1, clock=clock)
    client = build_client(limiter)

    for _ in range(3):
        resp = client.get("/")
        assert resp.status_code == 200
        assert resp.text == "ok"
    assert resp.headers["x-ratelimit-limit"] == "3"


def test_blocks_over_capacity_with_429_and_retry_after() -> None:
    clock = ManualClock()
    limiter = RateLimiter(capacity=2, refill_rate=1, clock=clock)
    client = build_client(limiter)

    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 200

    blocked = client.get("/")
    assert blocked.status_code == 429
    assert "Retry-After" in blocked.headers
    assert int(blocked.headers["Retry-After"]) >= 1
    assert blocked.json()["detail"].startswith("Rate limit exceeded")


def test_recovers_after_clock_advances() -> None:
    clock = ManualClock()
    limiter = RateLimiter(capacity=1, refill_rate=1, clock=clock)
    client = build_client(limiter)

    assert client.get("/").status_code == 200
    assert client.get("/").status_code == 429

    clock.advance(1.0)  # refill one token — no real sleep
    assert client.get("/").status_code == 200


def test_custom_key_func_separates_tenants() -> None:
    clock = ManualClock()
    limiter = RateLimiter(capacity=1, refill_rate=1, clock=clock)

    def key_by_header(request: Request) -> str:
        return request.headers.get("x-api-key", "anon")

    client = build_client(limiter, key_func=key_by_header)

    assert client.get("/", headers={"x-api-key": "tenant-a"}).status_code == 200
    assert client.get("/", headers={"x-api-key": "tenant-a"}).status_code == 429
    # Different tenant has its own bucket.
    assert client.get("/", headers={"x-api-key": "tenant-b"}).status_code == 200


def test_quota_headers_on_allowed_response() -> None:
    clock = ManualClock()
    limiter = RateLimiter(capacity=5, refill_rate=1, clock=clock)
    client = build_client(limiter)

    resp = client.get("/")
    assert resp.headers["x-ratelimit-limit"] == "5"
    assert resp.headers["x-ratelimit-remaining"] == "4"
