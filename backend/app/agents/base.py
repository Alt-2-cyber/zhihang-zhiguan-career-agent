from typing import Protocol

from app.agents.contracts import (
    CareerPlan,
    InterviewEvaluation,
    InterviewQuestion,
    JobMatch,
    LearningExamGeneration,
    ProfileAnalysis,
    ResumeOptimization,
    TrainingExchange,
    WeeklyMetrics,
    WeeklyReview,
    WorkplaceDeliverableGeneration,
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

    def generate_learning_exam(
        self,
        *,
        skill_name: str,
        context: dict[str, object],
        question_count: int,
    ) -> LearningExamGeneration: ...

    def generate_training_exchange(
        self,
        *,
        mode: str,
        stage: str,
        prompt: str,
        student_response: str,
        stress_level: str,
        material_context: list[str],
        expected_stage: str = "scoring",
    ) -> TrainingExchange: ...

    def generate_workplace_deliverable(
        self,
        *,
        action_type: str,
        work_context: dict[str, object],
        session_history: list[dict[str, object]],
        current_draft: str | None = None,
    ) -> WorkplaceDeliverableGeneration: ...
