from __future__ import annotations

from apps.api.domain.models import (
    ApprovalRequest,
    ToolActionType,
    ToolDefinition,
    ToolGatewayResult,
    ToolRequest,
)


class LocalToolGateway:
    """로컬에서 외부 업무 시스템 응답을 재현하는 tool gateway."""

    def invoke(self, request: ToolRequest, definition: ToolDefinition) -> ToolGatewayResult:
        if definition.action_type == ToolActionType.READ:
            return ToolGatewayResult(
                status="succeeded",
                reason="조회성 tool gateway 실행이 완료됐습니다.",
                output_payload={
                    "result": "local_gateway_read_result",
                    "source": request.name,
                    "data": request.input_payload,
                },
            )

        return ToolGatewayResult(
            status="succeeded",
            reason="업무 tool gateway 실행이 기록됐습니다.",
            output_payload={
                "result": "local_gateway_action_recorded",
                "source": request.name,
            },
        )

    def replay(self, approval: ApprovalRequest) -> ToolGatewayResult:
        return ToolGatewayResult(
            status="succeeded",
            reason="승인된 tool 요청을 gateway에서 replay했습니다.",
            output_payload={
                "result": "approved_action_replayed",
                "approval_id": str(approval.id),
                "tool_execution_id": str(approval.tool_execution_id),
            },
        )
