import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.models import AgentModelCall

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelCallUsage:
    operation: str
    provider: str
    model: str
    status: str
    started_at: datetime
    completed_at: datetime
    prompt_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_micros: int | None = None
    request_id: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @property
    def latency_ms(self) -> int:
        return max(0, round((self.completed_at - self.started_at).total_seconds() * 1000))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_usage(payload: Any) -> dict[str, int | None]:
    raw = payload.get("usage", {}) if isinstance(payload, dict) else {}
    if not isinstance(raw, dict):
        return {"input_tokens": None, "output_tokens": None, "total_tokens": None}

    def as_int(value: Any) -> int | None:
        return value if isinstance(value, int) and value >= 0 else None

    input_tokens = as_int(raw.get("prompt_tokens", raw.get("input_tokens")))
    output_tokens = as_int(raw.get("completion_tokens", raw.get("output_tokens")))
    total_tokens = as_int(raw.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def calculate_cost_micros(
    usage: dict[str, int | None],
    *,
    input_cost_per_million_usd: float | None,
    output_cost_per_million_usd: float | None,
) -> int | None:
    input_tokens = usage.get("input_tokens") or 0
    output_tokens = usage.get("output_tokens") or 0
    if input_cost_per_million_usd is None or output_cost_per_million_usd is None:
        return None
    return round(
        (input_tokens * input_cost_per_million_usd + output_tokens * output_cost_per_million_usd)
        / 1_000_000
        * 1_000_000
    )


def build_db_usage_recorder(
    db: Session,
    *,
    run_id: str | None = None,
    owner_id: str | None = None,
):
    def record(usage: ModelCallUsage) -> None:
        # Telemetry must be best effort, but database usage records should not be
        # skipped merely because a metrics exporter or tracer is unavailable.
        try:
            _record_database_usage(db, usage, run_id=run_id, owner_id=owner_id)
        except Exception:
            logger.warning("failed to persist model usage", exc_info=True)
        try:
            from app.observability.metrics import observe_model_usage

            observe_model_usage(usage)
        except Exception:
            logger.warning("failed to publish model usage metrics", exc_info=True)
        try:
            from app.observability.tracing import model_call_span

            with model_call_span(usage):
                pass
        except Exception:
            logger.warning("failed to publish model usage trace", exc_info=True)

    return record


def _record_database_usage(
    db: Session,
    usage: ModelCallUsage,
    *,
    run_id: str | None,
    owner_id: str | None,
) -> None:
    try:
        from app.agents.models import AgentModelCall
        from app.chat.models import AgentRun

        with db.begin_nested():
            db.add(
                AgentModelCall(
                    run_id=run_id,
                    owner_id=owner_id,
                    operation=usage.operation,
                    provider=usage.provider,
                    model=usage.model,
                    prompt_version=usage.prompt_version,
                    status=usage.status,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    total_tokens=usage.total_tokens,
                    cost_micros=usage.cost_micros,
                    latency_ms=usage.latency_ms,
                    request_id=usage.request_id,
                    error_code=usage.error_code,
                    error_message=usage.error_message,
                    started_at=usage.started_at,
                    completed_at=usage.completed_at,
                )
            )
            if run_id:
                run = db.get(AgentRun, run_id)
                if run is not None:
                    run.model_call_count = (run.model_call_count or 0) + 1
                    run.input_tokens = (run.input_tokens or 0) + (usage.input_tokens or 0)
                    run.output_tokens = (run.output_tokens or 0) + (usage.output_tokens or 0)
                    run.total_tokens = (run.total_tokens or 0) + (usage.total_tokens or 0)
                    run.cost_micros = (run.cost_micros or 0) + (usage.cost_micros or 0)
            db.flush()
    except Exception:
        return


def record_model_call(
    db: Session,
    *,
    owner_id: str | None,
    operation: str,
    provider: str,
    model: str,
    status: str,
    started_at: datetime,
    completed_at: datetime,
    error: BaseException | None = None,
    usage: dict[str, Any] | None = None,
) -> None:
    """Record legacy structured calls in the same telemetry table as chat runs."""

    payload = usage or {}
    input_tokens = _non_negative_int(payload.get("input_tokens"))
    output_tokens = _non_negative_int(payload.get("output_tokens"))
    total_tokens = _non_negative_int(payload.get("total_tokens"))
    if total_tokens is None and input_tokens is not None and output_tokens is not None:
        total_tokens = input_tokens + output_tokens
    try:
        with db.begin_nested():
            db.add(
                AgentModelCall(
                    owner_id=owner_id,
                    operation=operation[:80],
                    provider=provider[:80],
                    model=model[:120],
                    status=status[:30],
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    cost_micros=_non_negative_int(payload.get("cost_micros")),
                    latency_ms=max(0, round((completed_at - started_at).total_seconds() * 1000)),
                    request_id=str(payload.get("request_id"))[:160]
                    if payload.get("request_id")
                    else None,
                    error_code=type(error).__name__[:80] if error else None,
                    error_message=str(error)[:300] if error else None,
                    started_at=started_at,
                    completed_at=completed_at,
                )
            )
            db.flush()
    except Exception:
        logger.warning("failed to persist structured Agent model usage", exc_info=True)


def _non_negative_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None
