from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.auth.models import UserRole
from app.auth.service import create_user


def test_login_returns_token_and_current_user(client: TestClient, db_session: Session) -> None:
    create_user(
        db_session,
        username="student1",
        password="Student123!",
        display_name="张同学",
        role=UserRole.student,
    )

    response = client.post(
        "/api/auth/login",
        json={"username": "student1", "password": "Student123!"},
    )

    assert response.status_code == 200
    token = response.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "student"
    assert me.json()["display_name"] == "张同学"


def test_login_rejects_wrong_password_and_writes_audit_log(
    client: TestClient, db_session: Session
) -> None:
    create_user(
        db_session,
        username="student1",
        password="Student123!",
        display_name="张同学",
        role=UserRole.student,
    )

    response = client.post(
        "/api/auth/login",
        json={"username": "student1", "password": "wrong-password"},
    )

    assert response.status_code == 401
    audit = db_session.scalar(select(AuditLog).where(AuditLog.action == "auth.login_failed"))
    assert audit is not None
    assert "wrong-password" not in (audit.details or "")
