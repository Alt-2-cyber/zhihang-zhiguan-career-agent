import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.agents.contracts import ProfileAnalysis


class AgentOutputError(RuntimeError):
    pass


ContractT = TypeVar("ContractT", bound=BaseModel)


class FastGPTAgentGateway:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        app_id: str,
        timeout_seconds: int = 30,
        client: httpx.Client | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.app_id = app_id
        self.client = client or httpx.Client(timeout=timeout_seconds)

    def analyze_profile(
        self, resume_text: str, preferences: dict[str, str]
    ) -> ProfileAnalysis:
        return self._invoke(
            operation="analyze_profile",
            inputs={"resume_text": resume_text, "preferences": preferences},
            contract=ProfileAnalysis,
        )

    def _invoke(
        self,
        *,
        operation: str,
        inputs: dict[str, object],
        contract: type[ContractT],
    ) -> ContractT:
        response = self.client.post(
            f"{self.base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "chatId": self.app_id,
                "stream": False,
                "detail": False,
                "messages": [
                    {
                        "role": "user",
                        "content": json.dumps(
                            {"operation": operation, "inputs": inputs}, ensure_ascii=False
                        ),
                    }
                ],
            },
        )
        response.raise_for_status()
        try:
            content = response.json()["choices"][0]["message"]["content"]
            return contract.model_validate_json(content)
        except (KeyError, IndexError, TypeError, ValidationError, json.JSONDecodeError) as error:
            raise AgentOutputError("平台未返回符合约定的结构化输出") from error

