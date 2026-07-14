import json

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.agents.service import build_agent_gateway
from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.core.config import get_settings
from app.core.database import get_db
from app.students.schemas import (
    ProfileAnalysisCreate,
    ProfileAnalysisDraftRead,
    StudentProfileRead,
)
from app.students.service import (
    assert_counselor_can_access_student,
    confirm_profile_analysis,
    create_profile_analysis,
    get_student_profile,
    serialize_profile,
)


router = APIRouter(prefix="/students", tags=["students"])


@router.post(
    "/me/profile-analyses",
    response_model=ProfileAnalysisDraftRead,
    status_code=status.HTTP_201_CREATED,
)
def analyze_my_profile(
    payload: ProfileAnalysisCreate,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    gateway = build_agent_gateway(get_settings())
    draft = create_profile_analysis(
        db,
        student=current_user,
        resume_text=payload.resume_text,
        preferences=payload.preferences,
        gateway=gateway,
    )
    return {
        "id": draft.id,
        "provider": draft.provider,
        "status": draft.status,
        "analysis": json.loads(draft.payload_json),
    }


@router.post(
    "/me/profile-analyses/{draft_id}/confirm", response_model=StudentProfileRead
)
def confirm_my_profile(
    draft_id: str,
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    profile = confirm_profile_analysis(db, student=current_user, draft_id=draft_id)
    return serialize_profile(profile)


@router.get("/me/profile", response_model=StudentProfileRead)
def read_my_profile(
    current_user: User = Depends(require_roles(UserRole.student)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return serialize_profile(get_student_profile(db, current_user.id))


@router.get("/{student_id}/profile", response_model=StudentProfileRead)
def read_student_profile(
    student_id: str,
    current_user: User = Depends(require_roles(UserRole.counselor, UserRole.admin)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    assert_counselor_can_access_student(db, current_user, student_id)
    return serialize_profile(get_student_profile(db, student_id))

