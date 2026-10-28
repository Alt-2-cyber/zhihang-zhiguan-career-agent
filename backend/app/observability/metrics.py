import re
from time import perf_counter

from prometheus_client import Counter, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.agents.usage import ModelCallUsage

HTTP_REQUESTS = Counter(
    "career_http_requests_total",
    "HTTP requests handled by the career system",
    ("method", "path", "status"),
)
HTTP_DURATION = Histogram(
    "career_http_request_duration_seconds",
    "HTTP request duration in seconds",
    ("method", "path"),
)
MODEL_CALLS = Counter(
    "career_agent_model_calls_total",
    "Agent provider calls",
    ("provider", "operation", "status"),
)
MODEL_TOKENS = Counter(
    "career_agent_tokens_total",
    "Agent model tokens",
    ("provider", "direction"),
)
MODEL_COST = Counter(
    "career_agent_cost_micros_total",
    "Agent model cost in micro USD",
    ("provider",),
)

UUID_PATH = re.compile(r"/[0-9a-f]{8}-[0-9a-f-]{27,36}(?=/|$)", re.IGNORECASE)


def normalize_path(path: str) -> str:
    return UUID_PATH.sub("/{id}", path)


def observe_model_usage(usage: ModelCallUsage) -> None:
    MODEL_CALLS.labels(usage.provider, usage.operation, usage.status).inc()
    if usage.input_tokens:
        MODEL_TOKENS.labels(usage.provider, "input").inc(usage.input_tokens)
    if usage.output_tokens:
        MODEL_TOKENS.labels(usage.provider, "output").inc(usage.output_tokens)
    if usage.cost_micros:
        MODEL_COST.labels(usage.provider).inc(usage.cost_micros)


def render_metrics() -> bytes:
    return generate_latest()


class MetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started = perf_counter()
        path = normalize_path(request.url.path)
        try:
            response = await call_next(request)
        except Exception:
            HTTP_REQUESTS.labels(request.method, path, "500").inc()
            HTTP_DURATION.labels(request.method, path).observe(perf_counter() - started)
            raise
        HTTP_REQUESTS.labels(request.method, path, str(response.status_code)).inc()
        HTTP_DURATION.labels(request.method, path).observe(perf_counter() - started)
        return response
