import json
from datetime import datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.applications.models import Application
from app.audit.models import AuditLog
from app.auth.models import User, UserRole
from app.chat.models import ChatAttachment, ChatMessage, ChatSession
from app.chat.schemas import ChatContextRef, ChatSessionCreate, ChatSessionUpdate
from app.core.errors import AppError
from app.employment.models import EmploymentRecord
from app.growth.models import LearningTask
from app.interventions.models import Intervention
from app.jobs.models import Job
from app.plans.models import CareerPlanRecord, PlanTaskRecord
from app.resumes.models import ResumeFile
from app.students.models import StudentProfile
from app.students.service import assert_counselor_can_access_student
from app.workplace.models import SimulationSession


def resolve_subject_student_id(
    db: Session, user: User, requested_student_id: str | None
) -> str | None:
    if user.role == UserRole.student:
        if requested_student_id is not None and requested_student_id != user.id:
            raise AppError(403, "forbidden", "学生只能创建自己的就业助手会话")
        return user.id
    if requested_student_id is not None:
        assert_counselor_can_access_student(db, user, requested_student_id)
    return requested_student_id


def assert_session_access(db: Session, user: User, session_id: str) -> ChatSession:
    chat_session = db.get(ChatSession, session_id)
    if chat_session is None or chat_session.owner_id != user.id:
        raise AppError(404, "chat_session_not_found", "对话不存在")
    if user.role == UserRole.student:
        if chat_session.subject_student_id != user.id:
            raise AppError(404, "chat_session_not_found", "对话不存在")
    elif chat_session.subject_student_id is not None:
        assert_counselor_can_access_student(db, user, chat_session.subject_student_id)
    return chat_session


def assert_active_session(chat_session: ChatSession) -> None:
    if chat_session.status != "active":
        raise AppError(409, "chat_session_archived", "已归档对话不能继续执行操作")


def serialize_session(chat_session: ChatSession) -> dict[str, object]:
    return {
        "id": chat_session.id,
        "owner_id": chat_session.owner_id,
        "role": chat_session.role,
        "subject_student_id": chat_session.subject_student_id,
        "mode": chat_session.mode,
        "title": chat_session.title,
        "summary": chat_session.summary,
        "summary_source_message_ids": json.loads(chat_session.summary_source_ids_json),
        "status": chat_session.status,
        "created_at": chat_session.created_at,
        "updated_at": chat_session.updated_at,
    }


def serialize_message(message: ChatMessage) -> dict[str, object]:
    return {
        "id": message.id,
        "sender": message.sender,
        "content": message.content,
        "attachment_ids": json.loads(message.attachment_ids_json),
        "citations": json.loads(message.citations_json),
        "provider": message.provider,
        "created_at": message.created_at,
    }


def create_chat_session(db: Session, *, user: User, payload: ChatSessionCreate) -> ChatSession:
    subject_student_id = resolve_subject_student_id(db, user, payload.subject_student_id)
    chat_session = ChatSession(
        owner_id=user.id,
        role=user.role.value,
        subject_student_id=subject_student_id,
        mode=payload.mode,
        title=payload.title,
        status="active",
    )
    db.add(chat_session)
    db.commit()
    db.refresh(chat_session)
    return chat_session


def list_chat_sessions(
    db: Session,
    *,
    user: User,
    query: str | None,
    limit: int,
    cursor_updated_at: datetime | None,
    cursor_id: str | None,
) -> tuple[list[ChatSession], str | None]:
    statement = select(ChatSession).where(ChatSession.owner_id == user.id)
    if query:
        statement = statement.where(ChatSession.title.ilike(f"%{query.strip()}%"))
    if cursor_updated_at is not None and cursor_id is not None:
        statement = statement.where(
            or_(
                ChatSession.updated_at < cursor_updated_at,
                and_(
                    ChatSession.updated_at == cursor_updated_at,
                    ChatSession.id < cursor_id,
                ),
            )
        )
    items = db.scalars(
        statement.order_by(ChatSession.updated_at.desc(), ChatSession.id.desc()).limit(limit + 1)
    ).all()
    page = list(items[:limit])
    next_cursor = None
    if len(items) > limit and page:
        last = page[-1]
        next_cursor = f"{last.updated_at.isoformat()}|{last.id}"
    return page, next_cursor


def update_chat_session(
    db: Session,
    *,
    user: User,
    chat_session: ChatSession,
    payload: ChatSessionUpdate,
) -> ChatSession:
    changes = payload.model_dump(exclude_unset=True)
    if "title" in changes:
        chat_session.title = changes["title"]
    if "mode" in changes and changes["mode"] != chat_session.mode:
        previous = chat_session.mode
        chat_session.mode = changes["mode"]
        db.add(
            AuditLog(
                user_id=user.id,
                action="chat.permission_mode_changed",
                resource_type="chat_session",
                resource_id=chat_session.id,
                details=json.dumps({"from": previous, "to": chat_session.mode}, ensure_ascii=False),
            )
        )
    if "status" in changes and changes["status"] != chat_session.status:
        chat_session.status = changes["status"]
        db.add(
            AuditLog(
                user_id=user.id,
                action=(
                    "chat.session_archived"
                    if chat_session.status == "archived"
                    else "chat.session_reopened"
                ),
                resource_type="chat_session",
                resource_id=chat_session.id,
                details=json.dumps({"status": chat_session.status}, ensure_ascii=False),
            )
        )
    db.commit()
    db.refresh(chat_session)
    return chat_session


def validate_context_refs(
    db: Session,
    *,
    user: User,
    chat_session: ChatSession,
    refs: list[ChatContextRef],
) -> None:
    subject_id = chat_session.subject_student_id
    for ref in refs:
        if ref.type == "job":
            if db.get(Job, ref.id) is None:
                raise AppError(404, "context_not_found", "岗位上下文不存在")
            continue
        if ref.type in {"job_intelligence", "quality_feedback"}:
            if ref.id != "overview":
                raise AppError(404, "context_not_found", "业务上下文不存在")
            continue
        if ref.type == "student":
            if user.role == UserRole.student:
                if ref.id != user.id:
                    raise AppError(403, "forbidden", "学生不能引用其他学生")
            else:
                assert_counselor_can_access_student(db, user, ref.id)
            if subject_id is not None and ref.id != subject_id:
                raise AppError(409, "context_subject_mismatch", "上下文学生与会话范围不一致")
            continue
        if subject_id is None:
            raise AppError(409, "context_requires_student", "该上下文需要明确学生范围")
        model_and_owner = {
            "profile": (StudentProfile, "student_id"),
            "plan": (CareerPlanRecord, "student_id"),
            "task": (PlanTaskRecord, "student_id"),
            "resume": (ResumeFile, "student_id"),
            "application": (Application, "student_id"),
            "intervention": (Intervention, "student_id"),
            "learning_task": (LearningTask, "student_id"),
            "simulation_session": (SimulationSession, "student_id"),
            "workplace_session": (SimulationSession, "student_id"),
            "employment": (EmploymentRecord, "student_id"),
            "employment_record": (EmploymentRecord, "student_id"),
        }
        model, owner_field = model_and_owner[ref.type]
        resource = db.get(model, ref.id)
        if resource is None or getattr(resource, owner_field) != subject_id:
            raise AppError(404, "context_not_found", "业务上下文不存在")


def validate_message_attachments(
    db: Session,
    *,
    user: User,
    chat_session: ChatSession,
    attachment_ids: list[str],
) -> None:
    for attachment_id in attachment_ids:
        attachment = db.get(ChatAttachment, attachment_id)
        if (
            attachment is None
            or attachment.owner_id != user.id
            or attachment.session_id != chat_session.id
        ):
            raise AppError(404, "chat_attachment_not_found", "对话附件不存在")
        if attachment.parse_status != "ready":
            raise AppError(409, "chat_attachment_not_ready", "对话附件尚未解析完成")
