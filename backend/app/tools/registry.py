from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.tools.authorization import authorize_tool_context
from app.tools.contracts import (
    ToolDefinition,
    ToolExecutionContext,
    ToolExecutionResult,
)


class ToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"tool already registered: {definition.name}")
        self._definitions[definition.name] = definition

    def resolve(self, name: str, requested_risk: str | None = None) -> ToolDefinition:
        del requested_risk
        definition = self._definitions.get(name)
        if definition is None:
            raise AppError(400, "tool_not_allowed", "Agent 请求了未注册的工具")
        return definition

    def catalog(self, *, specialist: str, role: str) -> list[dict[str, object]]:
        return [
            {
                "name": definition.name,
                "version": definition.version,
                "description": definition.description,
                "input_schema": definition.input_model.model_json_schema(),
                "risk": definition.risk.value,
            }
            for definition in self._definitions.values()
            if specialist in definition.specialists
            and any(allowed_role.value == role for allowed_role in definition.roles)
        ]

    def execute(
        self,
        db: Session,
        name: str,
        arguments: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        definition = self.resolve(name)
        actor = authorize_tool_context(db, context)
        if actor.role not in definition.roles:
            raise AppError(403, "tool_forbidden", "当前身份不能调用该 Agent 工具")
        if context.specialist not in definition.specialists:
            raise AppError(
                403,
                "tool_not_allowed_for_specialist",
                "当前专业 Agent 不能调用该工具",
            )
        try:
            validated_arguments = definition.input_model.model_validate(arguments)
        except ValidationError as error:
            raise AppError(422, "tool_arguments_invalid", "Agent 工具参数无效") from error

        handler_result = definition.handler(db, validated_arguments, context)
        try:
            validated_output = definition.output_model.model_validate(handler_result.output)
        except ValidationError as error:
            raise AppError(502, "tool_output_invalid", "Agent 工具返回结果无效") from error
        return ToolExecutionResult(
            tool_name=definition.name,
            version=definition.version,
            risk=definition.risk,
            data=validated_output.model_dump(mode="json"),
            citations=list(handler_result.citations),
            undo_data=handler_result.undo_data,
        )

    def undo(
        self,
        db: Session,
        name: str,
        undo_data: dict[str, object],
        context: ToolExecutionContext,
    ) -> ToolExecutionResult:
        definition = self.resolve(name)
        actor = authorize_tool_context(db, context)
        if actor.role not in definition.roles or context.specialist not in definition.specialists:
            raise AppError(403, "tool_forbidden", "当前身份不能撤销该 Agent 工具")
        if not definition.reversible or definition.undo_handler is None:
            raise AppError(409, "action_not_reversible", "该操作不能自动撤销")
        handler_result = definition.undo_handler(db, undo_data, context)
        try:
            validated_output = definition.output_model.model_validate(handler_result.output)
        except ValidationError as error:
            raise AppError(502, "tool_output_invalid", "Agent 工具返回结果无效") from error
        return ToolExecutionResult(
            tool_name=definition.name,
            version=definition.version,
            risk=definition.risk,
            data=validated_output.model_dump(mode="json"),
            citations=list(handler_result.citations),
        )
