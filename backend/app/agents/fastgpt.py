import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

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


class AgentOutputError(RuntimeError):
    pass


ContractT = TypeVar("ContractT", bound=BaseModel)


class FastGPTAgentGateway:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        app_id: str,
        timeout_seconds: int = 30,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.app_id = app_id
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def analyze_profile(self, resume_text: str, preferences: dict[str, str]) -> ProfileAnalysis:
        return self._invoke(
            operation="analyze_profile",
            inputs={"resume_text": resume_text, "preferences": preferences},
            contract=ProfileAnalysis,
        )

    def build_plan(self, profile_summary: str, target_role: str | None = None) -> CareerPlan:
        return self._invoke(
            operation="build_plan",
            inputs={"profile_summary": profile_summary, "target_role": target_role},
            contract=CareerPlan,
        )

    def match_job(self, profile_summary: str, job_description: str) -> JobMatch:
        return self._invoke(
            operation="match_job",
            inputs={
                "profile_summary": profile_summary,
                "job_description": job_description,
            },
            contract=JobMatch,
        )

    def optimize_resume(self, resume_text: str, job_description: str) -> ResumeOptimization:
        return self._invoke(
            operation="optimize_resume",
            inputs={"resume_text": resume_text, "job_description": job_description},
            contract=ResumeOptimization,
        )

    def start_interview(self, resume_text: str, job_description: str) -> InterviewQuestion:
        return self._invoke(
            operation="start_interview",
            inputs={"resume_text": resume_text, "job_description": job_description},
            contract=InterviewQuestion,
        )

    def evaluate_answer(
        self, question: str, answer: str, job_description: str
    ) -> InterviewEvaluation:
        return self._invoke(
            operation="evaluate_answer",
            inputs={
                "question": question,
                "answer": answer,
                "job_description": job_description,
            },
            contract=InterviewEvaluation,
        )

    def build_weekly_review(self, metrics: WeeklyMetrics) -> WeeklyReview:
        return self._invoke(
            operation="build_weekly_review",
            inputs={"metrics": metrics.model_dump(mode="json")},
            contract=WeeklyReview,
        )

    def _invoke(
        self,
        *,
        operation: str,
        inputs: dict[str, object],
        contract: type[ContractT],
    ) -> ContractT:
        response = self.client.post(
            f"{self.base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "chatId": self.app_id,
                "stream": False,
                "detail": False,
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"operation": operation, "inputs": inputs}, ensure_ascii=False
                        ),
                    }
                ],
            },
        )
        response.raise_for_status()
        try:
            content = response.json()["choices"][0]["message"]["content"]
            return contract.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValidationError, json.JSONDecodeError) as error:
            raise AgentOutputError("平台未返回符合约定的结构化输出") from error
