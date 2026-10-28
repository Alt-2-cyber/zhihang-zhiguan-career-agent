from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SpecialistName = Literal[
    "career",
    "job",
    "resume",
    "application",
    "interview",
    "counselor",
    "learning",
    "workplace",
    "intelligence",
    "employment",
]


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationMessage(ContractModel):
    role: Literal["user", "assistant", "tool"]
    content: str = Field(min_length=1, max_length=12_000)
    message_id: str | None = Field(default=None, max_length=36)


class ToolCatalogItem(ContractModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_.]{2,79}$")
    description: str = Field(min_length=1, max_length=300)
    input_schema: dict[str, object] = Field(default_factory=dict)
    version: str = Field(default="1", max_length=20)
    risk: Literal["read", "normal_write", "high_risk"] = "read"


class AgentLimits(ContractModel):
    max_steps: int = Field(ge=1, le=12)
    max_tool_calls: int = Field(ge=1, le=30)


class AgentStepPlan(ContractModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")
    agent: SpecialistName
    instruction: str = Field(min_length=1, max_length=500)
    depends_on: list[str] = Field(default_factory=list, max_length=5)


class ConversationPlan(ContractModel):
    intent: str = Field(min_length=1, max_length=80)
    steps: list[AgentStepPlan] = Field(min_length=1, max_length=6)

    @model_validator(mode="after")
    def validate_graph(self) -> "ConversationPlan":
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("step ids must be unique")
        known: set[str] = set()
        for step in self.steps:
            if not set(step.depends_on).issubset(known):
                raise ValueError("dependencies must reference earlier steps")
            known.add(step.id)
        return self


class ToolRequest(ContractModel):
    name: str = Field(pattern=r"^[a-z][a-z0-9_.]{2,79}$")
    arguments: dict[str, object] = Field(default_factory=dict)


class Citation(ContractModel):
    source_type: str = Field(min_length=1, max_length=40)
    source_id: str | None = Field(default=None, max_length=120)
    label: str = Field(min_length=1, max_length=160)
    excerpt: str = Field(min_length=1, max_length=500)
    url: str | None = Field(default=None, max_length=1_000)


class SuggestedAction(ContractModel):
    tool_name: str = Field(pattern=r"^[a-z][a-z0-9_.]{2,79}$")
    title: str = Field(min_length=1, max_length=120)
    rationale: str = Field(min_length=1, max_length=500)
    arguments: dict[str, object] = Field(default_factory=dict)


class SpecialistDecision(ContractModel):
    analysis: str = Field(min_length=1, max_length=2_000)
    tool_requests: list[ToolRequest] = Field(default_factory=list, max_length=4)


class SpecialistOutput(ContractModel):
    agent: SpecialistName
    summary: str = Field(min_length=1, max_length=4_000)
    citations: list[Citation] = Field(default_factory=list, max_length=20)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list, max_length=8)


class ConversationAnswer(ContractModel):
    provider: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=12_000)
    citations: list[Citation] = Field(default_factory=list, max_length=30)
    suggested_actions: list[SuggestedAction] = Field(default_factory=list, max_length=10)


class MemorySummary(ContractModel):
    confirmed_facts: list[str] = Field(default_factory=list, max_length=30)
    preferences: list[str] = Field(default_factory=list, max_length=20)
    unresolved_actions: list[str] = Field(default_factory=list, max_length=20)
    source_message_ids: list[str] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def require_sources(self) -> "MemorySummary":
        if (
            self.confirmed_facts or self.preferences or self.unresolved_actions
        ) and not self.source_message_ids:
            raise ValueError("summary facts require source message ids")
        return self


class PlanTurnRequest(ContractModel):
    messages: list[ConversationMessage] = Field(min_length=1, max_length=20)
    context: dict[str, object] = Field(default_factory=dict)
    tool_catalog: list[ToolCatalogItem] = Field(default_factory=list, max_length=40)
    limits: AgentLimits


class SpecialistRequest(ContractModel):
    step: AgentStepPlan
    messages: list[ConversationMessage] = Field(min_length=1, max_length=20)
    context: dict[str, object] = Field(default_factory=dict)
    dependency_outputs: list[SpecialistOutput] = Field(default_factory=list, max_length=6)
    tool_catalog: list[ToolCatalogItem] = Field(default_factory=list, max_length=20)
    tool_results: list[dict[str, object]] = Field(default_factory=list, max_length=12)


class SpecialistSummaryRequest(ContractModel):
    step: AgentStepPlan
    decision: SpecialistDecision
    dependency_outputs: list[SpecialistOutput] = Field(default_factory=list, max_length=6)
    tool_results: list[dict[str, object]] = Field(default_factory=list, max_length=12)


class ComposeAnswerRequest(ContractModel):
    messages: list[ConversationMessage] = Field(min_length=1, max_length=20)
    specialist_outputs: list[SpecialistOutput] = Field(min_length=1, max_length=6)
    pending_actions: list[SuggestedAction] = Field(default_factory=list, max_length=10)


class MemorySummaryRequest(ContractModel):
    previous_summary: MemorySummary | None = None
    messages: list[ConversationMessage] = Field(min_length=1, max_length=40)
