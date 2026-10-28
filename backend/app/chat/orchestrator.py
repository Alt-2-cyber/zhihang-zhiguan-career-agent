import json
from time import monotonic

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.conversation_contracts import (
    AgentLimits,
    Citation,
    ComposeAnswerRequest,
    ConversationMessage,
    MemorySummary,
    MemorySummaryRequest,
    PlanTurnRequest,
    SpecialistOutput,
    SpecialistRequest,
    SpecialistSummaryRequest,
    SuggestedAction,
    ToolCatalogItem,
    ToolRequest,
)
from app.agents.conversation_gateway import ConversationGateway
from app.auth.models import User
from app.chat.actions import propose_or_execute
from app.chat.events import append_event
from app.chat.models import AgentRun, AgentStep, ChatMessage, ChatSession, ToolCall
from app.core.config import Settings
from app.core.errors import AppError
from app.core.models import utc_now
from app.tools.contracts import ToolExecutionContext, ToolRisk
from app.tools.registry import ToolRegistry

SPECIALISTS = (
    "career",
    "job",
    "resume",
    "application",
    "interview",
    "counselor",
    "learning",
    "workplace",
    "intelligence",
    "employment",
)


def _conversation_messages(
    db: Session, session_id: str, *, limit: int
) -> list[ConversationMessage]:
    messages = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(limit)
    ).all()
    return [
        ConversationMessage(
            role=(message.sender if message.sender in {"user", "assistant", "tool"} else "tool"),
            content=message.content,
            message_id=message.id,
        )
        for message in reversed(messages)
    ]


def _tool_catalog(registry: ToolRegistry, *, specialist: str, role: str) -> list[ToolCatalogItem]:
    return [
        ToolCatalogItem(
            name=item["name"],
            description=item["description"],
            input_schema=item["input_schema"],
            version=str(item.get("version", "1")),
            risk=str(item.get("risk", "read")),
        )
        for item in registry.catalog(specialist=specialist, role=role)
    ]


def _main_catalog(registry: ToolRegistry, role: str) -> list[ToolCatalogItem]:
    items: dict[str, ToolCatalogItem] = {}
    for specialist in SPECIALISTS:
        for item in _tool_catalog(registry, specialist=specialist, role=role):
            items[item.name] = item
    return list(items.values())[:40]


def _context(chat_session: ChatSession, user_message: ChatMessage) -> dict[str, object]:
    return {
        "session_id": chat_session.id,
        "role": chat_session.role,
        "subject_student_id": chat_session.subject_student_id,
        "context_refs": json.loads(user_message.citations_json),
    }


def _existing_result(db: Session, idempotency_key: str) -> dict[str, object] | None:
    tool_call = db.scalar(select(ToolCall).where(ToolCall.idempotency_key == idempotency_key))
    if tool_call is None or tool_call.status != "succeeded" or not tool_call.result_json:
        return None
    return json.loads(tool_call.result_json)


def _reject_invalid_arguments(
    db: Session,
    *,
    run: AgentRun,
    step: AgentStep,
    tool_name: str,
    arguments: dict[str, object],
    registry: ToolRegistry,
) -> bool:
    """Reject malformed model proposals without failing the specialist step."""
    definition = registry.resolve(tool_name)
    try:
        definition.input_model.model_validate(arguments)
    except ValidationError:
        append_event(
            db,
            run.id,
            "tool.rejected",
            {
                "step_id": step.step_key,
                "tool": tool_name,
                "reason": "invalid_arguments",
                "error_code": "tool_arguments_invalid",
            },
        )
        return True
    return False


def _execute_read_tool(
    db: Session,
    *,
    registry: ToolRegistry,
    run: AgentRun,
    step: AgentStep,
    tool_name: str,
    arguments: dict[str, object],
    context: ToolExecutionContext,
) -> dict[str, object]:
    existing = _existing_result(db, context.idempotency_key)
    if existing is not None:
        return existing
    definition = registry.resolve(tool_name)
    tool_call = ToolCall(
        run_id=run.id,
        step_id=step.id,
        tool_name=definition.name,
        tool_version=definition.version,
        arguments_json=json.dumps(arguments, ensure_ascii=False),
        risk=definition.risk.value,
        status="running",
        idempotency_key=context.idempotency_key,
        started_at=utc_now(),
    )
    db.add(tool_call)
    db.flush()
    append_event(
        db,
        run.id,
        "tool.started",
        {"step_id": step.step_key, "tool_call_id": tool_call.id, "tool": tool_name},
    )
    try:
        result = registry.execute(db, tool_name, arguments, context)
    except AppError as error:
        tool_call.status = "failed"
        tool_call.error_code = error.code
        tool_call.error_message = error.message
        tool_call.completed_at = utc_now()
        append_event(
            db,
            run.id,
            "tool.failed",
            {"tool_call_id": tool_call.id, "tool": tool_name, "error_code": error.code},
        )
        raise
    tool_call.status = "succeeded"
    tool_call.result_json = result.model_dump_json()
    tool_call.completed_at = utc_now()
    append_event(
        db,
        run.id,
        "tool.succeeded",
        {"tool_call_id": tool_call.id, "tool": tool_name},
    )
    return result.model_dump(mode="json")


def _execute_step(
    db: Session,
    *,
    run: AgentRun,
    chat_session: ChatSession,
    user: User,
    step: AgentStep,
    messages: list[ConversationMessage],
    context_data: dict[str, object],
    dependency_outputs: list[SpecialistOutput],
    gateway: ConversationGateway,
    registry: ToolRegistry,
    settings: Settings,
    started_at: float,
) -> SpecialistOutput:
    step.status = "running"
    append_event(
        db,
        run.id,
        "step.started",
        {"step_id": step.step_key, "agent": step.agent_name},
    )
    step_plan = json.loads(step.input_json)
    specialist_context = {
        **context_data,
        "knowledge_ready": settings.agent_provider != "local",
    }
    specialist_request = SpecialistRequest(
        step=step_plan,
        messages=messages,
        context=specialist_context,
        dependency_outputs=dependency_outputs,
        tool_catalog=_tool_catalog(registry, specialist=step.agent_name, role=chat_session.role),
    )
    decision = gateway.decide_specialist(specialist_request)
    catalog_names = {item.name for item in specialist_request.tool_catalog}
    approved_requests: list[ToolRequest] = []
    for request in decision.tool_requests:
        if request.name not in catalog_names:
            append_event(
                db,
                run.id,
                "tool.rejected",
                {
                    "step_id": step.step_key,
                    "tool": request.name,
                    "reason": "tool_not_in_authorized_catalog",
                },
            )
            continue
        approved_requests.append(request)
    decision = decision.model_copy(update={"tool_requests": approved_requests})
    append_event(
        db,
        run.id,
        "tool.plan",
        {
            "step_id": step.step_key,
            "agent": step.agent_name,
            "analysis": decision.analysis,
            "candidates": [item.model_dump(mode="json") for item in approved_requests],
        },
    )
    tool_results: list[dict[str, object]] = []
    seen_calls: set[tuple[str, str]] = set()
    for index, request in enumerate(decision.tool_requests):
        request_key = (
            request.name,
            json.dumps(request.arguments, ensure_ascii=False, sort_keys=True, default=str),
        )
        if request_key in seen_calls:
            continue
        seen_calls.add(request_key)
        if run.tool_call_count >= settings.agent_max_tool_calls:
            raise AppError(409, "agent_tool_budget_exceeded", "Agent 工具调用次数已达上限")
        if monotonic() - started_at >= settings.agent_run_timeout_seconds:
            raise AppError(408, "agent_budget_exceeded", "Agent 本轮执行已超时")
        definition = registry.resolve(request.name)
        if _reject_invalid_arguments(
            db,
            run=run,
            step=step,
            tool_name=request.name,
            arguments=request.arguments,
            registry=registry,
        ):
            continue
        execution_context = ToolExecutionContext(
            session_id=chat_session.id,
            run_id=run.id,
            step_id=step.id,
            specialist=step.agent_name,
            actor_id=user.id,
            actor_role=user.role,
            subject_student_id=chat_session.subject_student_id,
            idempotency_key=f"{run.id}:{step.step_key}:{index}",
        )
        if definition.risk == ToolRisk.read:
            result = _execute_read_tool(
                db,
                registry=registry,
                run=run,
                step=step,
                tool_name=request.name,
                arguments=request.arguments,
                context=execution_context,
            )
        else:
            outcome = propose_or_execute(
                db,
                registry=registry,
                chat_session=chat_session,
                tool_name=request.name,
                arguments=request.arguments,
                context=execution_context,
                title=f"{step.agent_name} Agent 建议操作",
            )
            result = outcome.model_dump(mode="json")
            append_event(
                db,
                run.id,
                (
                    "tool.awaiting_confirmation"
                    if outcome.status == "pending_confirmation"
                    else "tool.succeeded"
                ),
                {
                    "tool_call_id": outcome.tool_call_id,
                    "proposal_id": outcome.proposal_id,
                    "tool": request.name,
                    "status": outcome.status,
                },
            )
        run.tool_call_count += 1
        tool_results.append(result)
    if tool_results and settings.agent_max_tool_rounds > 1:
        followup_request = specialist_request.model_copy(update={"tool_results": tool_results})
        followup = gateway.decide_specialist(followup_request)
        followup_requests = [
            request for request in followup.tool_requests if request.name in catalog_names
        ]
        append_event(
            db,
            run.id,
            "tool.followup_plan",
            {
                "step_id": step.step_key,
                "candidates": [item.model_dump(mode="json") for item in followup_requests],
            },
        )
        for index, request in enumerate(followup_requests, start=1):
            request_key = (
                request.name,
                json.dumps(request.arguments, ensure_ascii=False, sort_keys=True, default=str),
            )
            if request_key in seen_calls:
                continue
            seen_calls.add(request_key)
            if run.tool_call_count >= settings.agent_max_tool_calls:
                raise AppError(409, "agent_tool_budget_exceeded", "tool call budget exceeded")
            if monotonic() - started_at >= settings.agent_run_timeout_seconds:
                raise AppError(408, "agent_budget_exceeded", "agent run timeout")
            definition = registry.resolve(request.name)
            if _reject_invalid_arguments(
                db,
                run=run,
                step=step,
                tool_name=request.name,
                arguments=request.arguments,
                registry=registry,
            ):
                continue
            execution_context = ToolExecutionContext(
                session_id=chat_session.id,
                run_id=run.id,
                step_id=step.id,
                specialist=step.agent_name,
                actor_id=user.id,
                actor_role=user.role,
                subject_student_id=chat_session.subject_student_id,
                idempotency_key=f"{run.id}:{step.step_key}:followup:{index}",
            )
            if definition.risk == ToolRisk.read:
                result = _execute_read_tool(
                    db,
                    registry=registry,
                    run=run,
                    step=step,
                    tool_name=request.name,
                    arguments=request.arguments,
                    context=execution_context,
                )
            else:
                outcome = propose_or_execute(
                    db,
                    registry=registry,
                    chat_session=chat_session,
                    tool_name=request.name,
                    arguments=request.arguments,
                    context=execution_context,
                    title=f"{step.agent_name} Agent 寤鸿鎿嶄綔",
                )
                result = outcome.model_dump(mode="json")
                append_event(
                    db,
                    run.id,
                    (
                        "tool.awaiting_confirmation"
                        if outcome.status == "pending_confirmation"
                        else "tool.succeeded"
                    ),
                    {
                        "tool_call_id": outcome.tool_call_id,
                        "proposal_id": outcome.proposal_id,
                        "tool": request.name,
                        "status": outcome.status,
                    },
                )
            run.tool_call_count += 1
            tool_results.append(result)
    summary_request = SpecialistSummaryRequest(
        step=step_plan,
        decision=decision,
        dependency_outputs=dependency_outputs,
        tool_results=tool_results,
    )
    output = _sanitize_specialist_output(gateway.summarize_specialist(summary_request))
    verified_citations: dict[tuple[str | None, str | None, str], Citation] = {}
    for result in tool_results:
        raw_citations = result.get("citations", [])
        if not isinstance(raw_citations, list):
            continue
        for raw in raw_citations:
            try:
                citation = Citation.model_validate(raw)
            except ValueError:
                continue
            key = (citation.source_id, citation.url, citation.label)
            verified_citations[key] = citation
    citations = [
        citation
        for citation in output.citations
        if (citation.source_id, citation.url, citation.label) in verified_citations
    ]
    known = {(item.source_id, item.url, item.label) for item in citations}
    citations.extend(item for key, item in verified_citations.items() if key not in known)
    output = output.model_copy(update={"citations": citations[:20]})
    step.output_json = output.model_dump_json()
    step.status = "succeeded"
    append_event(
        db,
        run.id,
        "step.succeeded",
        {"step_id": step.step_key, "agent": step.agent_name},
    )
    db.commit()
    return output


def _update_memory(
    db: Session,
    *,
    chat_session: ChatSession,
    gateway: ConversationGateway,
    settings: Settings,
) -> None:
    message_count = len(
        db.scalars(select(ChatMessage.id).where(ChatMessage.session_id == chat_session.id)).all()
    )
    if message_count <= settings.chat_summary_message_threshold:
        return
    older = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_session.id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .offset(settings.chat_recent_message_limit)
        .limit(40)
    ).all()
    if not older:
        return
    previous = None
    if chat_session.summary:
        previous = MemorySummary.model_validate_json(chat_session.summary)
    summary = gateway.summarize_memory(
        MemorySummaryRequest(
            previous_summary=previous,
            messages=[
                ConversationMessage(
                    role=item.sender,
                    content=item.content,
                    message_id=item.id,
                )
                for item in reversed(older)
                if item.sender in {"user", "assistant", "tool"}
            ],
        )
    )
    chat_session.summary = summary.model_dump_json()
    chat_session.summary_source_ids_json = json.dumps(summary.source_message_ids)


def _record_run_failure(db: Session, run: AgentRun, error: Exception) -> None:
    error_code = error.code if isinstance(error, AppError) else type(error).__name__
    run.status = "failed"
    run.error_code = error_code[:80]
    run.error_message = str(error)[:300] if isinstance(error, AppError) else type(error).__name__
    run.completed_at = utc_now()
    append_event(
        db,
        run.id,
        "run.failed",
        {"error_code": run.error_code, "message": run.error_message},
    )
    db.commit()


FALSE_DEGRADATION_REPLACEMENTS = (
    ("当前在线模型不可用，已使用受限本地规则读取必要业务数据。", "我已根据系统中的业务数据完成核对。"),
    ("当前在线模型不可用，使用受限本地规则读取必要业务数据。", "我已根据系统中的业务数据完成核对。"),
    ("根据在线模型不可用，使用受限本地规则读取必要业务数据，", "根据系统业务数据，"),
    ("根据在线模型不可用，使用受限本地规则读取必要业务数据", "根据系统业务数据"),
    ("根据受限本地规则读取的业务数据，", "根据系统业务数据，"),
    ("根据受限本地规则读取必要业务数据，", "根据系统业务数据，"),
    ("在线模型不可用，", ""),
    ("已使用受限本地规则", "已根据系统业务数据"),
    ("使用受限本地规则", "根据系统业务数据"),
    ("受限本地规则", "系统业务数据"),
    ("本地规则", "系统规则"),
)


def _strip_false_degradation_claims(value: str) -> str:
    cleaned = value
    for needle, replacement in FALSE_DEGRADATION_REPLACEMENTS:
        cleaned = cleaned.replace(needle, replacement)
    return cleaned


def _sanitize_specialist_output(output: SpecialistOutput) -> SpecialistOutput:
    return output.model_copy(
        update={
            "summary": _strip_false_degradation_claims(output.summary),
            "suggested_actions": [
                action.model_copy(
                    update={
                        "title": _strip_false_degradation_claims(action.title),
                        "rationale": _strip_false_degradation_claims(action.rationale),
                    }
                )
                for action in output.suggested_actions
            ],
        }
    )


def _sanitize_online_answer(answer):
    if str(answer.provider).startswith("local-rules"):
        return answer
    return answer.model_copy(update={"content": _strip_false_degradation_claims(answer.content)})


def run_agent_turn(
    db: Session,
    *,
    run_id: str,
    gateway: ConversationGateway,
    registry: ToolRegistry,
    settings: Settings,
) -> dict[str, object]:
    run = db.get(AgentRun, run_id)
    if run is None:
        raise AppError(404, "agent_run_not_found", "Agent 执行记录不存在")
    if run.status == "completed" and run.assistant_message_id:
        return {
            "run_id": run.id,
            "status": "completed",
            "assistant_message_id": run.assistant_message_id,
        }
    chat_session = db.get(ChatSession, run.session_id)
    user_message = db.get(ChatMessage, run.user_message_id)
    user = db.get(User, chat_session.owner_id if chat_session else "")
    if chat_session is None or user_message is None or user is None:
        raise AppError(409, "agent_run_context_invalid", "Agent 执行上下文不完整")
    if user.role.value != chat_session.role:
        raise AppError(403, "forbidden", "Agent 执行身份与会话不一致")

    started_at = monotonic()
    run.status = "running"
    run.started_at = run.started_at or utc_now()
    run.completed_at = None
    run.error_code = None
    run.error_message = None
    append_event(db, run.id, "run.started", {"provider": gateway.provider})
    messages = _conversation_messages(db, chat_session.id, limit=settings.chat_recent_message_limit)
    context_data = _context(chat_session, user_message)
    try:
        plan = gateway.plan_turn(
            PlanTurnRequest(
                messages=messages,
                context=context_data,
                tool_catalog=_main_catalog(registry, chat_session.role),
                limits=AgentLimits(
                    max_steps=settings.agent_max_steps,
                    max_tool_calls=settings.agent_max_tool_calls,
                ),
            )
        )
    except Exception as error:
        _record_run_failure(db, run, error)
        raise
    if len(plan.steps) > settings.agent_max_steps:
        raise AppError(409, "agent_step_budget_exceeded", "Agent 专业步骤数已达上限")
    run.plan_json = plan.model_dump_json()
    append_event(db, run.id, "plan.created", plan.model_dump(mode="json"))

    existing_steps = {
        item.step_key: item
        for item in db.scalars(select(AgentStep).where(AgentStep.run_id == run.id)).all()
    }
    for sequence, planned in enumerate(plan.steps, start=1):
        if planned.id not in existing_steps:
            step = AgentStep(
                run_id=run.id,
                step_key=planned.id,
                agent_name=planned.agent,
                instruction=planned.instruction,
                dependencies_json=json.dumps(planned.depends_on),
                input_json=planned.model_dump_json(),
                status="pending",
                sequence=sequence,
            )
            db.add(step)
            db.flush()
            existing_steps[planned.id] = step
    db.commit()

    outputs: dict[str, SpecialistOutput] = {}
    for planned in plan.steps:
        step = existing_steps[planned.id]
        if step.status == "succeeded" and step.output_json:
            outputs[planned.id] = SpecialistOutput.model_validate_json(step.output_json)
            continue
        dependencies = [outputs[item] for item in planned.depends_on if item in outputs]
        try:
            outputs[planned.id] = _execute_step(
                db,
                run=run,
                chat_session=chat_session,
                user=user,
                step=step,
                messages=messages,
                context_data=context_data,
                dependency_outputs=dependencies,
                gateway=gateway,
                registry=registry,
                settings=settings,
                started_at=started_at,
            )
        except AppError as error:
            step.status = "failed"
            step.error_code = error.code
            step.error_message = error.message
            append_event(
                db,
                run.id,
                "step.failed",
                {"step_id": step.step_key, "error_code": error.code},
            )
            db.commit()

    successful_outputs = [outputs[step.id] for step in plan.steps if step.id in outputs]
    if not successful_outputs:
        successful_outputs = [
            SpecialistOutput(
                agent=plan.steps[0].agent,
                summary="本轮专业工具均未成功，请根据失败步骤重试。",
            )
        ]
    suggested_actions: list[SuggestedAction] = [
        action for output in successful_outputs for action in output.suggested_actions
    ][:10]
    streamed_answer = False
    pending_answer_parts: list[str] = []
    pending_answer_chars = 0
    last_answer_flush = monotonic()

    def flush_answer_delta() -> None:
        nonlocal pending_answer_chars, last_answer_flush, streamed_answer
        if not pending_answer_parts:
            return
        append_event(
            db,
            run.id,
            "answer.delta",
            {"content": "".join(pending_answer_parts)},
        )
        db.commit()
        pending_answer_parts.clear()
        pending_answer_chars = 0
        last_answer_flush = monotonic()
        streamed_answer = True

    def emit_answer_delta(content: str) -> None:
        nonlocal pending_answer_chars
        if not content:
            return
        pending_answer_parts.append(content)
        pending_answer_chars += len(content)
        # Keep the UI responsive while avoiding one database transaction per
        # provider token. The final flush below preserves every character.
        if pending_answer_chars >= 120 or monotonic() - last_answer_flush >= 0.2:
            flush_answer_delta()

    def reset_answer_stream() -> None:
        nonlocal pending_answer_chars, last_answer_flush, streamed_answer
        pending_answer_parts.clear()
        pending_answer_chars = 0
        last_answer_flush = monotonic()
        append_event(db, run.id, "answer.reset", {})
        db.commit()
        streamed_answer = False

    try:
        compose_request = ComposeAnswerRequest(
            messages=messages,
            specialist_outputs=successful_outputs,
            pending_actions=suggested_actions,
        )
        stream_method = getattr(gateway, "compose_answer_stream", None)
        if callable(stream_method):
            answer = _sanitize_online_answer(
                stream_method(
                    compose_request,
                    on_delta=emit_answer_delta,
                    on_reset=reset_answer_stream,
                )
            )
            flush_answer_delta()
        else:
            answer = _sanitize_online_answer(gateway.compose_answer(compose_request))
    except Exception as error:
        _record_run_failure(db, run, error)
        raise
    assistant = ChatMessage(
        session_id=chat_session.id,
        sender="assistant",
        content=answer.content,
        attachment_ids_json="[]",
        citations_json=json.dumps(
            [item.model_dump(mode="json") for item in answer.citations],
            ensure_ascii=False,
        ),
        provider=answer.provider,
    )
    db.add(assistant)
    db.flush()
    if streamed_answer:
        append_event(db, run.id, "answer.replace", {"content": answer.content})
    else:
        for offset in range(0, len(answer.content), 120):
            append_event(
                db,
                run.id,
                "answer.delta",
                {"content": answer.content[offset : offset + 120]},
            )
    append_event(
        db,
        run.id,
        "answer.completed",
        {"message_id": assistant.id, "provider": answer.provider},
    )
    run.assistant_message_id = assistant.id
    run.provider = answer.provider
    run.status = "completed"
    run.error_code = None
    run.error_message = None
    run.completed_at = utc_now()
    _update_memory(
        db,
        chat_session=chat_session,
        gateway=gateway,
        settings=settings,
    )
    append_event(
        db,
        run.id,
        "run.completed",
        {"message_id": assistant.id, "provider": answer.provider},
    )
    db.commit()
    return {
        "run_id": run.id,
        "status": run.status,
        "assistant_message_id": assistant.id,
    }
