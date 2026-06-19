from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.core.container import AppContainer, get_container
from apps.api.domain.models import ToolDefinition
from apps.api.schemas.tools import ToolDefinitionResponse

router = APIRouter(prefix="/v1/tools", tags=["tools"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]


@router.get("", response_model=list[ToolDefinitionResponse])
def list_tools(container: ContainerDep) -> list[ToolDefinitionResponse]:
    return [_to_response(tool) for tool in container.tool_registry.list_tools()]


def _to_response(tool: ToolDefinition) -> ToolDefinitionResponse:
    return ToolDefinitionResponse(
        name=tool.name,
        action_type=tool.action_type.value,
        required_scope=tool.required_scope,
        risk_level=tool.risk_level,
        description=tool.description,
        input_schema=tool.input_schema,
        output_schema=tool.output_schema,
        enabled=tool.enabled,
    )
