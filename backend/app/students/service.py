import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.base import AgentGateway
from app.auth.models import User, UserRole
from app.core.errors import AppError
from app.students.models import ProfileAnalysisDraft, StudentProfile


def create_profile_analysis(
    db: Session,
    *,
    student: User,
    resume_text: str,
    preferences: dict[str, str],
    gateway: AgentGateway,
) -> ProfileAnalysisDraft:
    analysis = gateway.analyze_profile(resume_text, preferences)
    draft = ProfileAnalysisDraft(
        student_id=student.id,
        provider=analysis.provider,
        payload_json=analysis.model_dump_json(),
        status="pending",
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    return draft


def confirm_profile_analysis(
    db: Session, *, student: User, draft_id: str
) -> StudentProfile:
    draft = db.get(ProfileAnalysisDraft, draft_id)
    if draft is None or draft.student_id != student.id:
        raise AppError(404, "profile_analysis_not_found", "画像分析草稿不存在")
    if draft.status != "pending":
        raise AppError(409, "profile_analysis_already_confirmed", "画像分析已经确认")

    payload = json.loads(draft.payload_json)
    profile = db.scalar(
        select(StudentProfile).where(StudentProfile.student_id == student.id)
    )
    if profile is None:
        profile = StudentProfile(student_id=student.id, version=1)
        db.add(profile)
    else:
        profile.version += 1
    profile.summary = payload["summary"]
    profile.strengths_json = json.dumps(payload["strengths"], ensure_ascii=False)
    profile.gaps_json = json.dumps(payload["gaps"], ensure_ascii=False)
    profile.constraints_json = json.dumps(payload["constraints"], ensure_ascii=False)
    profile.status = "confirmed"
    draft.status = "confirmed"
    db.commit()
    db.refresh(profile)
    return profile


def get_student_profile(db: Session, student_id: str) -> StudentProfile:
    profile = db.scalar(
        select(StudentProfile).where(StudentProfile.student_id == student_id)
    )
    if profile is None:
        raise AppError(404, "profile_not_found", "学生尚未确认就业画像")
    return profile


def assert_counselor_can_access_student(
    db: Session, counselor: User, student_id: str
) -> User:
    student = db.get(User, student_id)
    if student is None or student.role != UserRole.student:
        raise AppError(404, "student_not_found", "学生不存在")
    if counselor.role != UserRole.admin and (
        not counselor.class_id or counselor.class_id != student.class_id
    ):
        raise AppError(403, "forbidden", "无权查看该学生")
    return student


def serialize_profile(profile: StudentProfile) -> dict[str, object]:
    return {
        "id": profile.id,
        "student_id": profile.student_id,
        "summary": profile.summary,
        "strengths": json.loads(profile.strengths_json),
        "gaps": json.loads(profile.gaps_json),
        "constraints": json.loads(profile.constraints_json),
        "status": profile.status,
        "version": profile.version,
    }

