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
