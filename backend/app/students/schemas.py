from typing import Any

from pydantic import BaseModel, Field


class ProfileAnalysisCreate(BaseModel):
    resume_text: str = Field(min_length=1, max_length=100_000)
    preferences: dict[str, str] = Field(default_factory=dict)


class ProfileAnalysisDraftRead(BaseModel):
    id: str
    provider: str
    status: str
    analysis: dict[str, Any]


class StudentProfileRead(BaseModel):
    id: str
    student_id: str
    summary: str
    strengths: list[dict[str, Any]]
    gaps: list[str]
    constraints: list[str]
    status: str
    version: int

