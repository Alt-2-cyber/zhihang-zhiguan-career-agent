import json

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.service import build_agent_gateway
from app.auth.models import User, UserRole
from app.auth.security import get_current_user, require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError
from app.jobs.models import Job, JobMatchRecord
from app.students.service import get_student_profile

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
def list_jobs(
    _current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict[str, object]]:
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    return [
        {
            "id": item.id,
            "title": item.title,
            "company": item.company,
            "location": item.location,
            "description": item.description,
        }
        for item in jobs
    ]


class JobMatchRead(BaseModel):
    id: str
    job_id: str
    provider: str
    recommendation: str
    overall_score: int
    dimensions: list[dict[str, object]]
    gaps: list[str]
    actions: list[str]


@router.post("/{job_id}/match", response_model=JobMatchRead, status_code=status.HTTP_201_CREATED)
def match_job(
    job_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    job = db.get(Job, job_id)
    if job is None:
        raise AppError(404, "job_not_found", "岗位不存在")
    profile = get_student_profile(db, current_user.id)
    result = build_agent_gateway(get_settings(), db=db, owner_id=current_user.id).match_job(
        profile.summary, job.description
    )
    record = JobMatchRecord(
        student_id=current_user.id,
        job_id=job.id,
        provider=result.provider,
        recommendation=result.recommendation,
        overall_score=result.overall_score,
        dimensions_json=json.dumps(
            [item.model_dump(mode="json") for item in result.dimensions], ensure_ascii=False
        ),
        gaps_json=json.dumps(result.gaps, ensure_ascii=False),
        actions_json=json.dumps(result.actions, ensure_ascii=False),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return {
        "id": record.id,
        "job_id": record.job_id,
        "provider": record.provider,
        "recommendation": record.recommendation,
        "overall_score": record.overall_score,
        "dimensions": json.loads(record.dimensions_json),
        "gaps": json.loads(record.gaps_json),
        "actions": json.loads(record.actions_json),
    }
