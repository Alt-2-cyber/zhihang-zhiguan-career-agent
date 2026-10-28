from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.auth.models import UserRole


class ToolRisk(StrEnum):
    read = "read"
    normal_write = "normal_write"
    high_risk = "high_risk"


@dataclass(frozen=True)
class ToolExecutionContext:
    session_id: str
    run_id: str
    step_id: str | None
    specialist: str
    actor_id: str
    actor_role: UserRole
    subject_student_id: str | None
    idempotency_key: str


class ToolCitation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(min_length=1, max_length=40)
    source_id: str | None = Field(default=None, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    excerpt: str = Field(min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=1_000)


@dataclass(frozen=True)
class ToolHandlerResult:
    output: BaseModel | dict[str, object]
    citations: tuple[ToolCitation, ...] = field(default_factory=tuple)
    undo_data: dict[str, object] | None = None


class ToolExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_name: str
    version: str
    risk: ToolRisk
    data: dict[str, object]
    citations: list[ToolCitation] = Field(default_factory=list)
    undo_data: dict[str, object] | None = None


class ToolHandler(Protocol):
    def __call__(
        self,
        db: Session,
        arguments: BaseModel,
        context: ToolExecutionContext,
    ) -> ToolHandlerResult: ...


class ToolUndoHandler(Protocol):
    def __call__(
        self,
        db: Session,
        undo_data: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolHandlerResult: ...


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    version: str
    description: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    roles: frozenset[UserRole]
    specialists: frozenset[str]
    risk: ToolRisk
    reversible: bool
    handler: ToolHandler
    undo_handler: ToolUndoHandler | None = None
