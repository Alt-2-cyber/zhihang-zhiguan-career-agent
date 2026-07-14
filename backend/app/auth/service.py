from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.security import hash_password, verify_password


def create_user(
    db: Session,
    *,
    username: str,
    password: str,
    display_name: str,
    role: UserRole,
    class_id: str | None = None,
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        display_name=display_name,
        role=role,
        class_id=class_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        return None
    return user
