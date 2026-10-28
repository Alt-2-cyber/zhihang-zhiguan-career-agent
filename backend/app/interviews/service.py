import json
from collections.abc import Sequence

from app.agents.contracts import InterviewQuestion
from app.assessments.rubric import (
    DIMENSION_LABELS,
    EMOTION_DIMENSION_LABEL,
    UNIFIED_RUBRIC_VERSION,
    aggregate_scores,
)
from app.interviews.models import InterviewSession, InterviewTurn

CORE_QUESTION_COUNT = 6
MAX_FOLLOW_UPS = 2
MAX_INTERVIEW_TURNS = CORE_QUESTION_COUNT + MAX_FOLLOW_UPS


def _has_chinese(value: str) -> bool:
    return any("\u3400" <= character <= "\u9fff" for character in value)


def _is_english_heavy(value: str) -> bool:
    """Treat an all-English or mostly-English model response as unsafe for this UI."""
    chinese_count = sum("\u3400" <= character <= "\u9fff" for character in value)
    latin_count = sum(character.isascii() and character.isalpha() for character in value)
    return chinese_count == 0 or latin_count > chinese_count


def _localized_role(role: str | None) -> str:
    value = str(role or "").strip()
    return value if _has_chinese(value) and not _is_english_heavy(value) else "目标岗位"


def _fallback_question(question_id: str, role: str | None) -> str:
    role_label = _localized_role(role)
    if question_id.startswith("follow-up"):
        return "这个判断如何验证？请说明你本人承担的具体工作、关键取舍和最终结果。"
    if question_id.endswith("-1"):
        return f"请用两分钟做自我介绍，并结合简历说明你为什么适合{role_label}岗位。"
    if question_id.endswith("-2"):
        return "请选择一个有代表性的项目，说明你的具体职责、关键行动和可量化结果。"
    if question_id.endswith("-4"):
        return "请描述一次复杂问题或突发事件，说明你如何定位原因、权衡方案并验证最终结果。"
    if question_id.endswith("-5"):
        return "请举例说明你如何处理与产品、设计或研发同事的分歧，并最终按时交付工作。"
    if question_id.endswith("-6"):
        return f"针对{role_label}岗位，你最需要提升哪项能力？未来三个月准备如何提升？"
    return "请结合一个真实经历，说明你在目标岗位中承担的职责、关键行动和实际结果。"


def normalize_interview_question(
    question: InterviewQuestion,
    *,
    role: str | None = None,
    fallback_question: str | None = None,
    fallback_competency: str = "综合表达与岗位匹配",
) -> InterviewQuestion:
    """Keep persisted and provider-generated interview prompts in simplified Chinese."""
    prompt = question.question.strip()
    competency = question.competency.strip()
    if _is_english_heavy(prompt):
        prompt = fallback_question or _fallback_question(question.question_id, role)
    if _is_english_heavy(competency):
        competency = fallback_competency
    return question.model_copy(update={"question": prompt, "competency": competency})


def build_question_plan(
    *, role: str, adaptive_question: InterviewQuestion
) -> list[InterviewQuestion]:
    system_provider = "system:structured-interview"
    adaptive = normalize_interview_question(
        adaptive_question,
        role=role,
        fallback_question="请结合简历和目标岗位，说明一个最能体现你专业能力的项目或任务，并说明你的职责、关键行动和实际结果。",
        fallback_competency="岗位专业能力与成果证据",
    )
    return [
        InterviewQuestion(
            provider=system_provider,
            question_id="core-1",
            question=f"请用两分钟做自我介绍，并结合简历说明你为什么适合{_localized_role(role)}岗位。",
            competency="自我介绍与求职动机",
        ),
        InterviewQuestion(
            provider=system_provider,
            question_id="core-2",
            question="请选择一个有代表性的项目，说明你的具体职责、关键行动和可量化结果。",
            competency="项目经历与成果证据",
        ),
        adaptive.model_copy(
            update={"question_id": "core-3", "competency": "岗位专业能力与成果证据"}
        ),
        InterviewQuestion(
            provider=system_provider,
            question_id="core-4",
            question="请描述一次复杂问题或突发事件，说明你如何定位原因、权衡方案并验证最终结果。",
            competency="问题分析与解决",
        ),
        InterviewQuestion(
            provider=system_provider,
            question_id="core-5",
            question="请举例说明你如何处理与产品、设计或研发同事的分歧，并最终按时交付工作。",
            competency="协作沟通与执行",
        ),
        InterviewQuestion(
            provider=system_provider,
            question_id="core-6",
            question=f"针对{_localized_role(role)}岗位，你最需要提升哪项能力？未来三个月准备如何提升？",
            competency="成长复盘与岗位规划",
        ),
    ]


def build_configured_question_plan(
    *,
    role: str,
    adaptive_question: InterviewQuestion,
    scenario_steps: list[dict[str, object]] | None = None,
    core_question_count: int = CORE_QUESTION_COUNT,
) -> list[InterviewQuestion]:
    """Build a persisted plan from an optional database scenario."""
    bounded_count = max(1, min(core_question_count, 12))
    default_plan = build_question_plan(role=role, adaptive_question=adaptive_question)
    if not scenario_steps:
        return default_plan[:bounded_count]
    configured: list[InterviewQuestion] = []
    for index, item in enumerate(scenario_steps[:bounded_count], start=1):
        prompt = str(item.get("question") or item.get("prompt") or "").strip()
        if not prompt:
            continue
        configured.append(
            normalize_interview_question(
                InterviewQuestion(
                    provider="system:scenario",
                    question_id=f"core-{index}",
                    question=prompt.replace("{role}", role),
                    competency=str(
                        item.get("competency") or item.get("skill") or "综合沟通"
                    ),
                ),
                role=role,
                fallback_competency="综合沟通与岗位匹配",
            )
        )
    if len(configured) < bounded_count:
        configured.extend(default_plan[len(configured) : bounded_count])
    return configured[:bounded_count]


def load_question_plan(
    session: InterviewSession, *, role: str | None = None
) -> list[InterviewQuestion]:
    return [
        normalize_interview_question(InterviewQuestion.model_validate(item), role=role)
        for item in json.loads(session.question_plan_json)
    ]


def serialize_progress(session: InterviewSession) -> dict[str, object]:
    core_total = (
        session.core_question_count or len(load_question_plan(session)) or CORE_QUESTION_COUNT
    )
    max_turns = core_total + session.max_follow_ups
    return {
        "core_current": min(session.current_core_index + 1, core_total),
        "core_total": core_total,
        "follow_ups_used": session.follow_up_count,
        "follow_ups_max": session.max_follow_ups,
        "turns_answered": session.total_turns,
        "max_turns": max_turns,
        "current_kind": session.current_question_kind if session.status == "active" else None,
    }


def build_final_report(turns: Sequence[InterviewTurn]) -> dict[str, object]:
    score_names = (
        "content_completeness",
        "job_relevance",
        "answer_structure",
        "evidence_quality",
    )
    evaluations = [json.loads(turn.evaluation_json) for turn in turns]
    averages = aggregate_scores(
        {
            name: round(sum(int(item.get(name, 0)) for item in evaluations) / len(evaluations))
            if evaluations
            else 0
            for name in score_names
        }
    )
    emotion_scores = [
        int(item["emotion_stability"])
        for item in evaluations
        if item.get("emotion_stability") is not None
    ]
    if emotion_scores:
        averages["emotion_stability"] = round(sum(emotion_scores) / len(emotion_scores))
    feedback: list[str] = []
    for evaluation in evaluations:
        for item in evaluation.get("feedback", []):
            if isinstance(item, str) and item not in feedback:
                feedback.append(item)
    labels = {**DIMENSION_LABELS, "emotion_stability": EMOTION_DIMENSION_LABEL}
    strengths = [labels[name] for name, score in averages.items() if score >= 80]
    improvements = [labels[name] for name, score in averages.items() if score < 80]
    return {
        "rubric_version": UNIFIED_RUBRIC_VERSION,
        "turns_answered": len(turns),
        "average_scores": averages,
        "strengths": strengths,
        "improvements": improvements,
        "feedback": feedback[:6],
    }
