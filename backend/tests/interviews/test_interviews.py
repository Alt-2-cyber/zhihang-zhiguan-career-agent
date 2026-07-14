from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth.models import UserRole
from app.auth.service import create_user
from app.jobs.models import Job
from app.resumes.models import ResumeFile
from tests.conftest import login_headers


def test_interview_question_and_evaluation_use_only_allowed_scores(
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
        description="要求 Python、SQL 和业务分析能力",
    )
    db_session.add_all([resume, job])
    db_session.commit()
    headers = login_headers(client, student.username, "Student123!")

    started = client.post(
        "/api/interviews",
        headers=headers,
        json={"resume_id": resume.id, "job_id": job.id},
    )
    answered = client.post(
        f"/api/interviews/{started.json()['id']}/answers",
        headers=headers,
        json={"answer": "我负责清洗 10 万条销售数据并定位转化问题。"},
    )

    assert started.status_code == 201
    assert answered.status_code == 200
    evaluation = answered.json()["evaluation"]
    assert set(evaluation) >= {
        "content_completeness",
        "job_relevance",
        "answer_structure",
        "evidence_quality",
    }
    assert not ({"appearance", "gender", "accent"} & set(evaluation))
    assert answered.json()["follow_up"]["question_id"] == "q2"

