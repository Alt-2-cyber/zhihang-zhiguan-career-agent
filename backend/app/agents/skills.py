import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.conversation_prompts import OPERATION_INSTRUCTIONS as CONVERSATION_INSTRUCTIONS
from app.agents.models import AgentSkill
from app.agents.prompts import OPERATION_INSTRUCTIONS as STRUCTURED_INSTRUCTIONS


@dataclass(frozen=True)
class ResolvedSkill:
    skill_key: str
    operation: str
    version: str
    prompt_text: str
    contract_name: str
    source: str


def _builtin_skill(kind: str, operation: str) -> ResolvedSkill:
    instructions = (
        STRUCTURED_INSTRUCTIONS if kind == "structured" else CONVERSATION_INSTRUCTIONS
    )
    try:
        prompt_text = instructions[operation]
    except KeyError as error:
        raise ValueError(f"unsupported agent operation: {kind}.{operation}") from error
    version = {
        "generate_learning_exam": "exam-v1",
        "generate_training_exchange": "training-v1",
        "generate_workplace_deliverable": "workplace-v1",
    }.get(operation, f"{kind}-v1")
    return ResolvedSkill(
        skill_key=f"{kind}.{operation}",
        operation=operation,
        version=version,
        prompt_text=prompt_text,
        contract_name="runtime-contract",
        source="builtin",
    )


class PromptResolver:
    def __init__(self, db: Session | None = None) -> None:
        self.db = db

    def resolve(self, kind: str, operation: str) -> ResolvedSkill:
        fallback = _builtin_skill(kind, operation)
        if self.db is None:
            return fallback
        selected = self.db.scalar(
            select(AgentSkill)
            .where(
                AgentSkill.skill_key == fallback.skill_key,
                AgentSkill.status == "active",
            )
            .order_by(AgentSkill.activated_at.desc(), AgentSkill.updated_at.desc())
        )
        if selected is None:
            return fallback
        return ResolvedSkill(
            skill_key=selected.skill_key,
            operation=selected.operation,
            version=selected.version,
            prompt_text=selected.prompt_text,
            contract_name=selected.contract_name,
            source="database",
        )


def prompt_checksum(prompt_text: str) -> str:
    return hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()


def serialize_skill(skill: AgentSkill) -> dict[str, object]:
    try:
        metadata = json.loads(skill.metadata_json)
    except (TypeError, ValueError):
        metadata = {}
    return {
        "id": skill.id,
        "skill_key": skill.skill_key,
        "name": skill.name,
        "operation": skill.operation,
        "version": skill.version,
        "status": skill.status,
        "contract_name": skill.contract_name,
        "checksum": skill.checksum,
        "metadata": metadata,
        "created_by": skill.created_by,
        "activated_at": skill.activated_at,
        "retired_at": skill.retired_at,
        "created_at": skill.created_at,
        "updated_at": skill.updated_at,
    }


def activate_skill(db: Session, skill: AgentSkill) -> None:
    now = datetime.now(timezone.utc)
    active = db.scalars(
        select(AgentSkill).where(
            AgentSkill.skill_key == skill.skill_key,
            AgentSkill.status == "active",
            AgentSkill.id != skill.id,
        )
    ).all()
    for previous in active:
        previous.status = "retired"
        previous.retired_at = now
    skill.status = "active"
    skill.activated_at = now
    skill.retired_at = None
