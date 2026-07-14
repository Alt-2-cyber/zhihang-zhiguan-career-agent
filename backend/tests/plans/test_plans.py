import json
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.models import UserRole
from app.auth.service import create_user
from app.students.models import StudentProfile
from tests.conftest import login_headers


def test_generated_plan_has_one_primary_role_and_four_week_tasks(
    client: TestClient, db_session: Session
) -> None:
    student = create_user(
        db_session,
        username="student1",
        password="Student123!",
        display_name="张同学",
        role=UserRole.student,
    )
    db_session.add(
        StudentProfile(
            student_id=student.id,
            summary="掌握 Python 和 SQL，有数据分析项目经验",
            strengths_json=json.dumps([]),
            gaps_json=json.dumps([]),
            constraints_json=json.dumps([]),
            status="confirmed",
            version=1,
        )
    )
    db_session.commit()
    headers = login_headers(client, student.username, "Student123!")

    response = client.post(
        "/api/plans/generate",
        headers=headers,
        json={"target_role": "数据分析师"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["primary_role"] == "数据分析师"
    assert len(payload["backup_roles"]) <= 2
    assert {task["week"] for task in payload["tasks"]} == {1, 2, 3, 4}
    assert all(date.fromisoformat(task["due_date"]) >= date.today() for task in payload["tasks"])
    assert payload["status"] == "pending_confirmation"


def test_plan_requires_owner_confirmation(client: TestClient, db_session: Session) -> None:
    student = create_user(
        db_session,
        username="student1",
        password="Student123!",
        display_name="张同学",
        role=UserRole.student,
    )
    other = create_user(
        db_session,
        username="student2",
        password="Student123!",
        display_name="王同学",
        role=UserRole.student,
    )
    for user in (student, other):
        db_session.add(
            StudentProfile(
                student_id=user.id,
                summary="数据分析方向",
                strengths_json="[]",
                gaps_json="[]",
                constraints_json="[]",
                status="confirmed",
                version=1,
            )
        )
    db_session.commit()
    first_headers = login_headers(client, student.username, "Student123!")
    other_headers = login_headers(client, other.username, "Student123!")
    generated = client.post(
        "/api/plans/generate", headers=first_headers, json={"target_role": None}
    )

    denied = client.post(f"/api/plans/{generated.json()['id']}/confirm", headers=other_headers)
    confirmed = client.post(f"/api/plans/{generated.json()['id']}/confirm", headers=first_headers)

    assert denied.status_code == 404
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "active"
