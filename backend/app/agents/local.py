from datetime import date, timedelta

from app.agents.contracts import (
    CapabilityTag,
    CareerPlan,
    DimensionScore,
    Evidence,
    InterviewEvaluation,
    InterviewQuestion,
    JobMatch,
    MatchDimension,
    PlanTask,
    ProfileAnalysis,
    ResumeOptimization,
    ResumeSuggestion,
    WeeklyMetrics,
    WeeklyReview,
)


class LocalAgentGateway:
    """Deterministic provider for development, tests, and offline demonstrations."""

    provider = "local-demo"

    def __init__(self, today: date | None = None) -> None:
        self.today = today or date.today()

    def analyze_profile(self, resume_text: str, preferences: dict[str, str]) -> ProfileAnalysis:
        skill = "Python / SQL" if "Python" in resume_text or "SQL" in resume_text else "项目实践"
        quote = self._quote(resume_text)
        constraints = [f"目标{key}：{value}" for key, value in sorted(preferences.items())]
        return ProfileAnalysis(
            provider=self.provider,
            summary="具备数据分析基础，建议以可量化项目成果强化岗位竞争力。",
            strengths=[
                CapabilityTag(
                    name=skill,
                    level="具备实践基础",
                    evidence=[Evidence(source="resume", quote=quote)],
                )
            ],
            gaps=["项目成果缺少业务指标或量化结果"],
            constraints=constraints,
        )

    def build_plan(self, profile_summary: str, target_role: str | None = None) -> CareerPlan:
        role = target_role or "数据分析师"
        tasks = [
            PlanTask(
                title="完善目标岗位简历",
                week=1,
                due_date=self.today + timedelta(days=6),
                acceptance_criteria="完成一版针对目标岗位且不虚构经历的简历",
            ),
            PlanTask(
                title="筛选并投递匹配岗位",
                week=2,
                due_date=self.today + timedelta(days=13),
                acceptance_criteria="完成至少 5 个有匹配依据的岗位投递",
            ),
            PlanTask(
                title="完成模拟面试训练",
                week=3,
                due_date=self.today + timedelta(days=20),
                acceptance_criteria="完成一次模拟面试并根据反馈重答薄弱问题",
            ),
            PlanTask(
                title="复盘求职漏斗",
                week=4,
                due_date=self.today + timedelta(days=27),
                acceptance_criteria="根据投递结果确认下一周期最多三项改进动作",
            ),
        ]
        return CareerPlan(
            provider=self.provider,
            primary_role=role,
            backup_roles=["商业分析师", "运营分析师"],
            rationale=f"基于当前画像：{profile_summary[:120]}",
            tasks=tasks,
        )

    def match_job(self, profile_summary: str, job_description: str) -> JobMatch:
        profile_quote = self._quote(profile_summary)
        job_quote = self._quote(job_description)
        scores = {
            MatchDimension.requirements: 82,
            MatchDimension.skills: 86,
            MatchDimension.experience: 72,
            MatchDimension.preferences: 78,
            MatchDimension.growth: 80,
        }
        dimensions = [
            DimensionScore(
                dimension=dimension,
                score=score,
                evidence=[
                    Evidence(
                        source="resume"
                        if dimension in {MatchDimension.skills, MatchDimension.experience}
                        else "job",
                        quote=profile_quote
                        if dimension in {MatchDimension.skills, MatchDimension.experience}
                        else job_quote,
                    )
                ],
            )
            for dimension, score in scores.items()
        ]
        overall = round(sum(scores.values()) / len(scores))
        return JobMatch(
            provider=self.provider,
            recommendation="apply" if overall >= 80 else "improve_then_apply",
            overall_score=overall,
            dimensions=dimensions,
            gaps=["建议补充数据可视化工具的成果证据"],
            actions=["针对岗位关键词调整项目描述", "投递前核对硬性条件"],
        )

    def optimize_resume(self, resume_text: str, job_description: str) -> ResumeOptimization:
        original = self._quote(resume_text)
        return ResumeOptimization(
            provider=self.provider,
            suggestions=[
                ResumeSuggestion(
                    original=original,
                    suggested=f"{original}；补充本人可核实的分析规模、职责和业务结果",
                    reason=f"目标岗位强调：{self._quote(job_description, 80)}",
                )
            ],
        )

    def start_interview(self, resume_text: str, job_description: str) -> InterviewQuestion:
        return InterviewQuestion(
            question_id="q1",
            question="请用 STAR 结构说明你在数据分析项目中解决的核心问题。",
            competency="项目分析与表达结构",
        )

    def evaluate_answer(
        self, question: str, answer: str, job_description: str
    ) -> InterviewEvaluation:
        has_numbers = any(character.isdigit() for character in answer)
        score = 82 if has_numbers else 70
        return InterviewEvaluation(
            provider=self.provider,
            content_completeness=score,
            job_relevance=78,
            answer_structure=75,
            evidence_quality=score,
            feedback=["回答已覆盖主要行动", "建议补充可核实的量化结果"],
            follow_up=InterviewQuestion(
                question_id="q2",
                question="这个项目结果如何验证，你本人承担了哪些具体工作？",
                competency="证据充分度",
            ),
        )

    def build_weekly_review(self, metrics: WeeklyMetrics) -> WeeklyReview:
        return WeeklyReview(
            provider=self.provider,
            metrics=metrics,
            insights=[
                f"本周完成 {metrics.applications} 次投递，获得 {metrics.interviews} 次面试。"
            ],
            actions=["复核低匹配岗位", "补充简历量化证据", "完成一次模拟面试"],
        )

    @staticmethod
    def _quote(text: str, length: int = 120) -> str:
        cleaned = " ".join(text.split())
        return cleaned[:length] or "用户尚未提供有效文本"
