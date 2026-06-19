from typing import Any

from pydantic import BaseModel


class ToolDefinitionResponse(BaseModel):
    name: str
    action_type: str
    required_scope: str
    risk_level: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    enabled: bool


class ToolGatewayCircuitStatusResponse(BaseModel):
    tool_name: str
    state: str
    failure_streak: int
    open_remaining_ms: int
    failure_threshold: int
    open_seconds: float
