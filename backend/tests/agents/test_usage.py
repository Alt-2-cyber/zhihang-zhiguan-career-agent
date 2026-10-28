from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.agents.models import AgentModelCall
from app.auth.models import UserRole
from app.auth.service import create_user
from tests.conftest import login_headers


def test_counselor_can_read_real_model_usage_summary(client, db_session: Session) -> None:
    counselor = create_user(
        db_session,
        username="usage-counselor",
        password="Counselor123!",
        display_name="Usage Counselor",
        role=UserRole.counselor,
        class_id="class-usage",
    )
    now = datetime.now(timezone.utc)
    db_session.add(
        AgentModelCall(
            owner_id=counselor.id,
            operation="analyze_profile",
            provider="local-demo",
            model="local-demo",
            status="succeeded",
            started_at=now - timedelta(milliseconds=12),
            completed_at=now,
        )
    )
    db_session.commit()

    response = client.get(
        "/api/agents/usage?days=7",
        headers=login_headers(client, counselor.username, "Counselor123!"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["totals"]["calls"] == 1
    assert payload["totals"]["failures"] == 0
    assert payload["providers"][0]["name"] == "local-demo"
