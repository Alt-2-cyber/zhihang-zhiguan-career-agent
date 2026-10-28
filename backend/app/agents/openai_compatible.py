import json
from collections.abc import Callable
from datetime import date, datetime, timezone
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.agents.contracts import (
    CareerPlan,
    GeneratedExamQuestion,
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
from app.agents.failover import ProviderError
from app.agents.fastgpt import AgentOutputError
from app.agents.prompts import build_system_prompt
from app.agents.redaction import redact_data
from app.agents.skills import PromptResolver
from app.agents.usage import ModelCallUsage, calculate_cost_micros, parse_usage

ContractT = TypeVar("ContractT", bound=BaseModel)


def _exam_question_key(question: GeneratedExamQuestion) -> str:
    return " ".join(question.prompt.casefold().split())


class OpenAICompatibleAgentGateway:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        timeout_seconds: int = 60,
        client: httpx.Client | None = None,
        usage_recorder: Callable[[ModelCallUsage], None] | None = None,
        prompt_version: str | None = None,
        input_cost_per_million_usd: float | None = None,
        output_cost_per_million_usd: float | None = None,
        prompt_resolver: PromptResolver | None = None,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = client or httpx.Client(timeout=timeout_seconds)
        self.usage_recorder = usage_recorder
        self.prompt_version = prompt_version
        self.input_cost_per_million_usd = input_cost_per_million_usd
        self.output_cost_per_million_usd = output_cost_per_million_usd
        self.prompt_resolver = prompt_resolver

    def analyze_profile(self, resume_text: str, preferences: dict[str, str]) -> ProfileAnalysis:
        return self._invoke(
            "analyze_profile",
            {"resume_text": resume_text, "preferences": preferences},
            ProfileAnalysis,
        )

    def build_plan(self, profile_summary: str, target_role: str | None = None) -> CareerPlan:
        return self._invoke(
            "build_plan",
            {
                "profile_summary": profile_summary,
                "target_role": target_role,
                "today": date.today().isoformat(),
            },
            CareerPlan,
        )

    def match_job(self, profile_summary: str, job_description: str) -> JobMatch:
        return self._invoke(
            "match_job",
            {"profile_summary": profile_summary, "job_description": job_description},
            JobMatch,
        )

    def optimize_resume(self, resume_text: str, job_description: str) -> ResumeOptimization:
        return self._invoke(
            "optimize_resume",
            {"resume_text": resume_text, "job_description": job_description},
            ResumeOptimization,
        )

    def start_interview(
        self,
        resume_text: str,
        job_description: str,
        interview_type: str = "standard",
    ) -> InterviewQuestion:
        return self._invoke(
            "start_interview",
            {
                "resume_text": resume_text,
                "job_description": job_description,
                "interview_type": interview_type,
            },
            InterviewQuestion,
        )

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
            {
                "question": question,
                "answer": answer,
                "job_description": job_description,
                "interview_type": interview_type,
                "question_id": question_id,
            },
            InterviewEvaluation,
        )

    def build_weekly_review(self, metrics: WeeklyMetrics) -> WeeklyReview:
        return self._invoke(
            "build_weekly_review",
            {"metrics": metrics.model_dump(mode="json")},
            WeeklyReview,
        )

    def generate_learning_exam(
        self,
        *,
        skill_name: str,
        context: dict[str, object],
        question_count: int,
    ) -> LearningExamGeneration:
        target_count = max(1, min(question_count, 20))
        collected: list[GeneratedExamQuestion] = []
        prompt_version = "exam-v1"

        # Providers occasionally stop after one or two questions despite the
        # requested count. Ask only for the missing questions and include a
        # compact exclusion list so retries do not silently duplicate items.
        for attempt in range(1, 4):
            remaining = target_count - len(collected)
            if remaining <= 0:
                break
            request_context = dict(context)
            request_context["exam_generation"] = {
                "attempt": attempt,
                "required_question_count": remaining,
                "total_question_count": target_count,
                "output_language": "zh-CN",
                "existing_questions": [
                    {
                        "prompt": item.prompt[:240],
                        "competency": item.competency,
                    }
                    for item in collected
                ],
            }
            generation = self._invoke(
                "generate_learning_exam",
                {
                    "skill_name": skill_name,
                    "context": request_context,
                    "question_count": remaining,
                    "prompt_version": "exam-v1",
                },
                LearningExamGeneration,
            )
            prompt_version = generation.prompt_version
            for question in generation.questions:
                if _exam_question_key(question) in {
                    _exam_question_key(existing) for existing in collected
                }:
                    continue
                collected.append(question)
                if len(collected) >= target_count:
                    break

        if len(collected) < target_count:
            raise AgentOutputError(
                "exam provider returned fewer unique questions than requested "
                f"({len(collected)}/{target_count})"
            )
        return LearningExamGeneration(
            provider=self.provider,
            prompt_version=prompt_version,
            questions=collected[:target_count],
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
            {
                "mode": mode,
                "stage": stage,
                "prompt": prompt,
                "student_response": student_response,
                "stress_level": stress_level,
                "material_context": material_context,
                "expected_stage": expected_stage,
            },
            TrainingExchange,
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
            {
                "action_type": action_type,
                "work_context": work_context,
                "session_history": session_history[-8:],
                "current_draft": current_draft,
            },
            WorkplaceDeliverableGeneration,
        )

    def _invoke(
        self,
        operation: str,
        inputs: dict[str, object],
        contract: type[ContractT],
    ) -> ContractT:
        started_at = datetime.now(timezone.utc)
        request_id: str | None = None
        resolved_prompt = (
            self.prompt_resolver.resolve("structured", operation)
            if self.prompt_resolver is not None
            else None
        )
        prompt_version = resolved_prompt.version if resolved_prompt else self.prompt_version
        body = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": build_system_prompt(
                        operation,
                        contract,
                        instruction=resolved_prompt.prompt_text if resolved_prompt else None,
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(redact_data(inputs), ensure_ascii=False),
                },
            ],
            "response_format": {"type": "json_object"},
            "stream": False,
            "temperature": 0.2,
        }
        try:
            response = self.client.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=body,
            )
            request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
        except (httpx.TimeoutException, httpx.TransportError) as error:
            provider_error = ProviderError(type(error).__name__, retryable=True)
            self._record_failure(
                operation,
                started_at,
                provider_error,
                request_id=request_id,
                prompt_version=prompt_version,
            )
            raise provider_error from error

        if response.status_code >= 400:
            retryable = response.status_code == 429 or response.status_code >= 500
            provider_error = ProviderError(
                f"provider_http_{response.status_code}",
                retryable=retryable,
                status_code=response.status_code,
            )
            self._record_failure(
                operation,
                started_at,
                provider_error,
                request_id=request_id,
                prompt_version=prompt_version,
            )
            raise provider_error

        try:
            payload = response.json()
            content = payload["choices"][0]["message"]["content"]
            result = contract.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValueError, ValidationError) as error:
            output_error = AgentOutputError("模型未返回符合约定的结构化输出")
            self._record_failure(
                operation,
                started_at,
                output_error,
                request_id=request_id,
                prompt_version=prompt_version,
            )
            raise output_error from error

        if "provider" in contract.model_fields:
            result = result.model_copy(update={"provider": self.provider})
        usage = parse_usage(payload)
        self._record_success(
            operation,
            started_at,
            usage,
            request_id=request_id,
            prompt_version=prompt_version,
        )
        return result

    def _record_success(
        self,
        operation: str,
        started_at: datetime,
        usage: dict[str, int | None],
        *,
        request_id: str | None,
        prompt_version: str | None,
    ) -> None:
        self._record(
            ModelCallUsage(
                operation=operation,
                provider=self.provider,
                model=self.model,
                status="succeeded",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                prompt_version=prompt_version,
                input_tokens=usage["input_tokens"],
                output_tokens=usage["output_tokens"],
                total_tokens=usage["total_tokens"],
                cost_micros=calculate_cost_micros(
                    usage,
                    input_cost_per_million_usd=self.input_cost_per_million_usd,
                    output_cost_per_million_usd=self.output_cost_per_million_usd,
                ),
                request_id=request_id,
            )
        )

    def _record_failure(
        self,
        operation: str,
        started_at: datetime,
        error: Exception,
        *,
        request_id: str | None,
        prompt_version: str | None,
    ) -> None:
        self._record(
            ModelCallUsage(
                operation=operation,
                provider=self.provider,
                model=self.model,
                status="failed",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc),
                prompt_version=prompt_version,
                request_id=request_id,
                error_code=(
                    f"provider_http_{error.status_code}"
                    if isinstance(error, ProviderError) and error.status_code
                    else type(error).__name__
                ),
                error_message=str(error)[:300],
            )
        )

    def _record(self, usage: ModelCallUsage) -> None:
        if self.usage_recorder is None:
            return
        try:
            self.usage_recorder(usage)
        except Exception:
            return
