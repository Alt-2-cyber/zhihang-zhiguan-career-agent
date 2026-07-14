from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.models import UserRole
from app.auth.service import create_user
from app.jobs.models import Job
from app.students.models import StudentProfile
from tests.conftest import login_headers


def test_job_match_persists_evidence_for_all_dimensions(
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
            summary="掌握 Python、SQL，有销售数据分析项目经验",
            strengths_json="[]",
            gaps_json="[]",
            constraints_json="[]",
            status="confirmed",
            version=1,
        )
    )
    job = Job(
        title="数据分析师",
        company="示例科技",
        location="上海",
        description="要求 Python、SQL、可视化能力，负责业务数据分析。",
    )
    db_session.add(job)
    db_session.commit()
    headers = login_headers(client, student.username, "Student123!")

    response = client.post(f"/api/jobs/{job.id}/match", headers=headers)

    assert response.status_code == 201
    assert len(response.json()["dimensions"]) == 5
    assert all(item["evidence"] for item in response.json()["dimensions"])
