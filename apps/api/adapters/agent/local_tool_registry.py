from __future__ import annotations

from apps.api.domain.models import ToolActionType, ToolDefinition


class LocalToolRegistry:
    def __init__(self) -> None:
        self._tools = {
            tool.name: tool
            for tool in (
                ToolDefinition(
                    name="internal-records.lookup",
                    action_type=ToolActionType.READ,
                    required_scope="records:read",
                    risk_level="low",
                    description="내부 업무 레코드를 조회한다.",
                    input_schema={
                        "type": "object",
                        "required": ["query"],
                        "properties": {"query": {"type": "string"}},
                    },
                    output_schema={
                        "type": "object",
                        "properties": {"result": {"type": "string"}},
                    },
                ),
                ToolDefinition(
                    name="workflow.request-change",
                    action_type=ToolActionType.WRITE,
                    required_scope="workflow:request",
                    risk_level="high",
                    description="외부 상태 변경이 필요한 workflow 요청을 생성한다.",
                    input_schema={
                        "type": "object",
                        "required": ["request"],
                        "properties": {"request": {"type": "string"}},
                    },
                    output_schema={
                        "type": "object",
                        "properties": {"approval_ticket": {"type": "string"}},
                    },
                ),
            )
        }

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)
