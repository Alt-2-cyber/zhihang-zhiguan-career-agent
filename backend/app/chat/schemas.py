from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

ChatMode = Literal["confirm", "auto"]
ChatSessionStatus = Literal["active", "archived"]
ActionProposalStatus = Literal[
    "pending",
    "executing",
    "succeeded",
    "failed",
    "rejected",
    "expired",
    "undone",
]


class ChatSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ChatSessionCreate(ChatSchema):
    subject_student_id: str | None = Field(default=None, max_length=36)
    title: str = Field(default="新对话", min_length=1, max_length=120)
    mode: ChatMode = "confirm"


class ChatSessionUpdate(ChatSchema):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    mode: ChatMode | None = None
    status: ChatSessionStatus | None = None


class ActionDecision(ChatSchema):
    decision: Literal["confirm", "reject"]


ContextType = Literal[
    "student",
    "profile",
    "plan",
    "task",
    "job",
    "resume",
    "application",
    "intervention",
    "learning_task",
    "simulation_session",
    "workplace_session",
    "employment",
    "employment_record",
    "job_intelligence",
    "quality_feedback",
]


class ChatContextRef(ChatSchema):
    type: ContextType
    id: str = Field(min_length=1, max_length=120)


class ChatMessageCreate(ChatSchema):
    content: str = Field(min_length=1, max_length=12_000)
    attachment_ids: list[str] = Field(default_factory=list, max_length=10)
    context_refs: list[ChatContextRef] = Field(default_factory=list, max_length=10)


class ChatMessageAccepted(ChatSchema):
    message_id: str
    run_id: str
    events_url: str
    status: Literal["queued"] = "queued"


class AgentStepDetail(ChatSchema):
    id: str
    step_key: str
    agent: str
    instruction: str
    status: str
    dependencies: list[str]
    conclusion: str | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    tool_call_ids: list[str]


class ToolCallDetail(ChatSchema):
    id: str
    step_key: str | None
    name: str
    version: str
    risk: str
    status: str
    arguments: dict[str, JsonValue]
    result: JsonValue | None
    error_code: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None


class AgentRunDetails(ChatSchema):
    run_id: str
    status: str
    provider: str
    started_at: datetime | None
    completed_at: datetime | None
    duration_ms: int | None
    model_call_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_micros: int
    steps: list[AgentStepDetail]
    tools: list[ToolCallDetail]
