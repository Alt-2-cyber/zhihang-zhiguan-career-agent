from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.auth.models import User
from app.auth.schemas import LoginRequest, TokenResponse, UserRead
from app.auth.security import create_access_token, get_current_user
from app.auth.service import authenticate_user
from app.core.database import get_db
from app.core.errors import AppError


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        write_audit_log(
            db,
            action="auth.login_failed",
            details={"username": payload.username},
        )
        raise AppError(401, "invalid_credentials", "用户名或密码错误")

    write_audit_log(db, action="auth.login_succeeded", user_id=user.id)
    return TokenResponse(access_token=create_access_token(user))


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user

