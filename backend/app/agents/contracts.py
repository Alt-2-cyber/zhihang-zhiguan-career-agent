import re
from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Evidence(BaseModel):
    source: str = Field(min_length=1, max_length=80)
    quote: str = Field(min_length=1, max_length=500)


class CapabilityTag(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    level: str = Field(min_length=1, max_length=40)
    evidence: list[Evidence] = Field(min_length=1)


class ProfileAnalysis(BaseModel):
    provider: str
    summary: str = Field(min_length=1)
    strengths: list[CapabilityTag]
    gaps: list[str]
    constraints: list[str]


class PlanTask(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    week: int = Field(ge=1, le=4)
    due_date: date
    acceptance_criteria: str = Field(min_length=1, max_length=300)


class CareerPlan(BaseModel):
    provider: str
    primary_role: str = Field(min_length=1, max_length=100)
    backup_roles: list[str] = Field(max_length=2)
    rationale: str = Field(min_length=1)
    tasks: list[PlanTask] = Field(min_length=1)


class MatchDimension(StrEnum):
    requirements = "requirements"
    skills = "skills"
    experience = "experience"
    preferences = "preferences"
    growth = "growth"


class DimensionScore(BaseModel):
    dimension: MatchDimension
    score: int = Field(ge=0, le=100)
    evidence: list[Evidence]


class JobMatch(BaseModel):
    provider: str
    recommendation: Literal["apply", "improve_then_apply", "not_recommended"]
    overall_score: int = Field(ge=0, le=100)
    dimensions: list[DimensionScore]
    gaps: list[str]
    actions: list[str]

    @model_validator(mode="after")
    def require_five_dimensions(self) -> "JobMatch":
        actual = {item.dimension for item in self.dimensions}
        expected = set(MatchDimension)
        if actual != expected or len(self.dimensions) != len(expected):
            raise ValueError("必须提供完整且唯一的五个匹配维度")
        return self


class ResumeSuggestion(BaseModel):
    original: str = Field(min_length=1)
    suggested: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    requires_confirmation: bool = True


class ResumeOptimization(BaseModel):
    provider: str
    suggestions: list[ResumeSuggestion]


class InterviewQuestion(BaseModel):
    provider: str = "unknown"
    question_id: str
    question: str = Field(min_length=1)
    competency: str = Field(min_length=1)


class InterviewEvaluation(BaseModel):
    provider: str
    content_completeness: int = Field(ge=0, le=100)
    job_relevance: int = Field(ge=0, le=100)
    answer_structure: int = Field(ge=0, le=100)
    evidence_quality: int = Field(ge=0, le=100)
    emotion_stability: int | None = Field(default=None, ge=0, le=100)
    feedback: list[str]
    follow_up: InterviewQuestion | None = None


class WeeklyMetrics(BaseModel):
    applications: int = Field(ge=0)
    responses: int = Field(ge=0)
    assessments: int = Field(ge=0)
    interviews: int = Field(ge=0)
    offers: int = Field(ge=0)


class WeeklyReview(BaseModel):
    provider: str
    metrics: WeeklyMetrics
    insights: list[str]
    actions: list[str] = Field(max_length=3)

    @field_validator("insights", "actions")
    @classmethod
    def require_chinese_content(cls, values: list[str]) -> list[str]:
        if any(not any("\u3400" <= char <= "\u9fff" for char in item) for item in values):
            raise ValueError("周复盘洞察和行动必须使用中文")
        employer_terms = ("候选人", "面试官", "离职率", "招聘营销", "吸引申请")
        if any(term in item for item in values for term in employer_terms):
            raise ValueError("周复盘必须使用求职学生视角")
        return values


class ExamOption(BaseModel):
    key: Literal["A", "B", "C", "D"]
    text: str = Field(min_length=1, max_length=300)


class GeneratedExamQuestion(BaseModel):
    question_type: Literal["single_choice"] = "single_choice"
    prompt: str = Field(min_length=1, max_length=1_000)
    options: list[ExamOption] = Field(min_length=4, max_length=4)
    correct_answer: Literal["A", "B", "C", "D"]
    explanation: str = Field(min_length=1, max_length=1_000)
    competency: str = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_options(self) -> "GeneratedExamQuestion":
        keys = [item.key for item in self.options]
        if set(keys) != {"A", "B", "C", "D"}:
            raise ValueError("exam options must contain exactly A, B, C and D")
        if not _has_cjk(self.prompt) or not _has_cjk(self.explanation):
            raise ValueError("exam prompt and explanation must use Simplified Chinese")
        if not _has_cjk(self.competency) and not _is_technical_term(self.competency):
            raise ValueError("exam competency must use Simplified Chinese")
        if any(
            not _has_cjk(item.text) and not _is_technical_term(item.text)
            for item in self.options
        ):
            raise ValueError("exam options must use Simplified Chinese or technical terms")
        return self


def _has_cjk(value: str) -> bool:
    return any("\u3400" <= char <= "\u9fff" for char in value)


def _is_technical_term(value: str) -> bool:
    value = value.strip()
    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_./+#:-]{0,63}", value):
        return True
    return bool(
        re.fullmatch(
            r"[A-Z][A-Za-z0-9.+#/-]*(?:\s+[A-Z][A-Za-z0-9.+#/-]*){1,2}",
            value,
        )
    )


class LearningExamGeneration(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    prompt_version: str = Field(min_length=1, max_length=40)
    questions: list[GeneratedExamQuestion] = Field(min_length=1, max_length=20)


class TrainingRoleMessage(BaseModel):
    speaker: Literal[
        "interviewer",
        "reviewer",
        "career_coach",
        "candidate_logic",
        "candidate_collaboration",
        "candidate_challenger",
    ]
    display_name: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=1_000)
    reply_to_speaker: str | None = Field(default=None, max_length=60)


class TrainingExchange(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    messages: list[TrainingRoleMessage] = Field(min_length=1, max_length=4)
    next_stage: str = Field(min_length=1, max_length=60)
    feedback: list[str] = Field(min_length=1, max_length=4)

    @model_validator(mode="after")
    def reject_duplicate_roles(self) -> "TrainingExchange":
        speakers = [item.speaker for item in self.messages]
        if len(speakers) != len(set(speakers)):
            raise ValueError("training exchange roles must be unique")
        return self


class WorkplaceDeliverableGeneration(BaseModel):
    """Structured output for an AI-assisted post-hire work artifact."""

    provider: str = Field(min_length=1, max_length=80)
    action_type: Literal[
        "clarify_questions",
        "action_plan",
        "risk_register",
        "meeting_minutes",
        "weekly_report",
        "delivery_draft",
    ]
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=20, max_length=20_000)
    rationale: list[str] = Field(min_length=1, max_length=5)
