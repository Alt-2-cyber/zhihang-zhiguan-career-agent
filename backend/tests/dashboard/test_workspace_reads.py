from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.applications.models import Application
from app.auth.models import UserRole
from app.auth.service import create_user
from app.jobs.models import Job
from app.resumes.models import ResumeFile
from tests.conftest import login_headers


def test_student_workspace_read_endpoints_return_only_owned_records(
    client: TestClient, db_session: Session
) -> None:
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
    job = Job(
        title="数据分析师",
        company="示例科技",
        location="上海",
        description="负责业务数据分析",
    )
    db_session.add(job)
    db_session.flush()
    db_session.add_all(
        [
            Application(student_id=student.id, job_id=job.id, stage="applied"),
            Application(student_id=other.id, job_id=job.id, stage="offered"),
            ResumeFile(
                student_id=student.id,
                original_name="resume.pdf",
                stored_name="one.pdf",
                media_type="application/pdf",
                size_bytes=10,
                storage_path="uploads/one.pdf",
                parse_status="parsed",
                parsed_text="Python 数据分析",
            ),
        ]
    )
    db_session.commit()
    headers = login_headers(client, student.username, "Student123!")

    dashboard = client.get("/api/dashboard/student", headers=headers)
    jobs = client.get("/api/jobs", headers=headers)
    applications = client.get("/api/applications", headers=headers)
    resumes = client.get("/api/resumes", headers=headers)

    assert dashboard.status_code == 200
    assert dashboard.json()["application_count"] == 1
    assert jobs.json()[0]["title"] == "数据分析师"
    assert len(applications.json()) == 1
    assert applications.json()[0]["stage"] == "applied"
    assert len(resumes.json()) == 1
