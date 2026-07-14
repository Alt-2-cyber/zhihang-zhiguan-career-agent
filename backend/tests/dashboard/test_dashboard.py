import json

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.models import UserRole
from app.auth.service import create_user
from app.risks.models import RiskEvent
from tests.conftest import login_headers


def test_counselor_dashboard_contains_only_authorized_class(
    client: TestClient, db_session: Session
) -> None:
    counselor = create_user(
        db_session,
        username="counselor-a",
        password="Counselor123!",
        display_name="李老师",
        role=UserRole.counselor,
        class_id="class-a",
    )
    student_a = create_user(
        db_session,
        username="student-a",
        password="Student123!",
        display_name="张同学",
        role=UserRole.student,
        class_id="class-a",
    )
    student_b = create_user(
        db_session,
        username="student-b",
        password="Student123!",
        display_name="王同学",
        role=UserRole.student,
        class_id="class-b",
    )
    for student in (student_a, student_b):
        db_session.add(
            RiskEvent(
                student_id=student.id,
                rule_code="no_recent_application",
                level="intervention",
                facts_json=json.dumps({"days": 14}),
                status="open",
            )
        )
    db_session.commit()
    headers = login_headers(client, counselor.username, "Counselor123!")

    response = client.get("/api/dashboard/counselor", headers=headers)

    assert response.status_code == 200
    assert response.json()["student_count"] == 1
    assert response.json()["risk_count"] == 1
    assert response.json()["risks"][0]["student_id"] == student_a.id

