import json
import re
from collections.abc import Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.base import AgentGateway
from app.assessments.rubric import (
    UNIFIED_RUBRIC_VERSION,
    assess_answer_evidence,
    weighted_average,
)
from app.core.errors import AppError
from app.core.models import utc_now
from app.resumes.models import ResumeFile
from app.workplace.models import (
    SimulationMaterialBinding,
    SimulationMessage,
    SimulationScenario,
    SimulationSession,
    SimulationTurn,
    WorkplaceDeliverable,
)

VALID_MODES = frozenset(
    {
        "workplace",
        "group_interview",
        "stress_interview",
        "presentation_defense",
        "career_planning",
    }
)
DYNAMIC_EXCHANGE_MODES = frozenset(
    {"group_interview", "stress_interview", "presentation_defense", "career_planning"}
)
GROUP_STAGES = (
    "case_intro",
    "individual_statement",
    "free_discussion",
    "disagreement_resolution",
    "consensus",
    "summary",
    "scoring",
)
GROUP_ROLES = frozenset(
    {"candidate_logic", "candidate_collaboration", "candidate_challenger"}
)
STRESS_LEVELS = ("light", "medium", "high")
WORKPLACE_ACTION_TYPES = (
    "clarify_questions",
    "action_plan",
    "risk_register",
    "meeting_minutes",
    "weekly_report",
    "delivery_draft",
)
WORKPLACE_ACTION_LABELS = {
    "clarify_questions": "任务澄清问题清单",
    "action_plan": "行动计划",
    "risk_register": "风险清单",
    "meeting_minutes": "会议纪要与行动项",
    "weekly_report": "周报与进度汇报",
    "delivery_draft": "交付物草案",
}
UNSAFE_TRAINING_TERMS = ("废物", "滚", "羞辱", "威胁", "歧视", "人身攻击")


def _loads(value: str | None, default: object) -> object:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _list(value: str | None) -> list[object]:
    loaded = _loads(value, [])
    return loaded if isinstance(loaded, list) else []


def _scenario_mode(scenario: SimulationScenario) -> str:
    return scenario.mode if scenario.mode in VALID_MODES else "workplace"


def scenario_phase(mode: str) -> str:
    return "post_hire" if mode == "workplace" else "pre_hire"


def _work_context(scenario: SimulationScenario) -> dict[str, object]:
    value = _loads(scenario.work_context_json, {})
    return value if isinstance(value, dict) else {}


def _stages(scenario: SimulationScenario) -> list[dict[str, str]]:
    configured = _list(scenario.stage_definition_json)
    stages: list[dict[str, str]] = []
    for item in configured:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key", "")).strip()
        title = str(item.get("title", key)).strip()
        prompt = str(item.get("prompt", "")).strip()
        if key and title and prompt:
            stages.append({"key": key[:60], "title": title[:100], "prompt": prompt[:2_000]})
    if stages:
        return stages
    fallback_steps = _list(scenario.steps_json)
    return [
        {
            "key": f"step_{index}",
            "title": f"第 {index + 1} 轮",
            "prompt": str(item.get("prompt", ""))[:2_000]
            if isinstance(item, dict)
            else str(item)[:2_000],
        }
        for index, item in enumerate(fallback_steps)
    ]


def _stage_index(stages: list[dict[str, str]], key: str) -> int:
    for index, item in enumerate(stages):
        if item["key"] == key:
            return index
    return 0


def _next_stage(stages: list[dict[str, str]], stage: str) -> str:
    current = _stage_index(stages, stage)
    return stages[current + 1]["key"] if current + 1 < len(stages) else "scoring"


def _evaluate(response: str, rubric: list[dict[str, object]]) -> tuple[int, dict[str, object]]:
    normalized = response.strip()
    structure = (
        85
        if re.search(r"(?:第一|首先|1[.、])", normalized)
        and re.search(r"(?:第二|其次|2[.、])", normalized)
        else 65
    )
    evidence = 88 if re.search(r"(?:数据|指标|结果|验证|例如|项目)", normalized) else 62
    empathy = 86 if re.search(r"(?:理解|确认|协同|倾听|共识|对方)", normalized) else 64
    completeness = min(92, 55 + len(normalized) // 8)
    evidence_check = assess_answer_evidence(normalized)
    score = weighted_average(
        {
            "content_completeness": completeness,
            "job_relevance": empathy,
            "answer_structure": structure,
            "evidence_quality": evidence,
        }
    )
    strengths = []
    improvements = []
    if structure >= 80:
        strengths.append("表达具有清晰的步骤结构")
    else:
        improvements.append("先说明目标，再按步骤表达行动和结果")
    if evidence >= 80:
        strengths.append("使用了结果或验证证据")
    else:
        improvements.append("补充一个可核验的数据、项目或结果")
    if empathy >= 80:
        strengths.append("体现了沟通对象和协作意识")
    else:
        improvements.append("补充确认对方诉求和形成共识的动作")
    return score, {
        "rubric_version": UNIFIED_RUBRIC_VERSION,
        "dimensions": {
            "structure": structure,
            "evidence": evidence,
            "collaboration": empathy,
            "completeness": completeness,
        },
        "strengths": strengths,
        "improvements": improvements,
        "rubric": rubric,
        "evidence_check": evidence_check,
    }


def serialize_scenario(item: SimulationScenario) -> dict[str, object]:
    stages = _stages(item)
    return {
        "id": item.id,
        "title": item.title,
        "category": item.category,
        "difficulty": item.difficulty,
        "description": item.description,
        "mode": _scenario_mode(item),
        "phase": scenario_phase(_scenario_mode(item)),
        "competencies": [str(value) for value in _list(item.competencies_json)],
        "step_count": len(stages),
        "stages": [{"key": value["key"], "title": value["title"]} for value in stages],
        "work_context": _work_context(item),
        "safety_policy": _loads(item.safety_policy_json, {}),
    }


def _serialize_material(db: Session, item: SimulationMaterialBinding) -> dict[str, object]:
    name = "已绑定材料"
    if item.source_type == "resume":
        resume = db.get(ResumeFile, item.source_id)
        name = resume.original_name if resume else "已移除的简历"
    return {
        "id": item.id,
        "source_type": item.source_type,
        "source_id": item.source_id,
        "source_name": name,
        "purpose": item.purpose,
        "confirmed_at": item.confirmed_at.isoformat(),
    }


def _serialize_deliverable(item: WorkplaceDeliverable) -> dict[str, object]:
    return {
        "id": item.id,
        "session_id": item.session_id,
        "action_type": item.action_type,
        "action_label": WORKPLACE_ACTION_LABELS.get(item.action_type, item.action_type),
        "title": item.title,
        "content": item.content,
        "status": item.status,
        "revision": item.revision,
        "reviewer_feedback": item.reviewer_feedback,
        "review": _loads(item.review_json, None),
        "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
    }


def session_detail(db: Session, session: SimulationSession) -> dict[str, object]:
    scenario = db.get(SimulationScenario, session.scenario_id)
    if scenario is None:
        raise AppError(409, "simulation_scenario_missing", "训练场景已不可用")
    stages = _stages(scenario)
    current_index = _stage_index(stages, session.stage)
    turns = db.scalars(
        select(SimulationTurn)
        .where(SimulationTurn.session_id == session.id)
        .order_by(SimulationTurn.sequence)
    ).all()
    messages = db.scalars(
        select(SimulationMessage)
        .where(SimulationMessage.session_id == session.id)
        .order_by(SimulationMessage.sequence)
    ).all()
    bindings = db.scalars(
        select(SimulationMaterialBinding)
        .where(SimulationMaterialBinding.session_id == session.id)
        .order_by(SimulationMaterialBinding.created_at)
    ).all()
    deliverables = db.scalars(
        select(WorkplaceDeliverable)
        .where(WorkplaceDeliverable.session_id == session.id)
        .order_by(WorkplaceDeliverable.updated_at.desc(), WorkplaceDeliverable.created_at.desc())
    ).all()
    return {
        "id": session.id,
        "status": session.status,
        "mode": session.mode,
        "stage": session.stage,
        "stress_level": session.stress_level,
        "current_step": session.current_step,
        "score": session.score,
        "assessment": _loads(session.assessment_json, None),
        "report": _loads(session.report_json, None),
        "scenario": serialize_scenario(scenario),
        "phase": scenario_phase(session.mode),
        "work_context": _work_context(scenario),
        "current_prompt": stages[current_index]["prompt"]
        if session.status == "active" and current_index < len(stages)
        else None,
        "turns": [
            {
                "id": item.id,
                "sequence": item.sequence,
                "prompt": item.prompt,
                "response": item.response,
                "score": item.score,
                "feedback": _loads(item.feedback_json, {}),
            }
            for item in turns
        ],
        "messages": [
            {
                "id": item.id,
                "sequence": item.sequence,
                "speaker": item.speaker,
                "display_name": item.display_name,
                "stage": item.stage,
                "content": item.content,
                "reply_to": item.reply_to,
                "metadata": _loads(item.metadata_json, {}),
            }
            for item in messages
        ],
        "materials": [_serialize_material(db, item) for item in bindings],
        "deliverables": [_serialize_deliverable(item) for item in deliverables],
    }


def _get_owned_session(db: Session, *, student_id: str, session_id: str) -> SimulationSession:
    session = db.get(SimulationSession, session_id)
    if session is None or session.student_id != student_id:
        raise AppError(404, "simulation_session_not_found", "训练会话不存在")
    return session


def _get_owned_workplace_session(
    db: Session, *, student_id: str, session_id: str
) -> SimulationSession:
    session = _get_owned_session(db, student_id=student_id, session_id=session_id)
    if session.mode != "workplace":
        raise AppError(409, "workplace_session_required", "该会话属于入职前模拟面试")
    return session


def _validate_workplace_action(action_type: str) -> str:
    normalized = action_type.strip()
    if normalized not in WORKPLACE_ACTION_TYPES:
        raise AppError(422, "workplace_action_invalid", "不支持的职场交付物类型")
    return normalized


def _review_workplace_deliverable(
    *, content: str, action_type: str, context: dict[str, object]
) -> tuple[int, dict[str, object]]:
    normalized = " ".join(content.split())
    objective = str(context.get("objective", ""))
    stakeholders = context.get("stakeholders", [])
    has_objective = bool(objective) and any(
        part and part in normalized for part in re.split(r"[，。；、\s]+", objective) if len(part) >= 2
    )
    has_steps = bool(re.search(r"(?:^|\s)(?:\d+[.、)、]|[-*])", content, flags=re.MULTILINE))
    has_risk = any(term in normalized for term in ("风险", "依赖", "阻塞", "升级", "备选"))
    has_owner = any(term in normalized for term in ("负责人", "协作", "对接", "同步", "责任人"))
    has_acceptance = any(term in normalized for term in ("验收", "标准", "指标", "结果", "截止", "交付"))
    evidence = assess_answer_evidence(content)
    dimensions = {
        "objective_understanding": 88 if has_objective else 62,
        "actionability": 88 if has_steps else 65,
        "risk_awareness": 88 if has_risk or action_type == "risk_register" else 60,
        "stakeholder_alignment": 88 if has_owner and (stakeholders or "协作" in normalized) else 64,
        "delivery_quality": min(94, 58 + len(normalized) // 12) if has_acceptance else 64,
        "evidence_quality": 88
        if evidence.get("status") == "grounded"
        else 72
        if evidence.get("status") == "insufficient"
        else 58,
    }
    score = round(sum(dimensions.values()) / len(dimensions))
    strengths: list[str] = []
    improvements: list[str] = []
    if has_objective:
        strengths.append("围绕工作目标组织了内容")
    else:
        improvements.append("开头先复述任务目标和完成定义")
    if has_steps:
        strengths.append("行动可以按步骤执行")
    else:
        improvements.append("补充负责人、顺序和检查点")
    if has_risk:
        strengths.append("识别了依赖或风险")
    else:
        improvements.append("增加风险、依赖和升级路径")
    if has_acceptance:
        strengths.append("写明了交付或验收依据")
    else:
        improvements.append("补充可验证的验收标准和截止时间")
    return score, {
        "rubric_version": "workplace-v1",
        "dimensions": dimensions,
        "strengths": strengths,
        "improvements": improvements,
        "evidence_check": evidence,
    }


def _workplace_report(db: Session, session: SimulationSession) -> dict[str, object]:
    items = db.scalars(
        select(WorkplaceDeliverable)
        .where(
            WorkplaceDeliverable.session_id == session.id,
            WorkplaceDeliverable.status.in_(("submitted", "reviewed")),
        )
        .order_by(WorkplaceDeliverable.revision)
    ).all()
    dimensions: dict[str, list[int]] = {}
    strengths: list[str] = []
    improvements: list[str] = []
    evidence: list[dict[str, object]] = []
    for item in items:
        review = _loads(item.review_json, {})
        payload = review if isinstance(review, dict) else {}
        for key, value in dict(payload.get("dimensions", {})).items():
            if isinstance(value, int):
                dimensions.setdefault(str(key), []).append(value)
        strengths.extend(str(value) for value in payload.get("strengths", []) if value)
        improvements.extend(str(value) for value in payload.get("improvements", []) if value)
        evidence.append(
            {
                "deliverable_id": item.id,
                "action_type": item.action_type,
                "title": item.title,
                "revision": item.revision,
                "score": payload.get("score"),
                "submitted_at": item.submitted_at.isoformat() if item.submitted_at else None,
            }
        )
    averages = {
        key: round(sum(values) / len(values)) for key, values in dimensions.items() if values
    }
    return {
        "rubric_version": "workplace-v1",
        "mode": "workplace",
        "average_dimensions": averages,
        "strengths": list(dict.fromkeys(strengths))[:6],
        "improvements": list(dict.fromkeys(improvements))[:6],
        "evidence": evidence,
    }


def list_workplace_deliverables(
    db: Session, *, student_id: str, session_id: str
) -> list[dict[str, object]]:
    _get_owned_workplace_session(db, student_id=student_id, session_id=session_id)
    items = db.scalars(
        select(WorkplaceDeliverable)
        .where(
            WorkplaceDeliverable.session_id == session_id,
            WorkplaceDeliverable.student_id == student_id,
        )
        .order_by(WorkplaceDeliverable.updated_at.desc(), WorkplaceDeliverable.created_at.desc())
    ).all()
    return [_serialize_deliverable(item) for item in items]


def save_workplace_deliverable(
    db: Session,
    *,
    student_id: str,
    session_id: str,
    action_type: str,
    title: str,
    content: str,
) -> WorkplaceDeliverable:
    session = _get_owned_workplace_session(db, student_id=student_id, session_id=session_id)
    if session.status not in {"active", "paused"}:
        raise AppError(409, "workplace_session_closed", "已完成的职场训练不能继续修改草案")
    normalized_action = _validate_workplace_action(action_type)
    normalized_content = content.strip()
    if len(normalized_content) < 20:
        raise AppError(422, "workplace_deliverable_too_short", "交付物至少需要 20 个字符")
    normalized_title = title.strip()[:200] or WORKPLACE_ACTION_LABELS[normalized_action]
    latest = db.scalar(
        select(WorkplaceDeliverable)
        .where(
            WorkplaceDeliverable.session_id == session_id,
            WorkplaceDeliverable.student_id == student_id,
            WorkplaceDeliverable.action_type == normalized_action,
        )
        .order_by(WorkplaceDeliverable.revision.desc())
    )
    if latest is not None and latest.status == "draft":
        latest.title = normalized_title
        latest.content = normalized_content
        latest.reviewer_feedback = None
        latest.review_json = None
        latest.submitted_at = None
        db.commit()
        db.refresh(latest)
        return latest
    item = WorkplaceDeliverable(
        session_id=session_id,
        student_id=student_id,
        action_type=normalized_action,
        title=normalized_title,
        content=normalized_content,
        status="draft",
        revision=(latest.revision + 1) if latest else 1,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def submit_workplace_deliverable(
    db: Session,
    *,
    student_id: str,
    session_id: str,
    action_type: str,
    title: str,
    content: str,
) -> WorkplaceDeliverable:
    session = _get_owned_workplace_session(db, student_id=student_id, session_id=session_id)
    if session.status not in {"active", "paused"}:
        raise AppError(409, "workplace_session_closed", "已完成的职场训练不能再次提交")
    normalized_action = _validate_workplace_action(action_type)
    normalized_content = content.strip()
    if len(normalized_content) < 20:
        raise AppError(422, "workplace_deliverable_too_short", "交付物至少需要 20 个字符")
    item = save_workplace_deliverable(
        db,
        student_id=student_id,
        session_id=session_id,
        action_type=normalized_action,
        title=title,
        content=normalized_content,
    )
    scenario = db.get(SimulationScenario, session.scenario_id)
    context = _work_context(scenario) if scenario else {}
    score, review = _review_workplace_deliverable(
        content=item.content, action_type=item.action_type, context=context
    )
    review["score"] = score
    item.status = "submitted"
    item.review_json = json.dumps(review, ensure_ascii=False)
    item.reviewer_feedback = "；".join(review["improvements"][:3]) or "交付物已提交，可继续补充事实证据。"
    item.submitted_at = utc_now()
    db.commit()
    db.refresh(item)
    return item


def complete_workplace_session(
    db: Session, *, student_id: str, session_id: str
) -> SimulationSession:
    session = _get_owned_workplace_session(db, student_id=student_id, session_id=session_id)
    if session.status not in {"active", "paused"}:
        raise AppError(409, "workplace_complete_invalid", "当前职场训练不能完成")
    submitted = db.scalars(
        select(WorkplaceDeliverable).where(
            WorkplaceDeliverable.session_id == session.id,
            WorkplaceDeliverable.status.in_(("submitted", "reviewed")),
        )
    ).all()
    if not submitted:
        raise AppError(409, "workplace_deliverables_required", "至少提交一份工作交付物后才能完成训练")
    scores = [
        int((_loads(item.review_json, {}) or {}).get("score", 0))
        for item in submitted
        if isinstance(_loads(item.review_json, {}), dict)
    ]
    session.score = round(sum(scores) / len(scores)) if scores else 0
    session.status = "completed"
    session.stage = "scoring"
    session.completed_at = utc_now()
    session.report_json = json.dumps(_workplace_report(db, session), ensure_ascii=False)
    session.assessment_json = json.dumps(
        {
            "summary": "职场交付物已提交并完成工作能力复盘。",
            "next_action": "根据风险清单和改进建议，在真实工作中补充下一轮证据。",
        },
        ensure_ascii=False,
    )
    db.commit()
    db.refresh(session)
    return session


def generate_workplace_deliverable(
    db: Session,
    *,
    student_id: str,
    session_id: str,
    action_type: str,
    gateway: AgentGateway,
) -> tuple[WorkplaceDeliverable, object]:
    session = _get_owned_workplace_session(db, student_id=student_id, session_id=session_id)
    if session.status not in {"active", "paused"}:
        raise AppError(409, "workplace_session_closed", "已完成的职场训练不能生成新草案")
    normalized_action = _validate_workplace_action(action_type)
    scenario = db.get(SimulationScenario, session.scenario_id)
    if scenario is None:
        raise AppError(409, "simulation_scenario_missing", "训练场景已不可用")
    history = list_workplace_deliverables(db, student_id=student_id, session_id=session_id)
    current = next(
        (item for item in history if item["action_type"] == normalized_action and item["status"] == "draft"),
        None,
    )
    generated = gateway.generate_workplace_deliverable(
        action_type=normalized_action,
        work_context=_work_context(scenario),
        session_history=history,
        current_draft=str(current["content"]) if current else None,
    )
    if generated.action_type != normalized_action:
        raise AppError(502, "workplace_agent_action_invalid", "工作 Agent 返回了不匹配的交付物类型")
    item = save_workplace_deliverable(
        db,
        student_id=student_id,
        session_id=session_id,
        action_type=normalized_action,
        title=generated.title,
        content=generated.content,
    )
    return item, generated


def start_session(
    db: Session, student_id: str, scenario_id: str, *, commit: bool = True
) -> SimulationSession:
    scenario = db.get(SimulationScenario, scenario_id)
    if scenario is None or scenario.status != "active":
        raise AppError(404, "simulation_scenario_not_found", "训练场景不存在")
    mode = _scenario_mode(scenario)
    active = db.scalar(
        select(SimulationSession).where(
            SimulationSession.student_id == student_id,
            SimulationSession.scenario_id == scenario_id,
            SimulationSession.status.in_(("active", "paused")),
        )
    )
    if active:
        return active
    stages = _stages(scenario)
    if not stages:
        raise AppError(409, "simulation_stages_missing", "训练场景未配置有效流程")
    item = SimulationSession(
        student_id=student_id,
        scenario_id=scenario_id,
        mode=mode,
        stage=stages[0]["key"],
        stress_level="light",
    )
    db.add(item)
    if commit:
        db.commit()
        db.refresh(item)
    else:
        db.flush()
    return item


def list_available_materials(db: Session, *, student_id: str) -> list[dict[str, object]]:
    resumes = db.scalars(
        select(ResumeFile)
        .where(ResumeFile.student_id == student_id, ResumeFile.parse_status == "parsed")
        .order_by(ResumeFile.updated_at.desc())
        .limit(30)
    ).all()
    return [
        {
            "source_type": "resume",
            "source_id": item.id,
            "source_name": item.original_name,
            "ready": bool(item.parsed_text),
        }
        for item in resumes
        if item.parsed_text
    ]


def bind_material(
    db: Session,
    *,
    student_id: str,
    session_id: str,
    source_type: str,
    source_id: str,
    purpose: str,
) -> SimulationMaterialBinding:
    session = _get_owned_session(db, student_id=student_id, session_id=session_id)
    if session.status not in {"active", "paused"}:
        raise AppError(409, "simulation_material_session_closed", "已结束训练不能再绑定材料")
    if source_type != "resume":
        raise AppError(422, "simulation_material_type_invalid", "目前仅支持绑定已解析的简历")
    resume = db.get(ResumeFile, source_id)
    if resume is None or resume.student_id != student_id:
        raise AppError(404, "simulation_material_not_found", "训练材料不存在")
    if resume.parse_status != "parsed" or not resume.parsed_text:
        raise AppError(409, "simulation_material_not_ready", "简历尚未解析完成，不能用于训练")
    normalized_purpose = purpose.strip()[:60] or "answer_context"
    existing = db.scalar(
        select(SimulationMaterialBinding).where(
            SimulationMaterialBinding.session_id == session.id,
            SimulationMaterialBinding.source_type == source_type,
            SimulationMaterialBinding.source_id == source_id,
            SimulationMaterialBinding.purpose == normalized_purpose,
        )
    )
    if existing:
        return existing
    item = SimulationMaterialBinding(
        session_id=session.id,
        student_id=student_id,
        source_type=source_type,
        source_id=source_id,
        purpose=normalized_purpose,
        context_preview="已由学生确认用于本次训练；原文仅在受控模型上下文中使用。",
        confirmed_at=utc_now(),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _material_context(db: Session, session: SimulationSession) -> list[str]:
    bindings = db.scalars(
        select(SimulationMaterialBinding).where(SimulationMaterialBinding.session_id == session.id)
    ).all()
    values: list[str] = []
    for binding in bindings:
        if binding.source_type != "resume":
            continue
        resume = db.get(ResumeFile, binding.source_id)
        if resume and resume.student_id == session.student_id and resume.parsed_text:
            values.append(resume.parsed_text[:1_200])
    return values[:3]


def _message_sequence(db: Session, session_id: str) -> int:
    value = db.scalar(
        select(func.max(SimulationMessage.sequence)).where(SimulationMessage.session_id == session_id)
    )
    return int(value or 0) + 1


def _validate_exchange(mode: str, exchange_speakers: Iterable[str], expected_stage: str, next_stage: str) -> None:
    speakers = list(exchange_speakers)
    if next_stage != expected_stage:
        raise AppError(502, "training_exchange_stage_invalid", "训练 Agent 返回了非法流程阶段")
    if mode == "group_interview" and set(speakers) != GROUP_ROLES:
        raise AppError(502, "training_exchange_roles_invalid", "群面 Agent 必须返回三个预设候选人角色")
    if mode == "stress_interview" and speakers != ["interviewer"]:
        raise AppError(502, "training_exchange_roles_invalid", "压力训练只能由面试官角色继续追问")


    if mode == "presentation_defense" and speakers != ["reviewer"]:
        raise AppError(
            502,
            "training_exchange_roles_invalid",
            "\u7b54\u8fa9\u8bad\u7ec3\u53ea\u80fd\u7531\u8bc4\u59d4\u89d2\u8272\u53d1\u8d77\u8ffd\u95ee",
        )
    if mode == "career_planning" and speakers != ["career_coach"]:
        raise AppError(
            502,
            "training_exchange_roles_invalid",
            "\u804c\u4e1a\u89c4\u5212\u8bad\u7ec3\u53ea\u80fd\u7531\u804c\u4e1a\u6559\u7ec3\u89d2\u8272\u7ee7\u7eed\u5f15\u5bfc",
        )


def _ensure_safe_exchange(messages: Iterable[str]) -> None:
    for content in messages:
        if any(term in content for term in UNSAFE_TRAINING_TERMS):
            raise AppError(502, "training_exchange_safety_rejected", "训练 Agent 输出不符合安全规范")


def _build_report(turns: list[SimulationTurn], mode: str) -> dict[str, object]:
    dimensions: dict[str, list[int]] = {}
    strengths: list[str] = []
    improvements: list[str] = []
    evidence: list[dict[str, object]] = []
    for turn in turns:
        feedback = _loads(turn.feedback_json, {})
        payload = feedback if isinstance(feedback, dict) else {}
        for key, value in dict(payload.get("dimensions", {})).items():
            if isinstance(value, int):
                dimensions.setdefault(str(key), []).append(value)
        strengths.extend(str(item) for item in payload.get("strengths", []) if item)
        improvements.extend(str(item) for item in payload.get("improvements", []) if item)
        evidence.append(
            {
                "turn": turn.sequence,
                "score": turn.score,
                "response_excerpt": turn.response.strip()[:180],
            }
        )
    return {
        "rubric_version": UNIFIED_RUBRIC_VERSION,
        "mode": mode,
        "average_dimensions": {
            key: round(sum(values) / len(values)) for key, values in dimensions.items() if values
        },
        "strengths": list(dict.fromkeys(strengths))[:4],
        "improvements": list(dict.fromkeys(improvements))[:4],
        "evidence": evidence,
    }


def _complete_session(db: Session, session: SimulationSession) -> None:
    turns = db.scalars(
        select(SimulationTurn)
        .where(SimulationTurn.session_id == session.id)
        .order_by(SimulationTurn.sequence)
    ).all()
    session.score = round(sum(item.score for item in turns) / len(turns)) if turns else 0
    session.status = "completed"
    session.stage = "scoring"
    session.completed_at = utc_now()
    report = _build_report(turns, session.mode)
    session.report_json = json.dumps(report, ensure_ascii=False)
    session.assessment_json = json.dumps(
        {
            "summary": "训练已完成，报告中的评分均来自本次实际提交的回答。",
            "next_action": "优先针对最低分维度补充一段包含行动、协作和结果证据的回答。",
        },
        ensure_ascii=False,
    )


def answer_session(
    db: Session,
    *,
    student_id: str,
    session_id: str,
    response: str,
    gateway: AgentGateway | None = None,
) -> SimulationSession:
    session = _get_owned_session(db, student_id=student_id, session_id=session_id)
    if session.status == "paused":
        raise AppError(409, "simulation_session_paused", "训练已暂停，请恢复后再提交回答")
    if session.status != "active":
        raise AppError(409, "simulation_session_completed", "训练会话已结束")
    scenario = db.get(SimulationScenario, session.scenario_id)
    if scenario is None:
        raise AppError(409, "simulation_scenario_missing", "训练场景已不可用")
    stages = _stages(scenario)
    if not stages or session.stage == "scoring":
        raise AppError(409, "simulation_state_invalid", "训练会话状态无效")
    stage_index = _stage_index(stages, session.stage)
    prompt = stages[stage_index]["prompt"]
    score, feedback = _evaluate(response, _list(scenario.rubric_json))
    turn = SimulationTurn(
        session_id=session.id,
        student_id=student_id,
        sequence=session.current_step + 1,
        prompt=prompt,
        response=response.strip(),
        score=score,
        feedback_json=json.dumps(feedback, ensure_ascii=False),
    )
    db.add(turn)
    db.flush()

    mode = session.mode if session.mode in VALID_MODES else _scenario_mode(scenario)
    expected_stage = _next_stage(stages, session.stage)
    if mode in DYNAMIC_EXCHANGE_MODES and expected_stage != "scoring":
        if gateway is None:
            raise AppError(503, "training_agent_unavailable", "训练 Agent 未初始化")
        exchange = gateway.generate_training_exchange(
            mode=mode,
            stage=session.stage,
            prompt=prompt,
            student_response=response.strip(),
            stress_level=session.stress_level,
            material_context=_material_context(db, session),
            expected_stage=expected_stage,
        )
        _validate_exchange(
            mode,
            [item.speaker for item in exchange.messages],
            expected_stage,
            exchange.next_stage,
        )
        _ensure_safe_exchange(item.content for item in exchange.messages)
        next_sequence = _message_sequence(db, session.id)
        created: dict[str, SimulationMessage] = {}
        references: list[tuple[SimulationMessage, str | None]] = []
        for item in exchange.messages:
            message = SimulationMessage(
                session_id=session.id,
                sequence=next_sequence,
                speaker=item.speaker,
                display_name=item.display_name,
                stage=session.stage,
                content=item.content,
                metadata_json=json.dumps(
                    {"provider": exchange.provider, "reply_to_speaker": item.reply_to_speaker},
                    ensure_ascii=False,
                ),
            )
            db.add(message)
            created[item.speaker] = message
            references.append((message, item.reply_to_speaker))
            next_sequence += 1
        db.flush()
        for message, reply_to_speaker in references:
            if reply_to_speaker and reply_to_speaker in created:
                message.reply_to = created[reply_to_speaker].id
        feedback["agent_feedback"] = exchange.feedback
        feedback["agent_provider"] = exchange.provider
        turn.feedback_json = json.dumps(feedback, ensure_ascii=False)

    session.current_step += 1
    if expected_stage == "scoring":
        _complete_session(db, session)
    else:
        session.stage = expected_stage
    db.commit()
    db.refresh(session)
    return session


def control_session(
    db: Session,
    *,
    student_id: str,
    session_id: str,
    action: str,
    pressure_level: str | None = None,
) -> SimulationSession:
    session = _get_owned_session(db, student_id=student_id, session_id=session_id)
    if action == "pause":
        if session.status != "active":
            raise AppError(409, "simulation_pause_invalid", "当前训练不能暂停")
        session.status = "paused"
    elif action == "resume":
        if session.status != "paused":
            raise AppError(409, "simulation_resume_invalid", "当前训练不能恢复")
        session.status = "active"
    elif action in {"lower_pressure", "set_pressure"}:
        if session.mode != "stress_interview":
            raise AppError(409, "simulation_pressure_invalid", "只有压力训练可以调整强度")
        if session.status not in {"active", "paused"}:
            raise AppError(409, "simulation_pressure_session_closed", "当前训练不能调整压力")
        if action == "lower_pressure":
            current = STRESS_LEVELS.index(session.stress_level) if session.stress_level in STRESS_LEVELS else 0
            session.stress_level = STRESS_LEVELS[max(0, current - 1)]
        else:
            if pressure_level not in STRESS_LEVELS:
                raise AppError(422, "simulation_pressure_level_invalid", "请选择低、中或高压力等级")
            session.stress_level = pressure_level
    elif action == "stop":
        if session.status not in {"active", "paused"}:
            raise AppError(409, "simulation_stop_invalid", "当前训练不能停止")
        session.status = "stopped"
        session.completed_at = utc_now()
        session.assessment_json = json.dumps(
            {"summary": "训练已由学生主动停止，已保留此前回答但未生成完成评分。"},
            ensure_ascii=False,
        )
    elif action == "complete":
        return complete_workplace_session(db, student_id=student_id, session_id=session_id)
    else:
        raise AppError(422, "simulation_control_invalid", "不支持的训练控制操作")
    db.commit()
    db.refresh(session)
    return session


def list_training_reports(
    db: Session, *, student_id: str, phase: str | None = None
) -> list[dict[str, object]]:
    sessions = db.scalars(
        select(SimulationSession)
        .where(SimulationSession.student_id == student_id, SimulationSession.status == "completed")
        .order_by(SimulationSession.completed_at.desc())
        .limit(100)
    ).all()
    rows: list[dict[str, object]] = []
    for session in sessions:
        scenario = db.get(SimulationScenario, session.scenario_id)
        if scenario is None:
            continue
        if phase == "post_hire" and session.mode != "workplace":
            continue
        if phase == "pre_hire" and session.mode == "workplace":
            continue
        rows.append(
            {
                "id": session.id,
                "title": scenario.title,
                "mode": session.mode,
                "score": session.score,
                "completed_at": session.completed_at.isoformat() if session.completed_at else None,
                "report": _loads(session.report_json, {}),
            }
        )
    return rows
