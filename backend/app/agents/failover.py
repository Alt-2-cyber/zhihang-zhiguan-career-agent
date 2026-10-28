from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from typing import Any, TypeVar

from app.agents.base import AgentGateway
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
from app.core.errors import AppError


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool, status_code: int | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


def _online_provider_unavailable(failures: list[str]) -> AppError:
    reason = "；".join(failures[:6]) or "online_providers=not_configured"
    return AppError(
        503,
        "online_provider_unavailable",
        f"在线模型不可用，未启用本地规则代替。原因：{reason}",
    )


@dataclass
class CircuitState:
    failures: int = 0
    opened_at: float | None = None


ResultT = TypeVar("ResultT")


class FailoverAgentGateway:
    provider = "failover"

    def __init__(
        self,
        *,
        providers: list[AgentGateway],
        fallback: AgentGateway | None = None,
        retry_attempts: int = 1,
        circuit_failure_threshold: int = 3,
        circuit_reset_seconds: int = 60,
        now: Callable[[], float] = monotonic,
    ) -> None:
        self.providers = providers
        self.fallback = fallback
        self.retry_attempts = retry_attempts
        self.circuit_failure_threshold = circuit_failure_threshold
        self.circuit_reset_seconds = circuit_reset_seconds
        self.now = now
        self._circuits = {id(provider): CircuitState() for provider in providers}

    def _circuit_allows(self, provider: AgentGateway) -> bool:
        state = self._circuits[id(provider)]
        if state.opened_at is None:
            return True
        if self.now() - state.opened_at < self.circuit_reset_seconds:
            return False
        state.failures = 0
        state.opened_at = None
        return True

    def _record_success(self, provider: AgentGateway) -> None:
        state = self._circuits[id(provider)]
        state.failures = 0
        state.opened_at = None

    def _record_failure(self, provider: AgentGateway) -> None:
        state = self._circuits[id(provider)]
        state.failures += 1
        if state.failures >= self.circuit_failure_threshold:
            state.opened_at = self.now()

    def _invoke(self, method: str, *args: Any, **kwargs: Any) -> ResultT:
        failures: list[str] = []
        if not self.providers:
            failures.append("online_providers=not_configured")
        for provider in self.providers:
            if not self._circuit_allows(provider):
                failures.append(f"{getattr(provider, 'provider', 'unknown-provider')}=circuit_open")
                continue
            attempt = 0
            while True:
                try:
                    result = getattr(provider, method)(*args, **kwargs)
                    self._record_success(provider)
                    return result
                except Exception as error:
                    retryable = isinstance(error, ProviderError) and error.retryable
                    if retryable and attempt < self.retry_attempts:
                        attempt += 1
                        continue
                    self._record_failure(provider)
                    failures.append(
                        f"{getattr(provider, 'provider', 'unknown-provider')}={str(error) or type(error).__name__}"
                    )
                    break
        if self.fallback is None:
            raise _online_provider_unavailable(failures)
        return getattr(self.fallback, method)(*args, **kwargs)

    def analyze_profile(self, resume_text: str, preferences: dict[str, str]) -> ProfileAnalysis:
        return self._invoke("analyze_profile", resume_text, preferences)

    def build_plan(self, profile_summary: str, target_role: str | None = None) -> CareerPlan:
        return self._invoke("build_plan", profile_summary, target_role)

    def match_job(self, profile_summary: str, job_description: str) -> JobMatch:
        return self._invoke("match_job", profile_summary, job_description)

    def optimize_resume(self, resume_text: str, job_description: str) -> ResumeOptimization:
        return self._invoke("optimize_resume", resume_text, job_description)

    def start_interview(
        self,
        resume_text: str,
        job_description: str,
        interview_type: str = "standard",
    ) -> InterviewQuestion:
        return self._invoke("start_interview", resume_text, job_description, interview_type)

    def evaluate_answer(
        self,
        question: str,
        answer: str,
        job_description: str,
        interview_type: str = "standard",
        question_id: str | None = None,
    ) -> InterviewEvaluation:
        return self._invoke(
            "evaluate_answer",
            question,
            answer,
            job_description,
            interview_type,
            question_id,
        )

    def build_weekly_review(self, metrics: WeeklyMetrics) -> WeeklyReview:
        return self._invoke("build_weekly_review", metrics)

    def generate_learning_exam(
        self,
        *,
        skill_name: str,
        context: dict[str, object],
        question_count: int,
    ) -> LearningExamGeneration:
        return self._invoke(
            "generate_learning_exam",
            skill_name=skill_name,
            context=context,
            question_count=question_count,
        )

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
    ) -> TrainingExchange:
        return self._invoke(
            "generate_training_exchange",
            mode=mode,
            stage=stage,
            prompt=prompt,
            student_response=student_response,
            stress_level=stress_level,
            material_context=material_context,
            expected_stage=expected_stage,
        )

    def generate_workplace_deliverable(
        self,
        *,
        action_type: str,
        work_context: dict[str, object],
        session_history: list[dict[str, object]],
        current_draft: str | None = None,
    ) -> WorkplaceDeliverableGeneration:
        return self._invoke(
            "generate_workplace_deliverable",
            action_type=action_type,
            work_context=work_context,
            session_history=session_history,
            current_draft=current_draft,
        )
