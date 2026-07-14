from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.models import UserRole
from app.auth.service import create_user
from tests.conftest import login_headers


def test_intervention_requires_same_class_and_completes_with_feedback(
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
    other_counselor = create_user(
        db_session,
        username="counselor-b",
        password="Counselor123!",
        display_name="王老师",
        role=UserRole.counselor,
        class_id="class-b",
    )
    student = create_user(
        db_session,
        username="student-a",
        password="Student123!",
        display_name="张同学",
        role=UserRole.student,
        class_id="class-a",
    )
    counselor_headers = login_headers(client, counselor.username, "Counselor123!")
    other_headers = login_headers(client, other_counselor.username, "Counselor123!")
    student_headers = login_headers(client, student.username, "Student123!")

    denied = client.post(
        "/api/interventions",
        headers=other_headers,
        json={"student_id": student.id, "title": "完成岗位筛选", "description": "筛选 5 个岗位"},
    )
    created = client.post(
        "/api/interventions",
        headers=counselor_headers,
        json={"student_id": student.id, "title": "完成岗位筛选", "description": "筛选 5 个岗位"},
    )
    submitted = client.patch(
        f"/api/interventions/{created.json()['id']}/submit",
        headers=student_headers,
        json={"feedback": "已完成 5 个岗位筛选，并投递 2 个。"},
    )
    resolved = client.patch(
        f"/api/interventions/{created.json()['id']}/resolve",
        headers=counselor_headers,
    )

    assert denied.status_code == 403
    assert created.status_code == 201
    assert submitted.json()["status"] == "submitted"
    assert resolved.json()["status"] == "resolved"
    assert resolved.json()["feedback"].startswith("已完成")

