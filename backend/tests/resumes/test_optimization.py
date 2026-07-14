from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.models import UserRole
from app.auth.service import create_user
from app.jobs.models import Job
from app.resumes.models import ResumeFile, ResumeVersion
from tests.conftest import login_headers


def test_resume_optimization_creates_version_only_after_confirmation(
    client: TestClient, db_session: Session
) -> None:
    student = create_user(
        db_session,
        username="student1",
        password="Student123!",
        display_name="张同学",
        role=UserRole.student,
    )
    resume = ResumeFile(
        student_id=student.id,
        original_name="resume.pdf",
        stored_name="safe.pdf",
        media_type="application/pdf",
        size_bytes=20,
        storage_path="uploads/safe.pdf",
        parse_status="parsed",
        parsed_text="使用 Python 完成销售数据分析项目",
    )
    job = Job(
        title="数据分析师",
        company="示例科技",
        location="上海",
        description="要求 Python、SQL，并能量化分析结果。",
    )
    db_session.add_all([resume, job])
    db_session.commit()
    headers = login_headers(client, student.username, "Student123!")

    draft = client.post(
        f"/api/resumes/{resume.id}/optimizations",
        headers=headers,
        json={"job_id": job.id},
    )

    assert draft.status_code == 201
    assert db_session.query(ResumeVersion).count() == 0
    suggestion = draft.json()["suggestions"][0]
    assert suggestion["original"] in resume.parsed_text
    assert suggestion["requires_confirmation"] is True

    confirmed = client.post(
        f"/api/resumes/optimizations/{draft.json()['id']}/confirm", headers=headers
    )
    assert confirmed.status_code == 200
    assert db_session.query(ResumeVersion).count() == 1
