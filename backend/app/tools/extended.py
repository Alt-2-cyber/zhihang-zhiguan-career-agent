from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.core.errors import AppError
from app.employment.models import EmploymentRecord
from app.employment.service import create_employment, employment_summary
from app.growth.models import LearningTask
from app.growth.service import get_growth_overview, update_learning_task
from app.intelligence.service import job_intelligence_overview
from app.tools.contracts import (
    ToolDefinition,
    ToolExecutionContext,
    ToolHandlerResult,
    ToolRisk,
)
from app.tools.registry import ToolRegistry
from app.workplace.models import SimulationSession, WorkplaceDeliverable
from app.workplace.service import _serialize_deliverable, session_detail, start_session


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyArguments(Arguments):
    pass


class LearningTaskUpdateArguments(Arguments):
    task_id: str = Field(min_length=36, max_length=36)
    status: Literal["pending", "in_progress", "completed"]
    completion_note: str | None = Field(default=None, max_length=2000)
    evidence_url: str | None = Field(default=None, max_length=1000)


class ScenarioStartArguments(Arguments):
    scenario_id: str = Field(min_length=36, max_length=36)


class WorkplaceDeliverableArguments(Arguments):
    session_id: str | None = Field(default=None, min_length=36, max_length=36)
    action_type: str | None = Field(default=None, max_length=40)


class EmploymentCreateArguments(Arguments):
    application_id: str = Field(min_length=36, max_length=36)
    onboard_date: date
    student_consent: bool = False


class RecordOutput(BaseModel):
    record: dict[str, object] | None


class ItemsOutput(BaseModel):
    items: list[dict[str, object]]


class WriteOutput(BaseModel):
    id: str
    status: str
    updated_at: str | None = None


def _subject(context: ToolExecutionContext) -> str:
    if context.subject_student_id is None:
        raise AppError(409, "context_requires_student", "该工具需要明确学生范围")
    return context.subject_student_id


def _growth_overview(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    return ToolHandlerResult(output={"record": get_growth_overview(db, _subject(context))})


def _workplace_sessions(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    items = db.scalars(
        select(SimulationSession)
        .where(SimulationSession.student_id == _subject(context))
        .order_by(SimulationSession.updated_at.desc())
        .limit(20)
    ).all()
    return ToolHandlerResult(output={"items": [session_detail(db, item) for item in items]})


def _workplace_deliverables(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, WorkplaceDeliverableArguments)
    query = select(WorkplaceDeliverable).where(
        WorkplaceDeliverable.student_id == _subject(context)
    )
    if arguments.session_id:
        query = query.where(WorkplaceDeliverable.session_id == arguments.session_id)
    if arguments.action_type:
        query = query.where(WorkplaceDeliverable.action_type == arguments.action_type)
    items = db.scalars(query.order_by(WorkplaceDeliverable.updated_at.desc()).limit(50)).all()
    return ToolHandlerResult(output={"items": [_serialize_deliverable(item) for item in items]})


def _intelligence_overview(
    db: Session, _arguments: BaseModel, _context: ToolExecutionContext
) -> ToolHandlerResult:
    return ToolHandlerResult(output={"record": job_intelligence_overview(db)})


def _employment_records(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    items = db.scalars(
        select(EmploymentRecord)
        .where(EmploymentRecord.student_id == _subject(context))
        .order_by(EmploymentRecord.onboard_date.desc())
        .limit(20)
    ).all()
    return ToolHandlerResult(output={"items": [employment_summary(db, item) for item in items]})


def _update_learning_task(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, LearningTaskUpdateArguments)
    task = db.get(LearningTask, arguments.task_id)
    if task is None or task.student_id != _subject(context):
        raise AppError(404, "learning_task_not_found", "学习任务不存在")
    previous = {
        "task_id": task.id,
        "status": task.status,
        "completion_note": task.completion_note,
        "evidence_url": task.evidence_url,
        "expected_updated_at": task.updated_at.isoformat(),
    }
    updated = update_learning_task(
        db,
        student_id=task.student_id,
        task_id=task.id,
        status=arguments.status,
        completion_note=arguments.completion_note,
        evidence_url=arguments.evidence_url,
        commit=False,
    )
    previous["expected_status"] = updated.status
    return ToolHandlerResult(
        output={
            "id": updated.id,
            "status": updated.status,
            "updated_at": updated.updated_at.isoformat(),
        },
        undo_data=previous,
    )


def _undo_learning_task(
    db: Session, undo: dict[str, object], context: ToolExecutionContext
) -> ToolHandlerResult:
    task = db.get(LearningTask, str(undo["task_id"]))
    if task is None or task.student_id != _subject(context):
        raise AppError(404, "learning_task_not_found", "学习任务不存在")
    if task.status != undo["expected_status"]:
        raise AppError(409, "undo_conflict", "学习任务已被后续操作修改")
    updated = update_learning_task(
        db,
        student_id=task.student_id,
        task_id=task.id,
        status=str(undo["status"]),
        completion_note=str(undo["completion_note"]) if undo.get("completion_note") else None,
        evidence_url=str(undo["evidence_url"]) if undo.get("evidence_url") else None,
        commit=False,
    )
    return ToolHandlerResult(
        output={
            "id": updated.id,
            "status": updated.status,
            "updated_at": updated.updated_at.isoformat(),
        }
    )


def _start_workplace_session(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, ScenarioStartArguments)
    item = start_session(db, _subject(context), arguments.scenario_id, commit=False)
    return ToolHandlerResult(
        output={"id": item.id, "status": item.status, "updated_at": item.updated_at.isoformat()}
    )


def _create_employment(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, EmploymentCreateArguments)
    actor = db.get(User, context.actor_id)
    if actor is None or actor.role != UserRole.student or actor.id != _subject(context):
        raise AppError(403, "tool_forbidden", "只有学生可以建立自己的就业记录")
    item = create_employment(
        db,
        student=actor,
        application_id=arguments.application_id,
        onboard_date=arguments.onboard_date,
        consent=arguments.student_consent,
        commit=False,
    )
    return ToolHandlerResult(
        output={"id": item.id, "status": item.status, "updated_at": item.updated_at.isoformat()}
    )


def register_extended_tools(registry: ToolRegistry) -> None:
    all_roles = frozenset({UserRole.student, UserRole.counselor, UserRole.admin})
    definitions = [
        ToolDefinition(
            "growth.overview",
            "1",
            "读取授权学生的技能差距、学习计划和完成进度",
            EmptyArguments,
            RecordOutput,
            all_roles,
            frozenset({"learning", "career", "counselor"}),
            ToolRisk.read,
            False,
            _growth_overview,
        ),
        ToolDefinition(
            "workplace.sessions",
            "1",
            "读取授权学生的职场模拟训练历史和评分",
            EmptyArguments,
            ItemsOutput,
            all_roles,
            frozenset({"workplace", "career", "counselor"}),
            ToolRisk.read,
            False,
            _workplace_sessions,
        ),
        ToolDefinition(
            "workplace.deliverables",
            "1",
            "读取授权学生的入职后工作交付物、版本和评审结果",
            WorkplaceDeliverableArguments,
            ItemsOutput,
            all_roles,
            frozenset({"workplace", "career", "counselor"}),
            ToolRisk.read,
            False,
            _workplace_deliverables,
        ),
        ToolDefinition(
            "intelligence.overview",
            "1",
            "读取合规岗位来源、时效和招聘趋势聚合",
            EmptyArguments,
            RecordOutput,
            all_roles,
            frozenset({"intelligence", "job", "career", "counselor"}),
            ToolRisk.read,
            False,
            _intelligence_overview,
        ),
        ToolDefinition(
            "employment.records",
            "1",
            "读取授权学生的就业记录和回访摘要，不返回企业原始评价",
            EmptyArguments,
            ItemsOutput,
            all_roles,
            frozenset({"employment", "career", "counselor"}),
            ToolRisk.read,
            False,
            _employment_records,
        ),
        ToolDefinition(
            "growth.update_task",
            "1",
            "更新学生学习任务状态并记录成果证据",
            LearningTaskUpdateArguments,
            WriteOutput,
            frozenset({UserRole.student}),
            frozenset({"learning"}),
            ToolRisk.normal_write,
            True,
            _update_learning_task,
            _undo_learning_task,
        ),
        ToolDefinition(
            "workplace.start_session",
            "1",
            "创建或恢复一个职场模拟训练会话",
            ScenarioStartArguments,
            WriteOutput,
            frozenset({UserRole.student}),
            frozenset({"workplace"}),
            ToolRisk.normal_write,
            False,
            _start_workplace_session,
        ),
        ToolDefinition(
            "employment.create_record",
            "1",
            "将本人已录用投递转为就业记录并生成回访节点",
            EmploymentCreateArguments,
            WriteOutput,
            frozenset({UserRole.student}),
            frozenset({"employment"}),
            ToolRisk.normal_write,
            False,
            _create_employment,
        ),
    ]
    for definition in definitions:
        registry.register(definition)
