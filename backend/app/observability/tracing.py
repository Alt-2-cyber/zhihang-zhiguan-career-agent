import logging
from collections.abc import Iterator
from contextlib import contextmanager

from app.agents.usage import ModelCallUsage

logger = logging.getLogger(__name__)

try:
    from opentelemetry import trace
except ImportError:  # pragma: no cover - dependency is installed in runtime images
    trace = None  # type: ignore[assignment]

_configured = False


def configure_tracing(*, enabled: bool, service_name: str, endpoint: str | None) -> None:
    global _configured
    if _configured or not enabled or trace is None:
        return
    if not endpoint:
        _configured = True
        return
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
        trace.set_tracer_provider(provider)
        _configured = True
    except Exception as error:  # tracing must never prevent the API from starting
        logger.warning("OpenTelemetry setup failed: %s", type(error).__name__)
        _configured = True


@contextmanager
def model_call_span(usage: ModelCallUsage) -> Iterator[None]:
    if trace is None:
        yield
        return
    tracer = trace.get_tracer("career-agent")
    with tracer.start_as_current_span("agent.model_call") as span:
        span.set_attribute("agent.provider", usage.provider)
        span.set_attribute("agent.operation", usage.operation)
        span.set_attribute("gen_ai.request.model", usage.model)
        span.set_attribute("gen_ai.response.status", usage.status)
        if usage.total_tokens is not None:
            span.set_attribute("gen_ai.usage.total_tokens", usage.total_tokens)
        yield
