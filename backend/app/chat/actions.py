import json
from datetime import datetime, timedelta, timezone

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import User
from app.chat.models import ActionProposal, AgentStep, ChatSession, ToolCall
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.models import utc_now
from app.tools.contracts import ToolExecutionContext, ToolExecutionResult, ToolRisk
from app.tools.registry import ToolRegistry


class ActionOutcome(BaseModel):
    status: str
    tool_call_id: str
    proposal_id: str
    result: dict[str, object] | None = None


def requires_confirmation(mode: str, risk: ToolRisk) -> bool:
    return mode == "confirm" or risk == ToolRisk.high_risk


def _json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _audit(
    db: Session,
    *,
    user_id: str,
    action: str,
    proposal_id: str,
    details: dict[str, object],
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type="action_proposal",
            resource_id=proposal_id,
            details=_json(details),
        )
    )


def _outcome(proposal: ActionProposal, tool_call: ToolCall) -> ActionOutcome:
    return ActionOutcome(
        status=("pending_confirmation" if proposal.status == "pending" else proposal.status),
        tool_call_id=tool_call.id,
        proposal_id=proposal.id,
        result=json.loads(tool_call.result_json) if tool_call.result_json else None,
    )


def _persist_success(
    db: Session,
    *,
    proposal: ActionProposal,
    tool_call: ToolCall,
    result: ToolExecutionResult,
    actor_id: str,
    audit_action: str,
) -> None:
    now = utc_now()
    tool_call.status = "succeeded"
    tool_call.result_json = result.model_dump_json()
    tool_call.completed_at = now
    proposal.status = "succeeded"
    proposal.undo_json = _json(result.undo_data) if result.undo_data is not None else None
    proposal.executed_at = now
    proposal.decided_by = actor_id
    _audit(
        db,
        user_id=actor_id,
        action=audit_action,
        proposal_id=proposal.id,
        details={"tool": tool_call.tool_name, "risk": tool_call.risk},
    )


def propose_or_execute(
    db: Session,
    *,
    registry: ToolRegistry,
    chat_session: ChatSession,
    tool_name: str,
    arguments: dict[str, object],
    context: ToolExecutionContext,
    title: str,
) -> ActionOutcome:
    if chat_session.id != context.session_id or chat_session.owner_id != context.actor_id:
        raise AppError(403, "forbidden", "Agent 动作会话上下文无效")
    existing = db.scalar(
        select(ToolCall).where(ToolCall.idempotency_key == context.idempotency_key)
    )
    if existing is not None:
        proposal = db.scalar(
            select(ActionProposal).where(ActionProposal.tool_call_id == existing.id)
        )
        if proposal is None:
            raise AppError(409, "action_state_invalid", "Agent 动作状态不完整")
        return _outcome(proposal, existing)

    definition = registry.resolve(tool_name)
    tool_call = ToolCall(
        run_id=context.run_id,
        step_id=context.step_id,
        tool_name=definition.name,
        tool_version=definition.version,
        arguments_json=_json(arguments),
        risk=definition.risk.value,
        status="pending",
        idempotency_key=context.idempotency_key,
    )
    db.add(tool_call)
    db.flush()
    proposal = ActionProposal(
        session_id=chat_session.id,
        run_id=context.run_id,
        tool_call_id=tool_call.id,
        title=title,
        risk=definition.risk.value,
        arguments_json=tool_call.arguments_json,
        preview_json=_json({"tool": definition.name, "arguments": arguments}),
        status="pending",
        expires_at=utc_now() + timedelta(minutes=get_settings().action_proposal_expiry_minutes),
    )
    db.add(proposal)
    db.flush()

    if requires_confirmation(chat_session.mode, definition.risk):
        tool_call.status = "waiting_confirmation"
        _audit(
            db,
            user_id=context.actor_id,
            action="chat.action_proposed",
            proposal_id=proposal.id,
            details={"tool": definition.name, "risk": definition.risk.value},
        )
        db.commit()
        return _outcome(proposal, tool_call)

    tool_call.status = "running"
    tool_call.started_at = utc_now()
    try:
        with db.begin_nested():
            result = registry.execute(db, definition.name, arguments, context)
    except AppError as error:
        tool_call.status = "failed"
        tool_call.error_code = error.code
        tool_call.error_message = error.message
        tool_call.completed_at = utc_now()
        proposal.status = "failed"
        db.commit()
        raise
    _persist_success(
        db,
        proposal=proposal,
        tool_call=tool_call,
        result=result,
        actor_id=context.actor_id,
        audit_action="chat.action_auto_executed",
    )
    db.commit()
    return _outcome(proposal, tool_call)


def _owned_action(
    db: Session, *, user: User, proposal_id: str, for_update: bool = False
) -> tuple[ActionProposal, ToolCall, ChatSession]:
    statement = select(ActionProposal).where(ActionProposal.id == proposal_id)
    if for_update:
        statement = statement.with_for_update()
    proposal = db.scalar(statement)
    if proposal is None:
        raise AppError(404, "action_not_found", "Agent 动作不存在")
    chat_session = db.get(ChatSession, proposal.session_id)
    if chat_session is None or chat_session.owner_id != user.id:
        raise AppError(404, "action_not_found", "Agent 动作不存在")
    tool_call = db.get(ToolCall, proposal.tool_call_id)
    if tool_call is None:
        raise AppError(409, "action_state_invalid", "Agent 动作状态不完整")
    return proposal, tool_call, chat_session


def _execution_context(
    db: Session,
    *,
    user: User,
    chat_session: ChatSession,
    tool_call: ToolCall,
) -> ToolExecutionContext:
    step = db.get(AgentStep, tool_call.step_id) if tool_call.step_id else None
    return ToolExecutionContext(
        session_id=chat_session.id,
        run_id=tool_call.run_id,
        step_id=tool_call.step_id,
        specialist=step.agent_name if step else "career",
        actor_id=user.id,
        actor_role=user.role,
        subject_student_id=chat_session.subject_student_id,
        idempotency_key=tool_call.idempotency_key,
    )


def confirm_action(
    db: Session, *, registry: ToolRegistry, user: User, proposal_id: str
) -> ActionOutcome:
    proposal, tool_call, chat_session = _owned_action(
        db, user=user, proposal_id=proposal_id, for_update=True
    )
    if proposal.status == "succeeded":
        return _outcome(proposal, tool_call)
    if proposal.status != "pending":
        raise AppError(409, "action_not_pending", "Agent 动作当前不能确认")
    if _aware(proposal.expires_at) <= utc_now():
        proposal.status = "expired"
        tool_call.status = "cancelled"
        db.commit()
        raise AppError(410, "action_expired", "Agent 动作确认已过期")

    context = _execution_context(db, user=user, chat_session=chat_session, tool_call=tool_call)
    proposal.status = "executing"
    proposal.decided_at = utc_now()
    tool_call.status = "running"
    tool_call.started_at = utc_now()
    try:
        with db.begin_nested():
            result = registry.execute(
                db,
                tool_call.tool_name,
                json.loads(tool_call.arguments_json),
                context,
            )
    except AppError as error:
        proposal.status = "failed"
        proposal.decided_by = user.id
        tool_call.status = "failed"
        tool_call.error_code = error.code
        tool_call.error_message = error.message
        tool_call.completed_at = utc_now()
        db.commit()
        raise
    _persist_success(
        db,
        proposal=proposal,
        tool_call=tool_call,
        result=result,
        actor_id=user.id,
        audit_action="chat.action_confirmed",
    )
    db.commit()
    return _outcome(proposal, tool_call)


def reject_action(db: Session, *, user: User, proposal_id: str) -> ActionOutcome:
    proposal, tool_call, _chat_session = _owned_action(
        db, user=user, proposal_id=proposal_id, for_update=True
    )
    if proposal.status == "rejected":
        return _outcome(proposal, tool_call)
    if proposal.status != "pending":
        raise AppError(409, "action_not_pending", "Agent 动作当前不能拒绝")
    proposal.status = "rejected"
    proposal.decided_by = user.id
    proposal.decided_at = utc_now()
    tool_call.status = "cancelled"
    _audit(
        db,
        user_id=user.id,
        action="chat.action_rejected",
        proposal_id=proposal.id,
        details={"tool": tool_call.tool_name},
    )
    db.commit()
    return _outcome(proposal, tool_call)


def undo_action(
    db: Session, *, registry: ToolRegistry, user: User, proposal_id: str
) -> ActionOutcome:
    proposal, tool_call, chat_session = _owned_action(
        db, user=user, proposal_id=proposal_id, for_update=True
    )
    if proposal.status == "undone":
        return _outcome(proposal, tool_call)
    if proposal.status != "succeeded" or not proposal.undo_json:
        raise AppError(409, "action_not_reversible", "该操作不能自动撤销")
    context = _execution_context(db, user=user, chat_session=chat_session, tool_call=tool_call)
    with db.begin_nested():
        result = registry.undo(
            db,
            tool_call.tool_name,
            json.loads(proposal.undo_json),
            context,
        )
    tool_call.result_json = result.model_dump_json()
    proposal.status = "undone"
    _audit(
        db,
        user_id=user.id,
        action="chat.action_undone",
        proposal_id=proposal.id,
        details={"tool": tool_call.tool_name},
    )
    db.commit()
    return _outcome(proposal, tool_call)
