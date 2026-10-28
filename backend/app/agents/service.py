from sqlalchemy.orm import Session

from app.agents.base import AgentGateway
from app.agents.conversation_gateway import (
    ConversationGateway,
    FailoverConversationGateway,
    LocalRuleConversationGateway,
    OpenAIConversationGateway,
)
from app.agents.failover import FailoverAgentGateway
from app.agents.fastgpt import FastGPTAgentGateway
from app.agents.local import LocalAgentGateway
from app.agents.openai_compatible import OpenAICompatibleAgentGateway
from app.agents.skills import PromptResolver
from app.agents.usage import build_db_usage_recorder
from app.core.config import Settings


def _provider_order(settings: Settings) -> list[str]:
    seen: set[str] = set()
    order: list[str] = []
    for item in settings.agent_provider_order.split(","):
        name = item.strip().lower()
        if name in {"zhipu", "deepseek"} and name not in seen:
            seen.add(name)
            order.append(name)
    for name in ("zhipu", "deepseek"):
        if name not in seen:
            order.append(name)
    return order


def _build_structured_provider(
    name: str,
    settings: Settings,
    *,
    usage_recorder=None,
    prompt_version: str | None = None,
    prompt_resolver: PromptResolver | None = None,
) -> AgentGateway | None:
    if name == "zhipu" and settings.zhipu_api_key:
        return OpenAICompatibleAgentGateway(
            provider=f"zhipu:{settings.zhipu_model}",
            base_url=settings.zhipu_base_url,
            api_key=settings.zhipu_api_key,
            model=settings.zhipu_model,
            timeout_seconds=settings.agent_timeout_seconds,
            usage_recorder=usage_recorder,
            prompt_version=prompt_version,
            input_cost_per_million_usd=settings.agent_input_cost_per_million_usd,
            output_cost_per_million_usd=settings.agent_output_cost_per_million_usd,
            prompt_resolver=prompt_resolver,
        )
    if name == "deepseek" and settings.deepseek_api_key:
        return OpenAICompatibleAgentGateway(
            provider=f"deepseek:{settings.deepseek_model}",
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            timeout_seconds=settings.agent_timeout_seconds,
            usage_recorder=usage_recorder,
            prompt_version=prompt_version,
            input_cost_per_million_usd=settings.agent_input_cost_per_million_usd,
            output_cost_per_million_usd=settings.agent_output_cost_per_million_usd,
            prompt_resolver=prompt_resolver,
        )
    return None


def _build_conversation_provider(
    name: str,
    settings: Settings,
    *,
    usage_recorder=None,
    prompt_version: str | None = None,
    prompt_resolver: PromptResolver | None = None,
) -> ConversationGateway | None:
    if name == "zhipu" and settings.zhipu_api_key:
        return OpenAIConversationGateway(
            provider=f"zhipu:{settings.zhipu_model}",
            base_url=settings.zhipu_base_url,
            api_key=settings.zhipu_api_key,
            model=settings.zhipu_model,
            timeout_seconds=settings.agent_timeout_seconds,
            usage_recorder=usage_recorder,
            prompt_version=prompt_version,
            input_cost_per_million_usd=settings.agent_input_cost_per_million_usd,
            output_cost_per_million_usd=settings.agent_output_cost_per_million_usd,
            prompt_resolver=prompt_resolver,
        )
    if name == "deepseek" and settings.deepseek_api_key:
        return OpenAIConversationGateway(
            provider=f"deepseek:{settings.deepseek_model}",
            base_url=settings.deepseek_base_url,
            api_key=settings.deepseek_api_key,
            model=settings.deepseek_model,
            timeout_seconds=settings.agent_timeout_seconds,
            usage_recorder=usage_recorder,
            prompt_version=prompt_version,
            input_cost_per_million_usd=settings.agent_input_cost_per_million_usd,
            output_cost_per_million_usd=settings.agent_output_cost_per_million_usd,
            prompt_resolver=prompt_resolver,
        )
    return None


def build_agent_gateway(
    settings: Settings,
    *,
    db: Session | None = None,
    owner_id: str | None = None,
    run_id: str | None = None,
) -> AgentGateway:
    usage_recorder = (
        build_db_usage_recorder(db, run_id=run_id, owner_id=owner_id) if db is not None else None
    )
    prompt_resolver = PromptResolver(db)
    if settings.agent_provider == "local":
        return LocalAgentGateway()
    if settings.agent_provider == "failover":
        providers = [
            provider
            for provider in (
                _build_structured_provider(
                    name,
                    settings,
                    usage_recorder=usage_recorder,
                    prompt_resolver=prompt_resolver,
                )
                for name in _provider_order(settings)
            )
            if provider is not None
        ]
        return FailoverAgentGateway(
            providers=providers,
            fallback=LocalAgentGateway() if settings.agent_allow_local_fallback else None,
            retry_attempts=settings.agent_retry_attempts,
            circuit_failure_threshold=settings.agent_circuit_failure_threshold,
            circuit_reset_seconds=settings.agent_circuit_reset_seconds,
        )
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


def build_conversation_gateway(
    settings: Settings,
    *,
    db: Session | None = None,
    owner_id: str | None = None,
    run_id: str | None = None,
) -> ConversationGateway:
    usage_recorder = (
        build_db_usage_recorder(db, run_id=run_id, owner_id=owner_id) if db is not None else None
    )
    prompt_resolver = PromptResolver(db)
    if settings.agent_provider == "local":
        return LocalRuleConversationGateway()
    if settings.agent_provider == "failover":
        providers = [
            provider
            for provider in (
                _build_conversation_provider(
                    name,
                    settings,
                    usage_recorder=usage_recorder,
                    prompt_resolver=prompt_resolver,
                )
                for name in _provider_order(settings)
            )
            if provider is not None
        ]
        return FailoverConversationGateway(
            providers=providers,
            fallback=LocalRuleConversationGateway() if settings.agent_allow_local_fallback else None,
            retry_attempts=settings.agent_retry_attempts,
            circuit_failure_threshold=settings.agent_circuit_failure_threshold,
            circuit_reset_seconds=settings.agent_circuit_reset_seconds,
        )
    raise ValueError(f"Unsupported conversation provider: {settings.agent_provider}")
