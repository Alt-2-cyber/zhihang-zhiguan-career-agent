from typing import Protocol

from app.agents.contracts import (
    CareerPlan,
    InterviewEvaluation,
    InterviewQuestion,
    JobMatch,
    ProfileAnalysis,
    ResumeOptimization,
    WeeklyMetrics,
    WeeklyReview,
)


class AgentGateway(Protocol):
    def analyze_profile(self, resume_text: str, preferences: dict[str, str]) -> ProfileAnalysis: ...

    def build_plan(self, profile_summary: str, target_role: str | None = None) -> CareerPlan: ...

    def match_job(self, profile_summary: str, job_description: str) -> JobMatch: ...

    def optimize_resume(self, resume_text: str, job_description: str) -> ResumeOptimization: ...

    def start_interview(self, resume_text: str, job_description: str) -> InterviewQuestion: ...

    def evaluate_answer(
        self, question: str, answer: str, job_description: str
    ) -> InterviewEvaluation: ...

    def build_weekly_review(self, metrics: WeeklyMetrics) -> WeeklyReview: ...
