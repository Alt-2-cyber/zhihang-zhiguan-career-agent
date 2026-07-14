from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.models import UserRole
from app.auth.service import create_user
from app.students.models import StudentProfile
from tests.conftest import login_headers


def test_ai_profile_does_not_become_official_until_student_confirms(
    client: TestClient, db_session: Session
) -> None:
    student = create_user(
        db_session,
        username="student1",
        password="Student123!",
        display_name="张同学",
        role=UserRole.student,
        class_id="class-a",
    )
    headers = login_headers(client, "student1", "Student123!")

    draft = client.post(
        "/api/students/me/profile-analyses",
        headers=headers,
        json={
            "resume_text": "使用 Python 和 SQL 完成销售数据分析项目。",
            "preferences": {"city": "上海", "industry": "互联网"},
        },
    )

    assert draft.status_code == 201
    assert (
        db_session.scalar(select(StudentProfile).where(StudentProfile.student_id == student.id))
        is None
    )

    confirmed = client.post(
        f"/api/students/me/profile-analyses/{draft.json()['id']}/confirm",
        headers=headers,
    )
    assert confirmed.status_code == 200
    profile = client.get("/api/students/me/profile", headers=headers)
    assert profile.status_code == 200
    assert profile.json()["status"] == "confirmed"
    assert profile.json()["strengths"][0]["evidence"][0]["source"] == "resume"


def test_counselor_can_read_only_students_in_same_class(
    client: TestClient, db_session: Session
) -> None:
    counselor = create_user(
        db_session,
        username="counselor1",
        password="Counselor123!",
        display_name="李老师",
        role=UserRole.counselor,
        class_id="class-a",
    )
    same_class_student = create_user(
        db_session,
        username="student-a",
        password="Student123!",
        display_name="同班学生",
        role=UserRole.student,
        class_id="class-a",
    )
    other_student = create_user(
        db_session,
        username="student-b",
        password="Student123!",
        display_name="其他班学生",
        role=UserRole.student,
        class_id="class-b",
    )
    profile = StudentProfile(
        student_id=same_class_student.id,
        summary="数据分析方向",
        strengths_json="[]",
        gaps_json="[]",
        constraints_json="[]",
        status="confirmed",
        version=1,
    )
    db_session.add(profile)
    db_session.commit()
    headers = login_headers(client, counselor.username, "Counselor123!")

    allowed = client.get(f"/api/students/{same_class_student.id}/profile", headers=headers)
    denied = client.get(f"/api/students/{other_student.id}/profile", headers=headers)

    assert allowed.status_code == 200
    assert denied.status_code == 403
