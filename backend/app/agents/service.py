from app.agents.base import AgentGateway
from app.agents.fastgpt import FastGPTAgentGateway
from app.agents.local import LocalAgentGateway
from app.core.config import Settings


def build_agent_gateway(settings: Settings) -> AgentGateway:
    if settings.agent_provider == "local":
        return LocalAgentGateway()
    if settings.agent_provider == "fastgpt":
        if not settings.fastgpt_base_url or not settings.fastgpt_api_key:
            raise ValueError("FastGPT provider requires base URL and API key")
        return FastGPTAgentGateway(
            base_url=settings.fastgpt_base_url,
            api_key=settings.fastgpt_api_key,
            app_id=settings.fastgpt_app_id,
            timeout_seconds=settings.agent_timeout_seconds,
        )
    raise ValueError(f"Unsupported agent provider: {settings.agent_provider}")

