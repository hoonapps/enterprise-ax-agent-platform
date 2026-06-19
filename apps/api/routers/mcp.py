from __future__ import annotations

import json
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends

from apps.api.core.container import AppContainer, get_container
from apps.api.domain.models import ToolActionType, ToolDecision, ToolDefinition, ToolExecution
from apps.api.schemas.mcp import McpJsonRpcRequest

router = APIRouter(tags=["mcp"])
ContainerDep = Annotated[AppContainer, Depends(get_container)]

PROTOCOL_VERSION = "2025-03-26"


@router.post("/mcp")
def handle_mcp(request: McpJsonRpcRequest, container: ContainerDep) -> dict[str, Any]:
    if request.jsonrpc != "2.0":
        return _error(request.id, -32600, "Invalid Request", "jsonrpc must be '2.0'")

    if request.method == "initialize":
        return _result(
            request.id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {
                    "name": "enterprise-ax-agent-platform",
                    "version": "0.1.0",
                },
            },
        )

    if request.method == "tools/list":
        return _result(
            request.id,
            {"tools": [_tool_to_mcp(tool) for tool in container.tool_registry.list_tools()]},
        )

    if request.method == "tools/call":
        return _handle_tool_call(request=request, container=container)

    return _error(request.id, -32601, "Method not found", request.method)


def _handle_tool_call(
    *,
    request: McpJsonRpcRequest,
    container: AppContainer,
) -> dict[str, Any]:
    tool_name = request.params.get("name")
    if not isinstance(tool_name, str) or not tool_name:
        return _error(request.id, -32602, "Invalid params", "params.name is required")

    raw_arguments = request.params.get("arguments", {})
    if not isinstance(raw_arguments, dict):
        return _error(request.id, -32602, "Invalid params", "params.arguments must be an object")
    arguments = cast(dict[str, Any], raw_arguments)

    tenant_id = _string_param(request.params, "tenant_id", "default")
    actor_id = _string_param(request.params, "actor_id", "mcp-client")
    actor_scopes = _string_list_param(request.params, "actor_scopes")

    execution = container.call_tool.execute(
        tenant_id=tenant_id,
        tool_name=tool_name,
        arguments=arguments,
        actor_id=actor_id,
        actor_scopes=actor_scopes,
    )
    return _result(request.id, _execution_to_mcp_result(execution))


def _tool_to_mcp(tool: ToolDefinition) -> dict[str, Any]:
    return {
        "name": tool.name,
        "description": tool.description,
        "inputSchema": tool.input_schema,
        "annotations": {
            "readOnlyHint": tool.action_type == ToolActionType.READ,
            "destructiveHint": tool.action_type == ToolActionType.WRITE,
            "idempotentHint": False,
            "openWorldHint": True,
        },
        "_meta": {
            "required_scope": tool.required_scope,
            "risk_level": tool.risk_level,
            "enabled": tool.enabled,
        },
    }


def _execution_to_mcp_result(execution: ToolExecution) -> dict[str, Any]:
    structured = {
        "tool_execution_id": str(execution.id),
        "tool_name": execution.tool_name,
        "action_type": execution.action_type.value,
        "decision": execution.decision.value,
        "status": execution.status,
        "reason": execution.reason,
        "input_payload": execution.input_payload,
        "output_payload": execution.output_payload,
    }
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(structured, ensure_ascii=False, sort_keys=True),
            }
        ],
        "structuredContent": structured,
        "isError": execution.decision == ToolDecision.DENIED,
    }


def _string_param(params: dict[str, Any], key: str, default: str) -> str:
    value = params.get(key, default)
    return value if isinstance(value, str) and value else default


def _string_list_param(params: dict[str, Any], key: str) -> list[str]:
    value = params.get(key, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _result(request_id: str | int | None, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(
    request_id: str | int | None,
    code: int,
    message: str,
    data: str,
) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message, "data": data},
    }
