from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.applications.models import ApplicationEvent
from app.auth.models import UserRole
from app.auth.service import create_user
from app.jobs.models import Job
from tests.conftest import login_headers


def test_application_stage_transition_persists_history_and_rejects_regression(
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
    db_session.commit()
    headers = login_headers(client, student.username, "Student123!")

    created = client.post(
        "/api/applications", headers=headers, json={"job_id": job.id}
    )
    applied = client.patch(
        f"/api/applications/{created.json()['id']}/stage",
        headers=headers,
        json={"stage": "applied"},
    )
    regression = client.patch(
        f"/api/applications/{created.json()['id']}/stage",
        headers=headers,
        json={"stage": "saved"},
    )

    assert created.status_code == 201
    assert applied.status_code == 200
    assert regression.status_code == 409
    events = (
        db_session.query(ApplicationEvent)
        .filter(ApplicationEvent.application_id == created.json()["id"])
        .all()
    )
    assert [event.to_stage for event in events] == ["saved", "applied"]

