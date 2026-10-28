import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.chat.models import AgentEvent, AgentRun
from app.core.errors import AppError


def append_event(
    db: Session, run_id: str, event_type: str, payload: dict[str, object]
) -> AgentEvent:
    run = db.get(AgentRun, run_id, with_for_update=True)
    if run is None:
        raise AppError(404, "agent_run_not_found", "Agent 执行记录不存在")
    last_sequence = db.scalar(
        select(func.max(AgentEvent.sequence)).where(AgentEvent.run_id == run_id)
    )
    event = AgentEvent(
        run_id=run_id,
        sequence=int(last_sequence or 0) + 1,
        event_type=event_type,
        payload_json=json.dumps(payload, ensure_ascii=False, default=str),
    )
    db.add(event)
    db.flush()
    return event


def list_events(db: Session, run_id: str, *, after_sequence: int = 0) -> list[AgentEvent]:
    return list(
        db.scalars(
            select(AgentEvent)
            .where(AgentEvent.run_id == run_id, AgentEvent.sequence > after_sequence)
            .order_by(AgentEvent.sequence)
        ).all()
    )
