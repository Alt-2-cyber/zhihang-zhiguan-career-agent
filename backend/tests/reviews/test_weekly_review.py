from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.applications.models import Application, ApplicationEvent
from app.auth.models import UserRole
from app.auth.service import create_user
from app.jobs.models import Job
from tests.conftest import login_headers


def test_weekly_review_calculates_pipeline_and_limits_actions(
    client: TestClient, db_session: Session
) -> None:
    student = create_user(
        db_session,
        username="student1",
        password="Student123!",
        display_name="张同学",
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
    application = Application(student_id=student.id, job_id=job.id, stage="interview")
    db_session.add(application)
    db_session.flush()
    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            ApplicationEvent(
                application_id=application.id,
                student_id=student.id,
                from_stage=None,
                to_stage="saved",
                occurred_at=now,
            ),
            ApplicationEvent(
                application_id=application.id,
                student_id=student.id,
                from_stage="saved",
                to_stage="applied",
                occurred_at=now,
            ),
            ApplicationEvent(
                application_id=application.id,
                student_id=student.id,
                from_stage="assessment",
                to_stage="interview",
                occurred_at=now,
            ),
        ]
    )
    db_session.commit()
    headers = login_headers(client, student.username, "Student123!")

    response = client.post("/api/reviews/weekly", headers=headers)

    assert response.status_code == 201
    assert response.json()["metrics"]["applications"] == 1
    assert response.json()["metrics"]["interviews"] == 1
    assert len(response.json()["actions"]) <= 3
    assert response.json()["status"] == "pending_confirmation"
