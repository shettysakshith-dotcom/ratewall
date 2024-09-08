# ratewall

A pluggable token-bucket rate limiter for Python, a pure-Python core plus drop-in Starlette/ASGI middleware that answers `429 Too Many Requests` with an honest `Retry-After`.

## The problem

Rate limiting looks trivial until you write it. Two things bite:

1. **Storage coupling.** Most implementations hard-wire the counter to a dict, or to Redis, and you can't swap backends without a rewrite.
2. **Untestable time.** A limiter's whole behaviour is a function of *elapsed time*, so naive tests end up calling `time.sleep()` - slow, flaky, and non-deterministic.

`ratewall` fixes both. The refill arithmetic is a pure function of `(config, state, now)`, storage sits behind a `Protocol`, and the clock is injected, so tests drive time by hand and never sleep.

## Install / quickstart

From a fresh clone (requires [`uv`](https://docs.astral.sh/uv/) and Python 3.12):

```bash
uv sync
uv run pytest -q          # 29 tests, no sleeping
uv run ratewall           # run the built-in burst simulation
```

## The CLI: watch a bucket drain

`ratewall` ships a small simulator that fires a burst at a bucket on a deterministic clock:

```bash
uv run ratewall --capacity 5 --rate 1 --requests 8 --interval 0.2
```

```
t=  0.0s  req#1  ALLOW  remaining=4/5
t=  0.2s  req#2  ALLOW  remaining=3/5
t=  0.4s  req#3  ALLOW  remaining=2/5
t=  0.6s  req#4  ALLOW  remaining=1/5
t=  0.8s  req#5  ALLOW  remaining=0/5
t=  1.0s  req#6  ALLOW  remaining=0/5
t=  1.2s  req#7  BLOCK  remaining=0/5  retry_after=0.80s
t=  1.4s  req#8  BLOCK  remaining=0/5  retry_after=0.60s
```

The bucket starts full (5 tokens), drains one per request, and refills at 1 token/second. Requests 1-6 spend the initial burst plus the trickle of refill; 7 and 8 arrive before another token is ready and get blocked with the exact wait until one is.

## The library

```python
from ratewall import RateLimiter

limiter = RateLimiter(capacity=100, refill_rate=10)  # burst 100, sustain 10/s

decision = limiter.check("user:42")
if decision.allowed:
    ...  # serve the request
else:
    ...  # 429, tell them to wait decision.retry_after seconds
```

### ASGI middleware

```python
from starlette.applications import Starlette
from ratewall import RateLimiter, RateLimitMiddleware

app = Starlette(routes=[...])
limiter = RateLimiter(capacity=100, refill_rate=10)
app.add_middleware(RateLimitMiddleware, limiter=limiter)
```

Over-quota requests get `429` with `Retry-After` and `X-RateLimit-*` headers; allowed
requests are stamped with `X-RateLimit-Limit` / `X-RateLimit-Remaining`. Limit by
anything, the default keys on client IP, but pass a `key_func` to limit per API key,
per tenant, or per route:

```python
def key_by_api_key(request):
    return request.headers.get("x-api-key", "anon")

app.add_middleware(RateLimitMiddleware, limiter=limiter, key_func=key_by_api_key)
```

## Pluggable storage

State lives behind a `Storage` Protocol:

```python
class Storage(Protocol):
    def get(self, key: str) -> BucketState | None: ...
    def set(self, key: str, state: BucketState) -> None: ...
```

`InMemoryStorage` ships and is the default (great for a single process and for tests).
For a multi-instance deployment you'd back it with Redis, `RedisStorage` in
`storage.py` documents exactly that interface (including the get→consume→set atomicity
concern) **without taking a dependency on `redis`**. Copy the implementation from its
docstring, hand it a client, and you're multi-process.

## Testing philosophy

Everything is deterministic. `ManualClock` lets tests advance time explicitly:

```python
clock = ManualClock()
limiter = RateLimiter(capacity=1, refill_rate=1, clock=clock)
assert limiter.check("k").allowed
assert not limiter.check("k").allowed   # drained
clock.advance(1.0)                       # refill — no real sleep
assert limiter.check("k").allowed
```

The middleware tests do the same through Starlette's `TestClient`: assert a real
`429` with a real `Retry-After`, advance the clock, assert recovery, all in ~0.05s.

Run the suite:

```bash
uv run ruff check .
uv run mypy
uv run pytest -q
```

## What I'd build next

- **A real `RedisStorage`** with a Lua script so get→consume→set is atomic under concurrency.
- **Sliding-window and fixed-window policies** behind the same `Storage`/`Clock` seams, selectable per route.
- **`X-RateLimit-Reset`** header (epoch seconds until the bucket is full again).
- **A FastAPI dependency** wrapper so you can rate-limit individual endpoints rather than the whole app.

## Maintainer

Maintained by **Sakshith Shetty**, a Customer & Business Insights Analyst focused on Python, SQL, and data analytics.

[LinkedIn](https://www.linkedin.com/in/sakshith-shetty) · [Email](mailto:shetty.sakshith@gmail.com)