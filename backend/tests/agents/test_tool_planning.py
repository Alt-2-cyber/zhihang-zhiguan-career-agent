from pydantic import ValidationError

from app.agents.conversation_contracts import (
    AgentStepPlan,
    ConversationMessage,
    ConversationPlan,
    PlanTurnRequest,
    SpecialistDecision,
    SpecialistRequest,
    ToolCatalogItem,
)
from app.agents.conversation_gateway import OpenAIConversationGateway
from app.tools.business import ResourceArguments, build_business_tool_registry


def test_resource_arguments_accept_common_id_aliases() -> None:
    assert ResourceArguments.model_validate({"id": "task-1"}).resource_id == "task-1"
    assert ResourceArguments.model_validate({"task_id": "task-2"}).resource_id == "task-2"
    assert ResourceArguments.model_validate({"resourceId": "task-3"}).resource_id == "task-3"


def test_resource_arguments_reject_placeholder_ids() -> None:
    for value in ("current", "placeholder", "职位名称对应的ID"):
        try:
            ResourceArguments.model_validate({"resource_id": value})
        except ValidationError:
            continue
        raise AssertionError(f"placeholder id was accepted: {value}")


def test_interview_catalog_does_not_expose_async_task_lookup() -> None:
    registry = build_business_tool_registry()
    names = {item["name"] for item in registry.catalog(specialist="interview", role="student")}
    assert "ai_task.get" not in names
    assert {"resumes.list", "knowledge.search"}.issubset(names)


def test_online_gateway_allows_empty_followup(monkeypatch) -> None:
    gateway = OpenAIConversationGateway(
        provider="test",
        base_url="http://example.invalid",
        api_key="test",
        model="test-model",
    )
    monkeypatch.setattr(
        gateway,
        "_invoke",
        lambda _operation, _request, _contract: SpecialistDecision(
            analysis="没有更多需要读取的资料",
            tool_requests=[{"name": "ai_task.get", "arguments": {}}],
        ),
    )
    request = SpecialistRequest(
        step=AgentStepPlan(
            id="interview",
            agent="interview",
            instruction="准备面试",
        ),
        messages=[ConversationMessage(role="user", content="准备面试")],
        tool_catalog=[
            ToolCatalogItem(
                name="resumes.list",
                description="读取简历",
                input_schema={"type": "object"},
            )
        ],
        tool_results=[{"tool_name": "resumes.list", "data": {"items": []}}],
    )
    assert gateway.decide_specialist(request).tool_requests == []


def test_online_gateway_constrains_interview_plan_to_relevant_agents(monkeypatch) -> None:
    gateway = OpenAIConversationGateway(
        provider="test",
        base_url="http://example.invalid",
        api_key="test",
        model="test-model",
    )
    monkeypatch.setattr(
        gateway,
        "_invoke",
        lambda _operation, _request, _contract: ConversationPlan(
            intent="broad",
            steps=[
                {"id": "job", "agent": "job", "instruction": "岗位"},
                {"id": "learning", "agent": "learning", "instruction": "学习"},
                {"id": "interview", "agent": "interview", "instruction": "面试"},
                {"id": "workplace", "agent": "workplace", "instruction": "职场"},
            ],
        ),
    )
    result = gateway.plan_turn(
        PlanTurnRequest(
            messages=[ConversationMessage(role="user", content="准备面试")],
            limits={"max_steps": 6, "max_tool_calls": 12},
        )
    )
    assert [step.agent for step in result.steps] == ["interview"]
