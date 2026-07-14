from datetime import date

from pydantic import BaseModel


class PlanGenerateRequest(BaseModel):
    target_role: str | None = None


class PlanTaskRead(BaseModel):
    id: str
    title: str
    week: int
    due_date: date
    acceptance_criteria: str
    status: str


class CareerPlanRead(BaseModel):
    id: str
    provider: str
    primary_role: str
    backup_roles: list[str]
    rationale: str
    status: str
    tasks: list[PlanTaskRead]

