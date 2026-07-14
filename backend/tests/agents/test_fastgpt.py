import json

import httpx
import pytest

from app.agents.fastgpt import AgentOutputError, FastGPTAgentGateway


def test_fastgpt_gateway_implements_complete_agent_protocol() -> None:
    gateway = FastGPTAgentGateway(
        base_url="https://fastgpt.example/api",
        api_key="secret",
        app_id="career-agent",
        client=httpx.Client(transport=httpx.MockTransport(lambda _request: httpx.Response(500))),
    )

    for method_name in (
        "analyze_profile",
        "build_plan",
        "match_job",
        "optimize_resume",
        "start_interview",
        "evaluate_answer",
        "build_weekly_review",
    ):
        assert callable(getattr(gateway, method_name, None)), method_name


def test_fastgpt_adapter_validates_profile_response() -> None:
    profile = {
        "provider": "sf-fastgpt",
        "summary": "具备数据分析基础",
        "strengths": [
            {
                "name": "Python",
                "level": "熟练",
                "evidence": [{"source": "resume", "quote": "使用 Python 分析数据"}],
            }
        ],
        "gaps": ["缺少行业经验"],
        "constraints": ["目标城市为上海"],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer secret"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(profile, ensure_ascii=False)}}]},
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    gateway = FastGPTAgentGateway(
        base_url="https://fastgpt.example/api",
        api_key="secret",
        app_id="career-agent",
        client=client,
    )

    result = gateway.analyze_profile("使用 Python 分析数据", {"city": "上海"})

    assert result.summary == "具备数据分析基础"


def test_fastgpt_adapter_rejects_non_json_output() -> None:
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                200, json={"choices": [{"message": {"content": "not-json"}}]}
            )
        )
    )
    gateway = FastGPTAgentGateway(
        base_url="https://fastgpt.example/api",
        api_key="secret",
        app_id="career-agent",
        client=client,
    )

    with pytest.raises(AgentOutputError, match="结构化输出"):
        gateway.analyze_profile("resume", {})
