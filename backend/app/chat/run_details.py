import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.models import AgentModelCall
from app.agents.redaction import redact_data, redact_pii
from app.chat.models import AgentEvent, AgentRun, AgentStep, ToolCall
from app.chat.schemas import AgentRunDetails, AgentStepDetail, ToolCallDetail

SENSITIVE_KEYS = (
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "credential",
    "password",
    "secret",
    "token",
)
IDENTITY_KEYS = {"owner_id", "student_id", "subject_student_id", "user_id"}


def _json_value(raw: str | None, fallback: Any) -> Any:
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return fallback


def _redact_audit_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: (
                "[REDACTED]"
                if key.lower() in IDENTITY_KEYS
                or any(marker in key.lower() for marker in SENSITIVE_KEYS)
                else _redact_audit_data(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_audit_data(item) for item in value]
    return redact_data(value)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _duration_ms(started_at: datetime | None, completed_at: datetime | None) -> int | None:
    if started_at is None or completed_at is None:
        return None
    return max(0, round((completed_at.timestamp() - started_at.timestamp()) * 1000))


def _step_times(db: Session, run_id: str) -> dict[str, tuple[datetime | None, datetime | None]]:
    result: dict[str, tuple[datetime | None, datetime | None]] = {}
    events = db.scalars(
        select(AgentEvent)
        .where(
            AgentEvent.run_id == run_id,
            AgentEvent.event_type.in_(["step.started", "step.succeeded", "step.failed"]),
        )
        .order_by(AgentEvent.sequence)
    ).all()
    for event in events:
        payload = _json_value(event.payload_json, {})
        step_key = payload.get("step_id") if isinstance(payload, dict) else None
        if not isinstance(step_key, str):
            continue
        started_at, completed_at = result.get(step_key, (None, None))
        if event.event_type == "step.started" and started_at is None:
            started_at = event.created_at
        elif event.event_type in {"step.succeeded", "step.failed"}:
            completed_at = event.created_at
        result[step_key] = (started_at, completed_at)
    return result


def serialize_run_details(db: Session, run: AgentRun) -> AgentRunDetails:
    steps = list(
        db.scalars(
            select(AgentStep)
            .where(AgentStep.run_id == run.id)
            .order_by(AgentStep.sequence, AgentStep.id)
        ).all()
    )
    tools = list(
        db.scalars(
            select(ToolCall)
            .where(ToolCall.run_id == run.id)
            .order_by(ToolCall.created_at, ToolCall.id)
        ).all()
    )
    model_calls = list(
        db.scalars(
            select(AgentModelCall)
            .where(AgentModelCall.run_id == run.id)
            .order_by(AgentModelCall.created_at, AgentModelCall.id)
        ).all()
    )
    step_by_id = {step.id: step for step in steps}
    tool_ids_by_step: dict[str, list[str]] = {}
    for tool in tools:
        if tool.step_id:
            tool_ids_by_step.setdefault(tool.step_id, []).append(tool.id)
    times = _step_times(db, run.id)

    step_details: list[AgentStepDetail] = []
    for step in steps:
        output = _json_value(step.output_json, {})
        conclusion = output.get("summary") if isinstance(output, dict) else None
        started_at, completed_at = times.get(step.step_key, (None, None))
        step_details.append(
            AgentStepDetail(
                id=step.id,
                step_key=step.step_key,
                agent=step.agent_name,
                instruction=redact_pii(step.instruction),
                status=step.status,
                dependencies=_json_value(step.dependencies_json, []),
                conclusion=redact_pii(conclusion) if isinstance(conclusion, str) else None,
                error_code=step.error_code,
                error_message=redact_pii(step.error_message) if step.error_message else None,
                started_at=_as_utc(started_at),
                completed_at=_as_utc(completed_at),
                duration_ms=_duration_ms(started_at, completed_at),
                tool_call_ids=tool_ids_by_step.get(step.id, []),
            )
        )

    tool_details: list[ToolCallDetail] = []
    for tool in tools:
        step = step_by_id.get(tool.step_id or "")
        arguments = _json_value(tool.arguments_json, {})
        if not isinstance(arguments, dict):
            arguments = {}
        tool_details.append(
            ToolCallDetail(
                id=tool.id,
                step_key=step.step_key if step else None,
                name=tool.tool_name,
                version=tool.tool_version,
                risk=tool.risk,
                status=tool.status,
                arguments=_redact_audit_data(arguments),
                result=_redact_audit_data(_json_value(tool.result_json, None)),
                error_code=tool.error_code,
                error_message=redact_pii(tool.error_message) if tool.error_message else None,
                started_at=_as_utc(tool.started_at),
                completed_at=_as_utc(tool.completed_at),
                duration_ms=_duration_ms(tool.started_at, tool.completed_at),
            )
        )

    return AgentRunDetails(
        run_id=run.id,
        status=run.status,
        provider=run.provider,
        started_at=_as_utc(run.started_at),
        completed_at=_as_utc(run.completed_at),
        duration_ms=_duration_ms(run.started_at, run.completed_at),
        model_call_count=run.model_call_count or len(model_calls),
        input_tokens=run.input_tokens or 0,
        output_tokens=run.output_tokens or 0,
        total_tokens=run.total_tokens or 0,
        cost_micros=run.cost_micros or 0,
        steps=step_details,
        tools=tool_details,
    )
