from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import AppError

password_hash = PasswordHash.recommended()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    return password_hash.verify(password, encoded)


def create_access_token(user: User) -> str:
    settings = get_settings()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    return jwt.encode(
        {"sub": user.id, "role": user.role.value, "exp": expires_at},
        settings.secret_key,
        algorithm="HS256",
    )


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id = payload.get("sub")
    except InvalidTokenError as error:
        raise AppError(401, "invalid_token", "登录状态无效或已过期") from error

    if not isinstance(user_id, str):
        raise AppError(401, "invalid_token", "登录状态无效或已过期")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError(401, "invalid_token", "登录状态无效或已过期")
    return user


def require_roles(*roles: UserRole) -> Callable[..., User]:
    def dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise AppError(403, "forbidden", "当前账号无权执行此操作")
        return current_user

    return dependency
