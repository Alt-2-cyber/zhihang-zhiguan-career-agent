import json

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.local import LocalAgentGateway
from app.auth.models import UserRole
from app.auth.service import create_user
from app.workplace.models import SimulationScenario, WorkplaceDeliverable
from tests.conftest import login_headers


def _scenario(db: Session, *, title: str = "第一周数据任务") -> SimulationScenario:
    item = SimulationScenario(
        title=title,
        category="workplace",
        difficulty="medium",
        description="验证入职后的任务工作台",
        competencies_json=json.dumps(["任务澄清", "风险识别"], ensure_ascii=False),
        steps_json="[]",
        rubric_json="[]",
        mode="workplace",
        stage_definition_json=json.dumps(
            [{"key": "brief", "title": "读取简报", "prompt": "读取工作简报"}],
            ensure_ascii=False,
        ),
        work_context_json=json.dumps(
            {
                "role": "数据分析师",
                "stage": "入职第一周",
                "objective": "提交销售趋势简报",
                "stakeholders": ["直属主管"],
                "deliverables": ["趋势简报"],
                "deadline": "周五 18:00",
                "acceptance_criteria": ["数据可追溯"],
                "constraints": ["先确认口径"],
                "workflow": ["clarify_questions", "action_plan"],
            },
            ensure_ascii=False,
        ),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def test_post_hire_workbench_persists_and_reviews_deliverables(
    client: TestClient, db_session: Session, monkeypatch
) -> None:
    student = create_user(
        db_session,
        username="workplace_student",
        password="Student123!",
        display_name="工作台学生",
        role=UserRole.student,
    )
    scenario = _scenario(db_session)
    monkeypatch.setattr("app.workplace.router.build_agent_gateway", lambda *args, **kwargs: LocalAgentGateway())
    headers = login_headers(client, student.username, "Student123!")

    listed = client.get("/api/workplace/scenarios?phase=post_hire", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["phase"] == "post_hire"
    assert listed.json()[0]["work_context"]["objective"]

    started = client.post(f"/api/workplace/scenarios/{scenario.id}/sessions", headers=headers)
    assert started.status_code == 201
    session_id = started.json()["id"]
    assert started.json()["deliverables"] == []

    generated = client.post(
        f"/api/workplace/sessions/{session_id}/workplace-assist",
        headers=headers,
        json={"action_type": "clarify_questions"},
    )
    assert generated.status_code == 200
    assert generated.json()["deliverable"]["status"] == "draft"
    assert "销售趋势简报" in generated.json()["deliverable"]["content"]

    submitted = client.post(
        f"/api/workplace/sessions/{session_id}/deliverables/submit",
        headers=headers,
        json={
            "action_type": "clarify_questions",
            "title": "任务澄清问题清单",
            "content": "目标是提交销售趋势简报。1. 与直属主管确认数据口径。2. 周五 18:00 前交付并按数据可追溯标准验收，同时记录风险。",
        },
    )
    assert submitted.status_code == 200
    assert submitted.json()["deliverable"]["status"] == "submitted"
    assert submitted.json()["deliverable"]["review"]["dimensions"]["objective_understanding"] >= 62

    completed = client.post(
        f"/api/workplace/sessions/{session_id}/controls",
        headers=headers,
        json={"action": "complete"},
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert completed.json()["report"]["mode"] == "workplace"

    stored = db_session.scalars(
        select(WorkplaceDeliverable).where(WorkplaceDeliverable.session_id == session_id)
    ).all()
    assert len(stored) == 1
    assert stored[0].status == "submitted"


def test_workplace_deliverables_are_isolated_between_students(
    client: TestClient, db_session: Session
) -> None:
    owner = create_user(
        db_session,
        username="workplace_owner",
        password="Student123!",
        display_name="任务所有者",
        role=UserRole.student,
    )
    other = create_user(
        db_session,
        username="workplace_other",
        password="Student123!",
        display_name="其他学生",
        role=UserRole.student,
    )
    scenario = _scenario(db_session, title="隔离任务")
    owner_headers = login_headers(client, owner.username, "Student123!")
    other_headers = login_headers(client, other.username, "Student123!")
    started = client.post(f"/api/workplace/scenarios/{scenario.id}/sessions", headers=owner_headers)
    session_id = started.json()["id"]

    response = client.get(
        f"/api/workplace/sessions/{session_id}/deliverables", headers=other_headers
    )
    assert response.status_code == 404
