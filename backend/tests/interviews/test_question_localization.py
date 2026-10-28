from app.agents.contracts import InterviewQuestion
from app.interviews.service import (
    build_configured_question_plan,
    build_question_plan,
    normalize_interview_question,
)


def test_provider_question_is_localized_before_persisting() -> None:
    adaptive = InterviewQuestion(
        provider="online",
        question_id="q1",
        question="Please explain the most difficult project you have delivered.",
        competency="Role-specific professional ability",
    )

    plan = build_question_plan(role="数据分析师", adaptive_question=adaptive)

    assert all(any("\u3400" <= character <= "\u9fff" for character in item.question) for item in plan)
    assert all(any("\u3400" <= character <= "\u9fff" for character in item.competency) for item in plan)
    assert plan[2].question.startswith("请结合简历和目标岗位")


def test_english_scenario_prompt_gets_a_chinese_fallback() -> None:
    adaptive = InterviewQuestion(
        provider="local-demo",
        question_id="q1",
        question="请结合一个真实项目说明你的专业能力。",
        competency="专业能力",
    )

    plan = build_configured_question_plan(
        role="数据分析师",
        adaptive_question=adaptive,
        scenario_steps=[{"question": "Tell me about a conflict at work.", "competency": "Collaboration"}],
        core_question_count=1,
    )

    assert plan[0].question.startswith("请用两分钟做自我介绍")
    assert plan[0].competency == "综合沟通与岗位匹配"


def test_legacy_question_can_be_safely_rendered_in_chinese() -> None:
    normalized = normalize_interview_question(
        InterviewQuestion(
            provider="legacy",
            question_id="core-4",
            question="Describe a complex problem and how you resolved it.",
            competency="Problem analysis and resolution",
        ),
        role="数据分析师",
    )

    assert normalized.question.startswith("请描述一次复杂问题")
    assert normalized.competency == "综合表达与岗位匹配"
