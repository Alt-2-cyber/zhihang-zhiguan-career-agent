from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.models import AgentModelCall


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(round((len(ordered) - 1) * percentile))))
    return ordered[index]


def _bucket(rows: list[AgentModelCall]) -> dict[str, object]:
    total = len(rows)
    successes = sum(row.status == "succeeded" for row in rows)
    failures = total - successes
    latencies = [row.latency_ms for row in rows if row.latency_ms is not None]
    return {
        "calls": total,
        "successes": successes,
        "failures": failures,
        "failure_rate": round(failures / total, 4) if total else 0,
        "avg_latency_ms": round(sum(latencies) / len(latencies)) if latencies else None,
        "p95_latency_ms": _percentile(latencies, 0.95),
        "input_tokens": _sum_optional(rows, "input_tokens"),
        "output_tokens": _sum_optional(rows, "output_tokens"),
        "total_tokens": _sum_optional(rows, "total_tokens"),
        "cost_micros": _sum_optional(rows, "cost_micros"),
    }


def _sum_optional(rows: list[AgentModelCall], field: str) -> int | None:
    values = [getattr(row, field) for row in rows if getattr(row, field) is not None]
    return sum(values) if values else None


def summarize_model_usage(
    db: Session,
    *,
    days: int = 7,
    provider: str | None = None,
    operation: str | None = None,
    max_rows: int = 50_000,
    now: datetime | None = None,
) -> dict[str, object]:
    current = now or datetime.now(timezone.utc)
    bounded_days = max(1, min(days, 90))
    since = current - timedelta(days=bounded_days)
    statement = (
        select(AgentModelCall)
        .where(AgentModelCall.completed_at >= since, AgentModelCall.completed_at <= current)
        .order_by(AgentModelCall.completed_at.asc(), AgentModelCall.id.asc())
        .limit(max_rows)
    )
    if provider:
        statement = statement.where(AgentModelCall.provider == provider[:80])
    if operation:
        statement = statement.where(AgentModelCall.operation == operation[:80])

    rows = list(db.scalars(statement).all())
    providers: dict[str, list[AgentModelCall]] = defaultdict(list)
    operations: dict[str, list[AgentModelCall]] = defaultdict(list)
    daily: dict[str, list[AgentModelCall]] = defaultdict(list)
    for row in rows:
        providers[row.provider].append(row)
        operations[row.operation].append(row)
        completed = row.completed_at
        if completed.tzinfo is None:
            completed = completed.replace(tzinfo=timezone.utc)
        daily[completed.astimezone(timezone.utc).date().isoformat()].append(row)

    def named_buckets(groups: dict[str, list[AgentModelCall]]) -> list[dict[str, object]]:
        return [{"name": name, **_bucket(group)} for name, group in sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))]

    return {
        "window": {
            "days": bounded_days,
            "since": since.isoformat(),
            "until": current.isoformat(),
            "truncated": len(rows) >= max_rows,
        },
        "totals": {"name": "总计", **_bucket(rows)},
        "providers": named_buckets(providers),
        "operations": named_buckets(operations),
        "daily": [{"date": day, **_bucket(daily[day])} for day in sorted(daily)],
    }
