from datetime import date

from app.agents.local import LocalAgentGateway


def test_local_gateway_is_deterministic_and_marks_provider() -> None:
    gateway = LocalAgentGateway(today=date(2026, 7, 14))
    profile = gateway.analyze_profile(
        resume_text="使用 Python 和 SQL 完成销售数据分析项目。",
        preferences={"city": "上海", "industry": "互联网"},
    )

    assert profile.provider == "local-demo"
    assert profile.strengths[0].evidence[0].source == "resume"
    assert profile == gateway.analyze_profile(
        resume_text="使用 Python 和 SQL 完成销售数据分析项目。",
        preferences={"city": "上海", "industry": "互联网"},
    )


def test_local_job_match_returns_five_dimensions() -> None:
    gateway = LocalAgentGateway(today=date(2026, 7, 14))
    result = gateway.match_job(
        profile_summary="掌握 Python、SQL，完成销售数据分析项目",
        job_description="数据分析师，要求 Python、SQL 和数据可视化能力",
    )

    assert len(result.dimensions) == 5
    assert result.recommendation in {"apply", "improve_then_apply", "not_recommended"}

