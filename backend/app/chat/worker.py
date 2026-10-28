from sqlalchemy.orm import Session

from app.agents.conversation_gateway import ConversationGateway
from app.ai.clients import AIServiceError
from app.ai.models import AITask
from app.chat.models import AgentRun
from app.chat.orchestrator import run_agent_turn
from app.core.config import Settings
from app.tools.registry import ToolRegistry


def handle_chat_agent_run(
    db: Session,
    task: AITask,
    *,
    gateway: ConversationGateway,
    registry: ToolRegistry,
    settings: Settings,
) -> dict[str, object]:
    run_id = str(task.input_data.get("run_id", ""))
    run = db.get(AgentRun, run_id)
    if run is None:
        raise AIServiceError("agent_run_not_found", "chat agent run is unavailable")
    if task.owner_id is None or run.session_id is None:
        raise AIServiceError("agent_run_invalid", "chat agent run is invalid")
    if run.status in {"failed", "cancelled"}:
        return {"run_id": run.id, "status": run.status}
    return run_agent_turn(
        db,
        run_id=run.id,
        gateway=gateway,
        registry=registry,
        settings=settings,
    )
