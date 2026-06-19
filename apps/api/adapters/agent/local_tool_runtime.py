from __future__ import annotations

from uuid import uuid4

from apps.api.application.ports import ToolGatewayPort, ToolRegistryPort
from apps.api.domain.models import (
    ApprovalRequest,
    ToolDecision,
    ToolExecution,
    ToolGatewayResult,
    ToolRequest,
)
from apps.api.domain.policies import ToolPolicy


class LocalToolRuntime:
    """외부 시스템 대신 tool 실행 경계를 검증하는 로컬 runtime."""

    def __init__(
        self,
        *,
        policy: ToolPolicy,
        registry: ToolRegistryPort,
        gateway: ToolGatewayPort,
    ) -> None:
        self.policy = policy
        self.registry = registry
        self.gateway = gateway

    def execute(self, request: ToolRequest) -> ToolExecution:
        definition = self.registry.get(request.name)
        decision, reason = self.policy.evaluate(request=request, definition=definition)

        if decision == ToolDecision.APPROVAL_REQUIRED:
            execution_id = uuid4()
            return ToolExecution(
                id=execution_id,
                tool_name=request.name,
                action_type=request.action_type,
                decision=decision,
                status="pending_approval",
                reason=reason,
                input_payload=request.input_payload,
                output_payload={
                    "approval_ticket": f"approval://{execution_id}",
                    "description": request.description,
                },
            )

        if decision == ToolDecision.DENIED:
            return ToolExecution(
                tool_name=request.name,
                action_type=request.action_type,
                decision=decision,
                status="skipped",
                reason=reason,
                input_payload=request.input_payload,
            )

        if definition is None:
            raise RuntimeError("tool definition must exist after policy evaluation")

        gateway_result = self.gateway.invoke(request=request, definition=definition)

        return ToolExecution(
            tool_name=request.name,
            action_type=request.action_type,
            decision=decision,
            status=gateway_result.status,
            reason=gateway_result.reason or reason,
            input_payload=request.input_payload,
            output_payload=self._with_gateway_metadata(gateway_result),
        )

    def replay_approved(self, approval: ApprovalRequest) -> ToolExecution:
        gateway_result = self.gateway.replay(approval)
        return ToolExecution(
            tool_name=approval.tool_name,
            action_type=approval.action_type,
            decision=ToolDecision.ALLOWED,
            status=gateway_result.status,
            reason=gateway_result.reason,
            input_payload=approval.input_payload,
            output_payload=self._with_gateway_metadata(gateway_result),
        )

    def _with_gateway_metadata(self, result: ToolGatewayResult) -> dict[str, object]:
        return {
            **result.output_payload,
            "_gateway": {
                "attempts": result.attempts,
                "elapsed_ms": result.elapsed_ms,
                "fallback_used": result.fallback_used,
                "error_message": result.error_message,
                "circuit_state": result.circuit_state,
                "circuit_open_remaining_ms": result.circuit_open_remaining_ms,
            },
        }
