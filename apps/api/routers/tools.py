from typing import Annotated

from fastapi import APIRouter, Depends

from apps.api.core.container import AppContainer, get_container
from apps.api.core.security import AuthPrincipal, require_scopes
from apps.api.domain.models import ToolDefinition, ToolGatewayCircuitStatus
from apps.api.schemas.tools import ToolDefinitionResponse, ToolGatewayCircuitStatusResponse

router = APIRouter(prefix="/v1/tools", tags=["tools"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]
ToolReadAuth = Annotated[AuthPrincipal, Depends(require_scopes("tools:read"))]


@router.get("", response_model=list[ToolDefinitionResponse])
def list_tools(container: ContainerDep, auth: ToolReadAuth) -> list[ToolDefinitionResponse]:
    _ = auth
    return [_to_response(tool) for tool in container.tool_registry.list_tools()]


@router.get("/gateway/status", response_model=list[ToolGatewayCircuitStatusResponse])
def get_tool_gateway_status(
    container: ContainerDep,
    auth: ToolReadAuth,
) -> list[ToolGatewayCircuitStatusResponse]:
    _ = auth
    tools = container.tool_registry.list_tools()
    statuses = container.tool_gateway.circuit_status(tool_names=[tool.name for tool in tools])
    return [_to_circuit_status_response(status) for status in statuses]


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


def _to_circuit_status_response(
    status: ToolGatewayCircuitStatus,
) -> ToolGatewayCircuitStatusResponse:
    return ToolGatewayCircuitStatusResponse(
        tool_name=status.tool_name,
        state=status.state,
        failure_streak=status.failure_streak,
        open_remaining_ms=status.open_remaining_ms,
        failure_threshold=status.failure_threshold,
        open_seconds=status.open_seconds,
    )
