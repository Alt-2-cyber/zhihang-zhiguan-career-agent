from datetime import date
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
    question_id: str
    question: str = Field(min_length=1)
    competency: str = Field(min_length=1)


class InterviewEvaluation(BaseModel):
    provider: str
    content_completeness: int = Field(ge=0, le=100)
    job_relevance: int = Field(ge=0, le=100)
    answer_structure: int = Field(ge=0, le=100)
    evidence_quality: int = Field(ge=0, le=100)
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

