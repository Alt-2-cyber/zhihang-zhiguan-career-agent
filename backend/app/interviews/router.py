import json

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.agents.service import build_agent_gateway
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.interviews.models import InterviewSession, InterviewTurn
from app.jobs.models import Job
from app.resumes.models import ResumeFile

router = APIRouter(prefix="/interviews", tags=["interviews"])


class InterviewStartRequest(BaseModel):
    resume_id: str
    job_id: str


class InterviewAnswerRequest(BaseModel):
    answer: str = Field(min_length=1, max_length=10_000)


@router.post("", status_code=status.HTTP_201_CREATED)
def start_interview(
    payload: InterviewStartRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    resume = db.get(ResumeFile, payload.resume_id)
    job = db.get(Job, payload.job_id)
    if resume is None or resume.student_id != current_user.id:
        raise AppError(404, "resume_not_found", "简历不存在")
    if job is None:
        raise AppError(404, "job_not_found", "岗位不存在")
    if not resume.parsed_text:
        raise AppError(409, "resume_not_parsed", "简历尚未成功解析")
    gateway = build_agent_gateway(get_settings())
    question = gateway.start_interview(resume.parsed_text, job.description)
    session = InterviewSession(
        student_id=current_user.id,
        resume_id=resume.id,
        job_id=job.id,
        provider=getattr(gateway, "provider", get_settings().agent_provider),
        current_question_json=question.model_dump_json(),
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return {
        "id": session.id,
        "status": session.status,
        "question": question.model_dump(mode="json"),
    }


@router.post("/{session_id}/answers")
def answer_interview_question(
    session_id: str,
    payload: InterviewAnswerRequest,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    session = db.get(InterviewSession, session_id)
    if session is None or session.student_id != current_user.id:
        raise AppError(404, "interview_not_found", "模拟面试不存在")
    job = db.get(Job, session.job_id)
    question = json.loads(session.current_question_json)
    evaluation = build_agent_gateway(get_settings()).evaluate_answer(
        question["question"], payload.answer, job.description
    )
    sequence = db.scalar(
        select(func.count())
        .select_from(InterviewTurn)
        .where(InterviewTurn.session_id == session.id)
    )
    db.add(
        InterviewTurn(
            session_id=session.id,
            student_id=current_user.id,
            sequence=int(sequence or 0) + 1,
            question=question["question"],
            answer=payload.answer,
            evaluation_json=evaluation.model_dump_json(),
        )
    )
    if evaluation.follow_up:
        session.current_question_json = evaluation.follow_up.model_dump_json()
    else:
        session.status = "completed"
    db.commit()
    payload_data = evaluation.model_dump(mode="json")
    follow_up = payload_data.pop("follow_up")
    payload_data.pop("provider", None)
    return {"evaluation": payload_data, "follow_up": follow_up, "status": session.status}
