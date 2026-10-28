import pytest
from conftest import login_headers
from sqlalchemy import create_engine, inspect

from alembic import command
from alembic.config import Config
from app.ai.models import AITaskType
from app.ai.service import ensure_task_available
from app.core.config import Settings
from app.core.errors import AppError
from app.core.seed import seed_demo_data


@pytest.mark.parametrize(
    ("task_type", "capability"),
    [
        (AITaskType.resume_ocr, "OCR"),
        (AITaskType.document_embedding, "BGE-M3"),
        (AITaskType.speech_transcription, "ASR"),
        (AITaskType.speech_synthesis, "TTS"),
        (AITaskType.chat_attachment_parse, "OCR"),
        (AITaskType.chat_attachment_embedding, "BGE-M3"),
        (AITaskType.chat_transcription, "ASR"),
        (AITaskType.chat_synthesis, "TTS"),
    ],
)
def test_server_demo_rejects_unavailable_local_ai_tasks(task_type, capability):
    settings = Settings(deployment_mode="server-demo")

    with pytest.raises(AppError) as error:
        ensure_task_available(task_type, settings=settings)

    assert error.value.status_code == 503
    assert error.value.code == "capability_unavailable"
    assert capability in error.value.message


@pytest.mark.parametrize(
    "task_type",
    [AITaskType.chat_agent_run, AITaskType.profile_analysis],
)
def test_server_demo_keeps_online_agent_tasks_available(task_type):
    settings = Settings(deployment_mode="server-demo")

    ensure_task_available(task_type, settings=settings)


@pytest.mark.parametrize(
    "task_type",
    [AITaskType.resume_ocr, AITaskType.document_embedding, AITaskType.speech_transcription],
)
def test_full_deployment_keeps_local_ai_tasks_available(task_type):
    settings = Settings(deployment_mode="full")

    ensure_task_available(task_type, settings=settings)


def test_server_demo_does_not_advertise_vector_search_tool(monkeypatch):
    import app.tools.business as business_tools

    settings = Settings(deployment_mode="server-demo")
    monkeypatch.setattr(business_tools, "get_settings", lambda: settings)

    registry = business_tools.build_business_tool_registry()
    names = {
        item["name"]
        for item in registry.catalog(specialist="career", role="student")
    }

    assert "knowledge.search" not in names
    assert "profile.get" in names
    assert "plan.get" in names


def test_ai_capabilities_report_server_demo_limits(client, db_session, monkeypatch):
    import app.ai.router as ai_router

    settings = Settings(
        deployment_mode="server-demo",
        agent_provider="failover",
        agent_provider_order="deepseek",
        deepseek_api_key="configured-for-test",
        agent_allow_local_fallback=False,
    )
    monkeypatch.setattr(ai_router, "get_settings", lambda: settings)
    monkeypatch.setattr(ai_router, "_service_readiness", lambda _url: False)
    seed_demo_data(db_session, student_password="Student123!", counselor_password="Counselor123!")
    db_session.commit()

    response = client.get(
        "/api/ai/capabilities",
        headers=login_headers(client, "student_demo", "Student123!"),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["deployment_mode"] == "server-demo"
    assert payload["agent"]["strict_online"] is True
    assert payload["services"]["embedding"]["ready"] is False
    assert payload["services"]["ocr"]["ready"] is False
    assert payload["services"]["speech"]["ready"] is False
    assert payload["services"]["emotion"]["ready"] is False
    assert payload["features"]["online_agent"] is True
    assert payload["features"]["camera_emotion"] is False


def test_empty_database_migrations_create_workplace_schema(tmp_path, monkeypatch):
    from app.core.config import get_settings
    from app.core.model_registry import load_all_models
    from app.core.models import Base

    database_url = f"sqlite:///{(tmp_path / 'migration.db').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        get_settings.cache_clear()

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        load_all_models()
        missing_tables = set(Base.metadata.tables) - tables
        missing_columns = {
            table_name: sorted(
                set(table.columns.keys())
                - {column["name"] for column in inspector.get_columns(table_name)}
            )
            for table_name, table in Base.metadata.tables.items()
            if table_name in tables
            and set(table.columns.keys())
            != {column["name"] for column in inspector.get_columns(table_name)}
        }
    finally:
        engine.dispose()

    assert not missing_tables, f"migrations omitted tables: {sorted(missing_tables)}"
    assert not missing_columns, f"migrations omitted columns: {missing_columns}"
    assert {
        "simulation_scenarios",
        "simulation_sessions",
        "simulation_turns",
        "simulation_material_bindings",
        "simulation_messages",
        "workplace_deliverables",
    }.issubset(tables)
