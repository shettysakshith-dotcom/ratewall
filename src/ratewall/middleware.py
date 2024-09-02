"""Starlette / ASGI middleware that enforces a :class:`RateLimiter`."""

from __future__ import annotations

import math
from collections.abc import Callable

from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ratewall.limiter import RateLimiter

KeyFunc = Callable[[Request], str]


def client_ip_key(request: Request) -> str:
    """Default key function: limit per client IP."""
    if request.client is not None:
        return request.client.host
    return "anonymous"


class RateLimitMiddleware:
    """Reject over-quota requests with ``429`` and a ``Retry-After`` header.

    Args:
        app: the wrapped ASGI application.
        limiter: the :class:`RateLimiter` policy to enforce.
        key_func: maps a request to a bucket key (default: client IP).
        cost: tokens charged per request.
    """

    def __init__(
        self,
        app: ASGIApp,
        limiter: RateLimiter,
        key_func: KeyFunc = client_ip_key,
        cost: float = 1.0,
    ) -> None:
        self.app = app
        self.limiter = limiter
        self.key_func = key_func
        self.cost = cost

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        key = self.key_func(request)
        decision = self.limiter.check(key, cost=self.cost)

        if not decision.allowed:
            retry_after = max(1, math.ceil(decision.retry_after))
            response: Response = JSONResponse(
                {"detail": "Rate limit exceeded. Slow down."},
                status_code=429,
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(decision.limit),
                    "X-RateLimit-Remaining": str(decision.remaining),
                },
            )
            await response(scope, receive, send)
            return

        # Allowed: forward, and stamp quota headers onto the outgoing response.
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"x-ratelimit-limit", str(decision.limit).encode()))
                headers.append(
                    (b"x-ratelimit-remaining", str(decision.remaining).encode())
                )
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_with_headers)


__all__ = [
    "KeyFunc",
    "RateLimitMiddleware",
    "client_ip_key",
]
