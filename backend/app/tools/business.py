import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import Any, Literal
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.agents.contracts import ResumeSuggestion
from app.ai.clients import LocalAIClients
from app.ai.models import AITask
from app.applications.models import Application, ApplicationEvent
from app.applications.service import transition_application_stage
from app.auth.models import User, UserRole
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.models import utc_now
from app.interventions.models import Intervention
from app.interventions.service import assign_intervention
from app.jobs.models import Job
from app.jobs.retrieval import retrieve_document_chunks
from app.plans.models import CareerPlanRecord, PlanTaskRecord
from app.resumes.models import ResumeFile, ResumeOptimizationDraft
from app.risks.models import RiskEvent
from app.students.models import StudentProfile
from app.tools.contracts import (
    ToolCitation,
    ToolDefinition,
    ToolExecutionContext,
    ToolHandlerResult,
    ToolRisk,
)
from app.tools.extended import register_extended_tools
from app.tools.public_jobs import (
    BingPublicJobSearch,
    PublicJobSearchError,
    source_trust,
    validate_public_http_url,
)
from app.tools.registry import ToolRegistry


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EmptyArguments(Arguments):
    pass


class ResourceArguments(Arguments):
    resource_id: str = Field(min_length=1, max_length=120)

    @field_validator("resource_id")
    @classmethod
    def reject_placeholder_ids(cls, value: str) -> str:
        normalized = value.strip().casefold()
        placeholders = {
            "current",
            "current_id",
            "placeholder",
            "resource_id",
            "task_id",
            "id",
        }
        if (
            normalized in placeholders
            or "placeholder" in normalized
            or "对应的id" in normalized
            or "对应id" in normalized
        ):
            raise ValueError("resource_id must be a real resource identifier")
        return value

    @model_validator(mode="before")
    @classmethod
    def accept_resource_id_aliases(cls, value: object) -> object:
        """Accept common model aliases without weakening the required-id contract."""
        if not isinstance(value, dict) or "resource_id" in value:
            return value
        data = dict(value)
        for alias in ("id", "task_id", "resourceId"):
            if alias in data:
                data["resource_id"] = data.pop(alias)
                break
        return data


class InternalJobSearchArguments(Arguments):
    query: str = Field(min_length=1, max_length=120)
    limit: int = Field(default=5, ge=1, le=10)


class KnowledgeSearchArguments(Arguments):
    query: str = Field(min_length=1, max_length=500)
    source_types: list[str] = Field(min_length=1, max_length=6)
    limit: int = Field(default=5, ge=1, le=10)


class PlanTaskArguments(Arguments):
    title: str = Field(min_length=1, max_length=120)
    week: int = Field(ge=1, le=4)
    due_date: date
    acceptance_criteria: str = Field(min_length=1, max_length=300)


class PlanDraftArguments(Arguments):
    primary_role: str = Field(min_length=1, max_length=100)
    backup_roles: list[str] = Field(default_factory=list, max_length=2)
    rationale: str = Field(min_length=1, max_length=2_000)
    tasks: list[PlanTaskArguments] = Field(min_length=1, max_length=20)


class TaskStatusArguments(Arguments):
    task_id: str = Field(min_length=1, max_length=36)
    status: Literal["pending", "completed"]
    expected_updated_at: datetime | None = None


class ApplicationStageArguments(Arguments):
    application_id: str = Field(min_length=1, max_length=36)
    stage: Literal["saved", "applied", "assessment", "interview", "offered", "closed"]


class ResumeDraftArguments(Arguments):
    resume_id: str = Field(min_length=1, max_length=36)
    job_id: str = Field(min_length=1, max_length=36)
    suggestions: list[ResumeSuggestion] = Field(min_length=1, max_length=30)


class InterventionArguments(Arguments):
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=2_000)


class DeleteArguments(Arguments):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_id: str = Field(min_length=1, max_length=120)


class BulkUpdateArguments(Arguments):
    resource_type: str = Field(min_length=1, max_length=80)
    resource_ids: list[str] = Field(min_length=1, max_length=100)
    changes: dict[str, object]


class ExternalSubmitArguments(Arguments):
    application_id: str = Field(min_length=1, max_length=36)


class PublicJobSearchArguments(Arguments):
    query: str = Field(min_length=1, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    limit: int = Field(default=5, ge=1, le=10)


class PublicJobImportArguments(Arguments):
    title: str = Field(min_length=1, max_length=120)
    company: str = Field(min_length=1, max_length=160)
    location: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=10_000)
    source_url: str = Field(min_length=1, max_length=1_000)
    source_fetched_at: datetime


class RecordOutput(BaseModel):
    record: dict[str, Any] | None


class ItemsOutput(BaseModel):
    items: list[dict[str, Any]]


class WriteOutput(BaseModel):
    id: str
    status: str
    stage: str | None = None
    student_id: str | None = None
    primary_role: str | None = None
    updated_at: str | None = None


def _subject_id(context: ToolExecutionContext) -> str:
    if context.subject_student_id is None:
        raise ValueError("tool requires a student subject")
    return context.subject_student_id


def _record_result(
    record: dict[str, object] | None, citation: ToolCitation | None = None
) -> ToolHandlerResult:
    return ToolHandlerResult(
        output={"record": record},
        citations=(citation,) if citation is not None else (),
    )


def _profile_get(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    profile = db.scalar(
        select(StudentProfile).where(StudentProfile.student_id == _subject_id(context))
    )
    if profile is None:
        return _record_result(None)
    record = {
        "id": profile.id,
        "student_id": profile.student_id,
        "summary": profile.summary,
        "strengths": json.loads(profile.strengths_json),
        "gaps": json.loads(profile.gaps_json),
        "constraints": json.loads(profile.constraints_json),
        "status": profile.status,
        "version": profile.version,
        "updated_at": profile.updated_at.isoformat(),
    }
    return _record_result(
        record,
        ToolCitation(
            source_type="profile",
            source_id=profile.id,
            label="已确认就业画像",
            excerpt=profile.summary[:500],
        ),
    )


def _plan_get(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    plan = db.scalar(
        select(CareerPlanRecord)
        .where(CareerPlanRecord.student_id == _subject_id(context))
        .order_by(CareerPlanRecord.created_at.desc())
    )
    if plan is None:
        return _record_result(None)
    tasks = db.scalars(
        select(PlanTaskRecord)
        .where(PlanTaskRecord.plan_id == plan.id)
        .order_by(PlanTaskRecord.week, PlanTaskRecord.due_date)
    ).all()
    record = {
        "id": plan.id,
        "student_id": plan.student_id,
        "provider": plan.provider,
        "primary_role": plan.primary_role,
        "backup_roles": json.loads(plan.backup_roles_json),
        "rationale": plan.rationale,
        "status": plan.status,
        "updated_at": plan.updated_at.isoformat(),
        "tasks": [
            {
                "id": task.id,
                "title": task.title,
                "week": task.week,
                "due_date": task.due_date.isoformat(),
                "acceptance_criteria": task.acceptance_criteria,
                "status": task.status,
            }
            for task in tasks
        ],
    }
    return _record_result(
        record,
        ToolCitation(
            source_type="plan",
            source_id=plan.id,
            label="当前求职计划",
            excerpt=f"主目标：{plan.primary_role}；{plan.rationale}"[:500],
        ),
    )


def _tasks_list(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    tasks = db.scalars(
        select(PlanTaskRecord)
        .where(PlanTaskRecord.student_id == _subject_id(context))
        .order_by(PlanTaskRecord.due_date, PlanTaskRecord.id)
    ).all()
    return ToolHandlerResult(
        output={
            "items": [
                {
                    "id": item.id,
                    "plan_id": item.plan_id,
                    "title": item.title,
                    "week": item.week,
                    "due_date": item.due_date.isoformat(),
                    "acceptance_criteria": item.acceptance_criteria,
                    "status": item.status,
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in tasks
            ]
        }
    )


def _job_record(job: Job) -> dict[str, object]:
    return {
        "id": job.id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description[:4_000],
        "source_url": job.source_url,
        "source_kind": job.source_kind,
        "source_host": job.source_host,
        "source_trust_level": job.source_trust_level,
        "source_trust_score": job.source_trust_score,
        "source_fetched_at": (job.source_fetched_at.isoformat() if job.source_fetched_at else None),
        "status": job.status,
        "updated_at": job.updated_at.isoformat(),
    }


def _jobs_get(
    db: Session, arguments: BaseModel, _context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, ResourceArguments)
    job = db.get(Job, arguments.resource_id)
    if job is None or job.status != "active":
        return _record_result(None)
    return _record_result(
        _job_record(job),
        ToolCitation(
            source_type="job",
            source_id=job.id,
            label=f"{job.company} · {job.title}",
            excerpt=job.description[:500],
            url=job.source_url,
        ),
    )


def _jobs_search_internal(
    db: Session, arguments: BaseModel, _context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, InternalJobSearchArguments)
    pattern = f"%{arguments.query.strip()}%"
    jobs = db.scalars(
        select(Job)
        .where(
            Job.status == "active",
            or_(
                Job.title.ilike(pattern),
                Job.company.ilike(pattern),
                Job.location.ilike(pattern),
                Job.description.ilike(pattern),
            ),
        )
        .order_by(Job.updated_at.desc(), Job.id)
        .limit(arguments.limit)
    ).all()
    return ToolHandlerResult(output={"items": [_job_record(job) for job in jobs]})


def _resumes_list(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    resumes = db.scalars(
        select(ResumeFile)
        .where(ResumeFile.student_id == _subject_id(context))
        .order_by(ResumeFile.created_at.desc())
    ).all()
    return ToolHandlerResult(
        output={
            "items": [
                {
                    "id": item.id,
                    "original_name": item.original_name,
                    "media_type": item.media_type,
                    "size_bytes": item.size_bytes,
                    "parse_status": item.parse_status,
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in resumes
            ]
        }
    )


def _resumes_get(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, ResourceArguments)
    resume = db.get(ResumeFile, arguments.resource_id)
    if resume is None or resume.student_id != _subject_id(context):
        return _record_result(None)
    excerpt = (resume.parsed_text or "")[:4_000]
    record = {
        "id": resume.id,
        "original_name": resume.original_name,
        "media_type": resume.media_type,
        "size_bytes": resume.size_bytes,
        "parse_status": resume.parse_status,
        "parse_error": resume.parse_error,
        "text_excerpt": excerpt,
        "updated_at": resume.updated_at.isoformat(),
    }
    citation = (
        ToolCitation(
            source_type="resume",
            source_id=resume.id,
            label=resume.original_name,
            excerpt=excerpt[:500],
        )
        if excerpt
        else None
    )
    return _record_result(record, citation)


def _applications_list(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    rows = db.execute(
        select(Application, Job)
        .join(Job, Job.id == Application.job_id)
        .where(Application.student_id == _subject_id(context))
        .order_by(Application.updated_at.desc())
    ).all()
    return ToolHandlerResult(
        output={
            "items": [
                {
                    "id": application.id,
                    "job_id": job.id,
                    "job_title": job.title,
                    "company": job.company,
                    "stage": application.stage,
                    "resume_version_id": application.resume_version_id,
                    "updated_at": application.updated_at.isoformat(),
                }
                for application, job in rows
            ]
        }
    )


def _class_student_ids(db: Session, context: ToolExecutionContext) -> list[str]:
    actor = db.get(User, context.actor_id)
    if actor is None or actor.class_id is None:
        return []
    return list(
        db.scalars(
            select(User.id).where(
                User.role == UserRole.student,
                User.class_id == actor.class_id,
                User.is_active.is_(True),
            )
        ).all()
    )


def _risk_student_ids(db: Session, context: ToolExecutionContext) -> list[str]:
    return (
        [_subject_id(context)]
        if context.subject_student_id is not None
        else _class_student_ids(db, context)
    )


def _risks_list(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    student_ids = _risk_student_ids(db, context)
    risks = (
        db.scalars(
            select(RiskEvent)
            .where(RiskEvent.student_id.in_(student_ids), RiskEvent.status == "open")
            .order_by(RiskEvent.updated_at.desc())
        ).all()
        if student_ids
        else []
    )
    return ToolHandlerResult(
        output={
            "items": [
                {
                    "id": item.id,
                    "student_id": item.student_id,
                    "rule_code": item.rule_code,
                    "level": item.level,
                    "facts": json.loads(item.facts_json),
                    "status": item.status,
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in risks
            ]
        }
    )


def _interventions_list(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    student_ids = _risk_student_ids(db, context)
    items = (
        db.scalars(
            select(Intervention)
            .where(Intervention.student_id.in_(student_ids))
            .order_by(Intervention.updated_at.desc())
        ).all()
        if student_ids
        else []
    )
    return ToolHandlerResult(
        output={
            "items": [
                {
                    "id": item.id,
                    "student_id": item.student_id,
                    "title": item.title,
                    "description": item.description[:1_000],
                    "status": item.status,
                    "feedback": item.feedback,
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in items
            ]
        }
    )


def _ai_task_get(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, ResourceArguments)
    task = db.get(AITask, arguments.resource_id)
    allowed_owner = context.subject_student_id or context.actor_id
    if task is None or task.owner_id != allowed_owner:
        return _record_result(None)
    return _record_result(
        {
            "id": task.id,
            "task_type": task.task_type,
            "status": task.status,
            "result": task.result_data,
            "error_code": task.error_code,
            "attempt_count": task.attempt_count,
            "updated_at": task.updated_at.isoformat(),
        }
    )


def _class_summary(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    student_ids = _class_student_ids(db, context)
    risk_count = (
        db.scalar(
            select(func.count())
            .select_from(RiskEvent)
            .where(RiskEvent.student_id.in_(student_ids), RiskEvent.status == "open")
        )
        if student_ids
        else 0
    )
    application_count = (
        db.scalar(
            select(func.count())
            .select_from(Application)
            .where(Application.student_id.in_(student_ids))
        )
        if student_ids
        else 0
    )
    return _record_result(
        {
            "student_count": len(student_ids),
            "application_count": int(application_count or 0),
            "risk_count": int(risk_count or 0),
        }
    )


def _students_progress(
    db: Session, _arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    student_ids = _class_student_ids(db, context)
    students = (
        db.scalars(select(User).where(User.id.in_(student_ids)).order_by(User.display_name)).all()
        if student_ids
        else []
    )
    risks = (
        db.scalars(
            select(RiskEvent).where(
                RiskEvent.student_id.in_(student_ids), RiskEvent.status == "open"
            )
        ).all()
        if student_ids
        else []
    )
    return ToolHandlerResult(
        output={
            "items": [
                {
                    "id": student.id,
                    "display_name": student.display_name,
                    "risk_count": sum(1 for risk in risks if risk.student_id == student.id),
                }
                for student in students
            ]
        }
    )


def _default_embed_query(text: str) -> list[float]:
    with LocalAIClients(get_settings()) as clients:
        return clients.embed([text]).vectors[0]


def _knowledge_search_handler(
    embed_query: Callable[[str], list[float]],
) -> Callable[[Session, BaseModel, ToolExecutionContext], ToolHandlerResult]:
    def handler(
        db: Session, arguments: BaseModel, context: ToolExecutionContext
    ) -> ToolHandlerResult:
        assert isinstance(arguments, KnowledgeSearchArguments)
        matches = retrieve_document_chunks(
            db,
            embed_query(arguments.query),
            source_types=arguments.source_types,
            owner_id=context.subject_student_id,
            limit=arguments.limit,
        )
        items: list[dict[str, object]] = []
        citations: list[ToolCitation] = []
        for match in matches:
            metadata = json.loads(match.chunk.metadata_json)
            label = str(metadata.get("title") or match.chunk.source_type)
            items.append(
                {
                    "source_type": match.chunk.source_type,
                    "source_id": match.chunk.source_id,
                    "content": match.chunk.content,
                    "score": round(match.score, 6),
                    "metadata": metadata,
                }
            )
            citations.append(
                ToolCitation(
                    source_type=match.chunk.source_type,
                    source_id=match.chunk.source_id,
                    label=label[:160],
                    excerpt=match.chunk.content[:500],
                    url=str(metadata["url"]) if metadata.get("url") else None,
                )
            )
        return ToolHandlerResult(output={"items": items}, citations=tuple(citations))

    return handler


def _plan_create_draft(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, PlanDraftArguments)
    plan = CareerPlanRecord(
        student_id=_subject_id(context),
        provider="agent-chat",
        primary_role=arguments.primary_role,
        backup_roles_json=json.dumps(arguments.backup_roles, ensure_ascii=False),
        rationale=arguments.rationale,
        status="pending_confirmation",
    )
    db.add(plan)
    db.flush()
    for task in arguments.tasks:
        db.add(
            PlanTaskRecord(
                plan_id=plan.id,
                student_id=plan.student_id,
                title=task.title,
                week=task.week,
                due_date=task.due_date,
                acceptance_criteria=task.acceptance_criteria,
                status="pending",
            )
        )
    db.flush()
    return ToolHandlerResult(
        output={
            "id": plan.id,
            "status": plan.status,
            "primary_role": plan.primary_role,
            "updated_at": plan.updated_at.isoformat(),
        }
    )


def _task_update_status(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, TaskStatusArguments)
    task = db.get(PlanTaskRecord, arguments.task_id)
    if task is None or task.student_id != _subject_id(context):
        raise AppError(404, "task_not_found", "求职任务不存在")
    if arguments.expected_updated_at is not None:
        current = (
            task.updated_at
            if task.updated_at.tzinfo
            else task.updated_at.replace(tzinfo=timezone.utc)
        )
        expected = (
            arguments.expected_updated_at
            if arguments.expected_updated_at.tzinfo
            else arguments.expected_updated_at.replace(tzinfo=timezone.utc)
        )
        if current != expected:
            raise AppError(409, "action_stale", "求职任务已被其他操作修改")
    previous_status = task.status
    previous_completed_at = task.completed_at.isoformat() if task.completed_at else None
    task.status = arguments.status
    task.completed_at = utc_now() if arguments.status == "completed" else None
    db.flush()
    return ToolHandlerResult(
        output={
            "id": task.id,
            "status": task.status,
            "updated_at": task.updated_at.isoformat(),
        },
        undo_data={
            "task_id": task.id,
            "previous_status": previous_status,
            "previous_completed_at": previous_completed_at,
            "expected_status": task.status,
        },
    )


def _undo_task_status(
    db: Session, undo_data: dict[str, object], context: ToolExecutionContext
) -> ToolHandlerResult:
    task_id = str(undo_data["task_id"])
    task = db.get(PlanTaskRecord, task_id)
    if task is None or task.student_id != _subject_id(context):
        raise AppError(404, "task_not_found", "求职任务不存在")
    if task.status != undo_data["expected_status"]:
        raise AppError(409, "undo_conflict", "任务状态已被后续操作修改")
    task.status = str(undo_data["previous_status"])
    previous_completed_at = undo_data.get("previous_completed_at")
    task.completed_at = (
        None
        if previous_completed_at is None
        else datetime.fromisoformat(str(previous_completed_at))
    )
    db.flush()
    return ToolHandlerResult(
        output={
            "id": task.id,
            "status": task.status,
            "updated_at": task.updated_at.isoformat(),
        }
    )


def _application_update_stage(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, ApplicationStageArguments)
    actor = db.get(User, context.actor_id)
    if actor is None or actor.role != UserRole.student:
        raise AppError(403, "tool_forbidden", "只有学生可以更新自己的投递阶段")
    application, previous = transition_application_stage(
        db,
        student=actor,
        application_id=arguments.application_id,
        stage=arguments.stage,
    )
    db.flush()
    return ToolHandlerResult(
        output={
            "id": application.id,
            "status": application.stage,
            "stage": application.stage,
            "updated_at": application.updated_at.isoformat(),
        },
        undo_data={
            "application_id": application.id,
            "previous_stage": previous,
            "expected_stage": application.stage,
        },
    )


def _undo_application_stage(
    db: Session, undo_data: dict[str, object], context: ToolExecutionContext
) -> ToolHandlerResult:
    application = db.get(Application, str(undo_data["application_id"]))
    if application is None or application.student_id != _subject_id(context):
        raise AppError(404, "application_not_found", "投递记录不存在")
    if application.stage != undo_data["expected_stage"]:
        raise AppError(409, "undo_conflict", "投递阶段已被后续操作修改")
    previous = application.stage
    application.stage = str(undo_data["previous_stage"])
    db.add(
        ApplicationEvent(
            application_id=application.id,
            student_id=application.student_id,
            from_stage=previous,
            to_stage=application.stage,
        )
    )
    db.flush()
    return ToolHandlerResult(
        output={
            "id": application.id,
            "status": application.stage,
            "stage": application.stage,
            "updated_at": application.updated_at.isoformat(),
        }
    )


def _resume_create_draft(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, ResumeDraftArguments)
    resume = db.get(ResumeFile, arguments.resume_id)
    job = db.get(Job, arguments.job_id)
    if resume is None or resume.student_id != _subject_id(context):
        raise AppError(404, "resume_not_found", "简历不存在")
    if job is None:
        raise AppError(404, "job_not_found", "岗位不存在")
    draft = ResumeOptimizationDraft(
        student_id=resume.student_id,
        resume_id=resume.id,
        job_id=job.id,
        provider="agent-chat",
        suggestions_json=json.dumps(
            [item.model_dump(mode="json") for item in arguments.suggestions],
            ensure_ascii=False,
        ),
        status="pending",
    )
    db.add(draft)
    db.flush()
    return ToolHandlerResult(output={"id": draft.id, "status": draft.status})


def _intervention_create(
    db: Session, arguments: BaseModel, context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, InterventionArguments)
    counselor = db.get(User, context.actor_id)
    if counselor is None or counselor.role not in {UserRole.counselor, UserRole.admin}:
        raise AppError(403, "tool_forbidden", "只有辅导员可以创建帮扶任务")
    item = assign_intervention(
        db,
        counselor=counselor,
        student_id=_subject_id(context),
        title=arguments.title,
        description=arguments.description,
    )
    db.flush()
    return ToolHandlerResult(
        output={"id": item.id, "status": item.status, "student_id": item.student_id}
    )


def _unsupported_high_risk(
    _db: Session, _arguments: BaseModel, _context: ToolExecutionContext
) -> ToolHandlerResult:
    raise AppError(501, "operation_not_supported", "当前版本不执行该高风险操作")


def _public_job_search_handler(
    provider: BingPublicJobSearch,
) -> Callable[[Session, BaseModel, ToolExecutionContext], ToolHandlerResult]:
    def handler(
        _db: Session, arguments: BaseModel, _context: ToolExecutionContext
    ) -> ToolHandlerResult:
        assert isinstance(arguments, PublicJobSearchArguments)
        try:
            results = provider.search(
                query=arguments.query,
                city=arguments.city,
                limit=arguments.limit,
            )
        except PublicJobSearchError as error:
            raise AppError(503, "public_job_search_unavailable", "公开岗位搜索暂不可用") from error
        items = [item.model_dump(mode="json") for item in results]
        citations = tuple(
            ToolCitation(
                source_type="public_job",
                source_id=item.url,
                label=item.title,
                excerpt=item.snippet or item.title,
                url=item.url,
            )
            for item in results
        )
        return ToolHandlerResult(output={"items": items}, citations=citations)

    return handler


def _public_job_import(
    db: Session, arguments: BaseModel, _context: ToolExecutionContext
) -> ToolHandlerResult:
    assert isinstance(arguments, PublicJobImportArguments)
    try:
        source_url = validate_public_http_url(arguments.source_url)
    except ValueError as error:
        raise AppError(422, "invalid_public_job_url", "公开岗位来源地址无效") from error
    source_host = urlsplit(source_url).hostname or "unknown"
    trust_level, trust_score = source_trust(source_host)
    job = Job(
        title=arguments.title,
        company=arguments.company,
        location=arguments.location,
        description=arguments.description,
        source_url=source_url,
        source_kind="public_web",
        source_host=source_host,
        source_trust_level=trust_level,
        source_trust_score=trust_score,
        source_fetched_at=arguments.source_fetched_at,
        status="active",
    )
    db.add(job)
    db.flush()
    return ToolHandlerResult(output={"id": job.id, "status": job.status})


ALL_ROLES = frozenset({UserRole.student, UserRole.counselor, UserRole.admin})
ALL_SPECIALISTS = frozenset(
    {
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
    }
)


def _read_definition(
    *,
    name: str,
    description: str,
    input_model: type[BaseModel],
    output_model: type[BaseModel],
    specialists: frozenset[str],
    handler: Callable[[Session, BaseModel, ToolExecutionContext], ToolHandlerResult],
    roles: frozenset[UserRole] = ALL_ROLES,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        version="1",
        description=description,
        input_model=input_model,
        output_model=output_model,
        roles=roles,
        specialists=specialists,
        risk=ToolRisk.read,
        reversible=False,
        handler=handler,
    )


def _write_definition(
    *,
    name: str,
    description: str,
    input_model: type[BaseModel],
    specialists: frozenset[str],
    handler: Callable[[Session, BaseModel, ToolExecutionContext], ToolHandlerResult],
    roles: frozenset[UserRole],
    risk: ToolRisk = ToolRisk.normal_write,
    reversible: bool = False,
    undo_handler: Callable[[Session, dict[str, object], ToolExecutionContext], ToolHandlerResult]
    | None = None,
) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        version="1",
        description=description,
        input_model=input_model,
        output_model=WriteOutput,
        roles=roles,
        specialists=specialists,
        risk=risk,
        reversible=reversible,
        handler=handler,
        undo_handler=undo_handler,
    )


def build_business_tool_registry(
    *,
    embed_query: Callable[[str], list[float]] | None = None,
    public_job_search: BingPublicJobSearch | None = None,
) -> ToolRegistry:
    registry = ToolRegistry()
    settings = get_settings()
    if public_job_search is None:
        public_job_search = BingPublicJobSearch(
            base_url=settings.public_job_search_base_url,
            client=httpx.Client(timeout=settings.public_job_search_timeout_seconds),
            max_results=settings.public_job_search_max_results,
            retry_attempts=settings.public_job_search_retry_attempts,
        )
    definitions = [
        _read_definition(
            name="profile.get",
            description="读取当前授权学生的已确认就业画像",
            input_model=EmptyArguments,
            output_model=RecordOutput,
            specialists=frozenset({"career", "job", "resume", "counselor"}),
            handler=_profile_get,
        ),
        _read_definition(
            name="plan.get",
            description="读取当前授权学生最近的求职计划和任务",
            input_model=EmptyArguments,
            output_model=RecordOutput,
            specialists=frozenset({"career", "application", "counselor"}),
            handler=_plan_get,
        ),
        _read_definition(
            name="tasks.list",
            description="列出当前授权学生的求职任务",
            input_model=EmptyArguments,
            output_model=ItemsOutput,
            specialists=frozenset({"career", "application", "counselor"}),
            handler=_tasks_list,
        ),
        _read_definition(
            name="jobs.get",
            description="读取一个内部候选岗位",
            input_model=ResourceArguments,
            output_model=RecordOutput,
            specialists=frozenset({"job", "resume", "application", "interview"}),
            handler=_jobs_get,
        ),
        _read_definition(
            name="jobs.search_internal",
            description="按关键词搜索内部岗位库",
            input_model=InternalJobSearchArguments,
            output_model=ItemsOutput,
            specialists=frozenset({"career", "job", "resume", "application"}),
            handler=_jobs_search_internal,
        ),
        _read_definition(
            name="resumes.list",
            description="列出当前授权学生的简历文件",
            input_model=EmptyArguments,
            output_model=ItemsOutput,
            specialists=frozenset({"resume", "job", "interview", "counselor"}),
            handler=_resumes_list,
        ),
        _read_definition(
            name="resumes.get",
            description="读取当前授权学生的一份简历摘要",
            input_model=ResourceArguments,
            output_model=RecordOutput,
            specialists=frozenset({"resume", "job", "interview", "counselor"}),
            handler=_resumes_get,
        ),
        _read_definition(
            name="applications.list",
            description="列出当前授权学生的投递记录",
            input_model=EmptyArguments,
            output_model=ItemsOutput,
            specialists=frozenset({"application", "career", "counselor"}),
            handler=_applications_list,
        ),
        _read_definition(
            name="risks.list",
            description="列出授权范围内的开放风险事实",
            input_model=EmptyArguments,
            output_model=ItemsOutput,
            specialists=frozenset({"counselor", "career"}),
            handler=_risks_list,
        ),
        _read_definition(
            name="interventions.list",
            description="列出授权范围内的帮扶任务",
            input_model=EmptyArguments,
            output_model=ItemsOutput,
            specialists=frozenset({"counselor", "career"}),
            handler=_interventions_list,
        ),
        _read_definition(
            name="ai_task.get",
            description="查询当前授权用户的异步 AI 任务状态",
            input_model=ResourceArguments,
            output_model=RecordOutput,
            # Interview, job and intelligence agents do not own asynchronous
            # task resources. Keeping this out of their catalog prevents the
            # model from inventing placeholder task ids during normal answers.
            specialists=frozenset({"career", "resume", "application", "learning", "workplace", "employment"}),
            handler=_ai_task_get,
        ),
        _read_definition(
            name="dashboard.class_summary",
            description="读取辅导员授权班级的就业汇总",
            input_model=EmptyArguments,
            output_model=RecordOutput,
            specialists=frozenset({"counselor"}),
            roles=frozenset({UserRole.counselor, UserRole.admin}),
            handler=_class_summary,
        ),
        _read_definition(
            name="students.list_progress",
            description="列出辅导员授权班级学生的进展摘要",
            input_model=EmptyArguments,
            output_model=ItemsOutput,
            specialists=frozenset({"counselor"}),
            roles=frozenset({UserRole.counselor, UserRole.admin}),
            handler=_students_progress,
        ),
        _read_definition(
            name="jobs.search_public",
            description="搜索无需登录的公开网页岗位结果，不执行投递",
            input_model=PublicJobSearchArguments,
            output_model=ItemsOutput,
            specialists=frozenset({"career", "job", "resume", "application"}),
            handler=_public_job_search_handler(public_job_search),
        ),
    ]
    if settings.deployment_mode != "server-demo":
        definitions.append(
            _read_definition(
                name="knowledge.search",
                description="检索公共知识和当前授权学生的个人文档",
                input_model=KnowledgeSearchArguments,
                output_model=ItemsOutput,
                specialists=ALL_SPECIALISTS,
                handler=_knowledge_search_handler(embed_query or _default_embed_query),
            )
        )
    definitions.extend(
        [
            _write_definition(
                name="jobs.import_candidate",
                description="将已选择的公开岗位来源导入内部候选岗位库",
                input_model=PublicJobImportArguments,
                specialists=frozenset({"career", "job", "application"}),
                roles=ALL_ROLES,
                handler=_public_job_import,
            ),
            _write_definition(
                name="plan.create_draft",
                description="创建需要用户确认的求职计划草稿",
                input_model=PlanDraftArguments,
                specialists=frozenset({"career"}),
                roles=frozenset({UserRole.student}),
                handler=_plan_create_draft,
            ),
            _write_definition(
                name="task.update_status",
                description="更新当前授权学生的一项求职任务状态",
                input_model=TaskStatusArguments,
                specialists=frozenset({"career", "application"}),
                roles=frozenset({UserRole.student}),
                handler=_task_update_status,
                reversible=True,
                undo_handler=_undo_task_status,
            ),
            _write_definition(
                name="application.update_stage",
                description="按业务规则更新学生投递阶段",
                input_model=ApplicationStageArguments,
                specialists=frozenset({"application"}),
                roles=frozenset({UserRole.student}),
                handler=_application_update_stage,
                reversible=True,
                undo_handler=_undo_application_stage,
            ),
            _write_definition(
                name="resume.create_version_draft",
                description="创建需要学生确认的定向简历优化草稿",
                input_model=ResumeDraftArguments,
                specialists=frozenset({"resume"}),
                roles=frozenset({UserRole.student}),
                handler=_resume_create_draft,
            ),
            _write_definition(
                name="intervention.create",
                description="为当前授权学生创建辅导员帮扶任务",
                input_model=InterventionArguments,
                specialists=frozenset({"counselor"}),
                roles=frozenset({UserRole.counselor, UserRole.admin}),
                handler=_intervention_create,
            ),
            _write_definition(
                name="record.delete",
                description="删除业务记录，始终需要二次确认",
                input_model=DeleteArguments,
                specialists=ALL_SPECIALISTS,
                roles=ALL_ROLES,
                handler=_unsupported_high_risk,
                risk=ToolRisk.high_risk,
            ),
            _write_definition(
                name="records.bulk_update",
                description="批量修改业务记录，始终需要二次确认",
                input_model=BulkUpdateArguments,
                specialists=ALL_SPECIALISTS,
                roles=ALL_ROLES,
                handler=_unsupported_high_risk,
                risk=ToolRisk.high_risk,
            ),
            _write_definition(
                name="application.external_submit",
                description="代替学生提交外部求职申请，当前版本不执行",
                input_model=ExternalSubmitArguments,
                specialists=frozenset({"application"}),
                roles=frozenset({UserRole.student}),
                handler=_unsupported_high_risk,
                risk=ToolRisk.high_risk,
            ),
        ]
    )
    for definition in definitions:
        registry.register(definition)
    register_extended_tools(registry)
    return registry
