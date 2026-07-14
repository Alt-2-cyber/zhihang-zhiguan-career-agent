from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.models import User, UserRole
from app.auth.security import require_roles
from app.auth.service import create_user


def test_student_cannot_access_counselor_route(client: TestClient, db_session: Session) -> None:
    create_user(
        db_session,
        username="student1",
        password="Student123!",
        display_name="张同学",
        role=UserRole.student,
    )

    @client.app.get("/api/test/counselor")
    def counselor_only(
        _user: User = Depends(require_roles(UserRole.counselor)),
    ) -> dict[str, bool]:
        return {"allowed": True}

    login = client.post(
        "/api/auth/login",
        json={"username": "student1", "password": "Student123!"},
    )
    token = login.json()["access_token"]

    response = client.get("/api/test/counselor", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"
