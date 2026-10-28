import hashlib
import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from uuid import uuid4

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

REDIS_WINDOW_SCRIPT = """
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
local nonce = ARGV[4]
local cutoff = now - window
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', cutoff)
local count = redis.call('ZCARD', KEYS[1])
if count >= limit then
  local first = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  local retry = math.ceil(tonumber(first[2]) + window - now)
  redis.call('EXPIRE', KEYS[1], window + 1)
  redis.call('EXPIRE', KEYS[2], window + 1)
  if retry < 1 then retry = 1 end
  return {0, retry}
end
local sequence = redis.call('INCR', KEYS[2])
redis.call('ZADD', KEYS[1], now, nonce .. ':' .. sequence)
redis.call('EXPIRE', KEYS[1], window + 1)
redis.call('EXPIRE', KEYS[2], window + 1)
return {1, 0}
"""


class SlidingWindowLimiter:
    def __init__(self, *, limit: int, window_seconds: int) -> None:
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        current = now if now is not None else time.monotonic()
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= self.limit:
                retry_after = max(1, int(events[0] + self.window_seconds - current + 0.999))
                return False, retry_after
            events.append(current)
            if len(self._events) > 10_000:
                self._events = {
                    item: values
                    for item, values in self._events.items()
                    if values and values[-1] > cutoff
                }
            return True, 0


class RedisSlidingWindowLimiter:
    """Process-shared sliding window backed by an atomic Redis Lua script."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        redis_url: str,
        key_prefix: str = "career:rate-limit",
    ) -> None:
        try:
            import redis
        except ImportError as error:  # pragma: no cover - dependency is installed in runtime images
            raise RuntimeError("redis package is required for RATE_LIMIT_BACKEND=redis") from error
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)
        self.key_prefix = key_prefix.strip(":")
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)
        self._script = self.client.register_script(REDIS_WINDOW_SCRIPT)

    def check(self, key: str, *, now: float | None = None) -> tuple[bool, int]:
        current = now if now is not None else time.time()
        redis_key = f"{self.key_prefix}:{hashlib.sha256(key.encode('utf-8')).hexdigest()}"
        result = self._script(
            keys=[redis_key, f"{redis_key}:sequence"],
            args=[current, self.window_seconds, self.limit, uuid4().hex],
        )
        return bool(int(result[0])), int(result[1])


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        backend: str = "memory",
        limit: int,
        window_seconds: int,
        redis_url: str = "redis://localhost:6379/0",
    ) -> None:
        super().__init__(app)
        normalized_backend = backend.strip().lower()
        self.fallback_limiter = SlidingWindowLimiter(limit=limit, window_seconds=window_seconds)
        if normalized_backend == "redis":
            self.limiter = RedisSlidingWindowLimiter(
                limit=limit,
                window_seconds=window_seconds,
                redis_url=redis_url,
            )
        elif normalized_backend == "memory":
            self.limiter = self.fallback_limiter
        else:
            raise ValueError(f"unsupported rate limit backend: {backend}")
        self.backend = normalized_backend
        self.limit = max(1, limit)
        self.window_seconds = max(1, window_seconds)

    @staticmethod
    def _key(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for", "")
        client = forwarded.split(",", 1)[0].strip() or (request.client.host if request.client else "unknown")
        authorization = request.headers.get("authorization", "")
        identity = hashlib.sha256(authorization.encode("utf-8")).hexdigest()[:16]
        return f"{client}:{identity}:{request.url.path}"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in {"/api/health", "/metrics"} or request.url.path.startswith("/docs"):
            return await call_next(request)
        try:
            allowed, retry_after = self.limiter.check(self._key(request))
        except Exception:
            if self.backend != "redis":
                raise
            logger.exception("Redis rate limiter unavailable; using process-local fallback")
            allowed, retry_after = self.fallback_limiter.check(self._key(request))
        if not allowed:
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "rate_limit_exceeded",
                        "message": "请求过于频繁，请稍后重试",
                    }
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(self.limit),
                    "X-RateLimit-Remaining": "0",
                },
            )
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = "1"
        return response
